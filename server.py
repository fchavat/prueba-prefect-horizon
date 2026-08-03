"""A minimal FastMCP server with a `sum` tool protected by Google OIDC auth.

Discovery endpoints such as `tools/list` are public. Tool invocation
(`tools/call`) and other sensitive operations require authentication.
"""

import os

import uvicorn
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import AuthorizationError
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.http import create_streamable_http_app
from fastmcp.server.middleware import Middleware as FastMCPMiddleware
from fastmcp.server.middleware import MiddlewareContext
from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware

# Load environment variables from a .env file if one exists.
load_dotenv()


# MCP methods that can be called without authentication.
# `tools/list` is public so clients can discover available tools.
# `initialize` and `notifications/initialized` are public because they are part
# of the MCP handshake, which happens before authentication.
PUBLIC_METHODS = frozenset(
    {
        "initialize",
        "notifications/initialized",
        "tools/list",
    }
)


class SelectiveAuthMiddleware(FastMCPMiddleware):
    """Require authentication for every MCP method except discovery/handshake."""

    async def on_request(self, context: MiddlewareContext, call_next):
        if context.method in PUBLIC_METHODS:
            return await call_next(context)

        token = get_access_token()
        if token is None:
            raise AuthorizationError("Authentication required")

        return await call_next(context)


def create_auth_provider() -> OIDCProxy:
    """Create the Google OIDC proxy used for OAuth endpoints and token validation."""
    # Comma-separated list of redirect URI patterns allowed for MCP clients.
    # Defaults to None (loopback clients only). For CogSol you must add its
    # OAuth callback, e.g.:
    #   ALLOWED_CLIENT_REDIRECT_URIS="https://*.cogsol.com/oauth/callback"
    allowed_uris = os.environ.get("ALLOWED_CLIENT_REDIRECT_URIS")
    allowed_client_redirect_uris = (
        [u.strip() for u in allowed_uris.split(",") if u.strip()]
        if allowed_uris
        else None
    )

    return OIDCProxy(
        config_url="https://accounts.google.com/.well-known/openid-configuration",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        base_url=os.environ.get("BASE_URL", "http://localhost:8000"),
        redirect_path="/auth/callback",
        allowed_client_redirect_uris=allowed_client_redirect_uris,
        required_scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
        # Google access tokens are opaque; validate the OIDC id_token instead.
        verify_id_token=True,
        # Google does not support RFC 8707 resource indicators.
        forward_resource=False,
        # Force the Google account chooser so testing does not reuse a session.
        extra_authorize_params={"prompt": "select_account"},
    )


def create_mcp_server(auth_provider: OIDCProxy) -> FastMCP:
    """Create the FastMCP server with selective authentication in middleware."""
    # The FastMCP instance itself is created WITHOUT auth=auth.  Authentication
    # is enforced in SelectiveAuthMiddleware so we can make `tools/list` public.
    mcp = FastMCP("sum-server")
    mcp.add_middleware(SelectiveAuthMiddleware())

    @mcp.tool()
    async def sum(a: float, b: float) -> float:
        """Return the sum of two numbers.

        This tool is protected by Google authentication. The caller must
        complete the OAuth flow before invoking it.
        """
        token = get_access_token()
        user_id = token.subject
        email = token.claims.get("email")
        print(f"sum invoked by user_id={user_id}, email={email}")
        return a + b

    return mcp


def main() -> None:
    """Build the ASGI app and run it with Uvicorn."""
    auth_provider = create_auth_provider()
    mcp = create_mcp_server(auth_provider)

    # Build the streamable HTTP app manually so we can:
    #   - mount the OAuth provider's routes (metadata, authorize, token, ...)
    #   - apply token-bearing middleware to validate tokens
    #   - leave the MCP endpoint itself unprotected by FastMCP's global
    #     RequireAuthMiddleware, so SelectiveAuthMiddleware decides per method.
    app = create_streamable_http_app(
        server=mcp,
        streamable_http_path="/mcp",
        auth=None,
        stateless_http=True,  # each request is self-contained (no session id required)
        routes=auth_provider.get_routes(mcp_path="/mcp"),
        middleware=[
            Middleware(
                AuthenticationMiddleware,
                backend=BearerAuthBackend(auth_provider),
            ),
            Middleware(AuthContextMiddleware),
        ],
    )

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
