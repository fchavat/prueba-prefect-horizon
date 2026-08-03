"""FastMCP server with a Google-authenticated `sum` tool, deployable to Prefect Horizon.

Horizon entry point:
    server.py:mcp

This version uses FastMCP's built-in ``auth=auth`` support, which protects the
entire MCP endpoint (including ``tools/list``) with Google OAuth 2.1.  The OAuth
metadata and flow endpoints (``/.well-known/oauth-authorization-server``,
``/authorize``, ``/token``, ``/register``, ``/auth/callback``) are mounted
automatically.

For local development you can still run ``uv run server.py``; Horizon ignores
the ``if __name__ == "__main__":`` block and manages the HTTP transport itself.
"""

import os

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from fastmcp.server.dependencies import get_access_token

# Load environment variables from a .env file if one exists.
load_dotenv()


def _create_auth_provider() -> OIDCProxy:
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


# Module-level auth provider and FastMCP instance so Horizon can use
# ``server.py:mcp`` as the entry point.
auth = _create_auth_provider()
mcp = FastMCP("sum-server", auth=auth)


@mcp.tool()
async def sum(a: float, b: float) -> float:
    """Return the sum of two numbers.

    This tool is protected by Google authentication. The caller must complete
    the OAuth flow before invoking it.
    """
    token = get_access_token()
    user_id = token.subject
    email = token.claims.get("email")
    print(f"sum invoked by user_id={user_id}, email={email}")
    return a + b


if __name__ == "__main__":
    # Local development entry point. Horizon ignores this block and runs the
    # server itself using the ``mcp`` object above.
    mcp.run(
        transport="http",
        host="127.0.0.1",
        port=8000,
        stateless_http=True,
    )
