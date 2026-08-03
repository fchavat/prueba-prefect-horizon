# fastmcp-openidc-proxy

A minimal FastMCP server that exposes a single protected `sum` tool and authenticates users via Google OIDC / OAuth 2.1.

## What it does

- Runs an MCP server over HTTP transport.
- Protects every tool with Google authentication using FastMCP's `OIDCProxy`.
- Demonstrates how to read the authenticated user's identity inside a tool.

## Prerequisites

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/)
- A Google Cloud project with an OAuth 2.0 **Web application** Client ID

## Google Cloud setup

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials).
2. Click **Create Credentials → OAuth client ID** and choose **Web application**.
3. Under **Authorized redirect URIs**, add:
   ```
   http://localhost:8000/auth/callback
   ```
4. Save the **Client ID** and **Client Secret**.
5. If you want to read the user's email in the tool, go to **OAuth consent screen** and make sure `.../auth/userinfo.email` is in the scopes.

## Local setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and paste your Google credentials:
   ```bash
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   BASE_URL=http://localhost:8000
   ```
3. Install dependencies:
   ```bash
   uv sync
   ```

## Run the server

```bash
uv run server.py
```

The server starts on `http://localhost:8000` and serves:

- `/.well-known/oauth-authorization-server` — MCP OAuth discovery
- `/register` — Dynamic client registration bridge
- `/authorize` — Authorization endpoint
- `/token` — Token endpoint
- `/auth/callback` — OAuth callback (must match Google Cloud Console)
- `/mcp` — MCP message endpoint (protected)

## Test with an MCP client

Use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector uv run server.py
```

When you call the `sum` tool, the client will trigger a Google login. After authentication, the request reaches the tool and the server prints the authenticated user's Google ID and email.

## Integrate with CogSol

CogSol supports MCP servers that use **OAuth 2.1 with Dynamic Client Registration (DCR)**. Because `OIDCProxy` exposes a DCR-compliant interface, you can integrate this server by providing its public URL.

### Deploy the server

You need a publicly reachable HTTPS URL. Choose any host you prefer (Railway, Fly.io, Render, etc.).

1. Update `.env` for production:
   ```bash
   BASE_URL=https://your-domain.com
   GOOGLE_CLIENT_ID=your-production-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-production-client-secret
   ALLOWED_CLIENT_REDIRECT_URIS="https://*.cogsol.com/oauth/callback"
   ```
   Replace the redirect URI pattern with the exact callback CogSol uses.

2. In **Google Cloud Console**, add this authorized redirect URI:
   ```
   https://your-domain.com/auth/callback
   ```
   Only your server's callback is sent to Google; CogSol's own callback is forwarded by the proxy, so it does **not** need to be registered in Google Cloud Console.

3. Start the server on the production host.

### Add the server in CogSol

1. In CogSol, create a new MCP Tool.
2. Set the URL to:
   ```
   https://your-domain.com/mcp
   ```
3. Choose **Authentication → OAuth 2.1**.
4. **Leave Client ID, Client Secret, and Scopes blank**. CogSol will use Dynamic OAuth 2.1 and register itself automatically via `/register`.
5. Save and authenticate when prompted.

CogSol will discover auth metadata from `/.well-known/oauth-authorization-server`, complete the Google login on behalf of the agent, and call the `sum` tool with a Bearer token.

## Deploy to Prefect Horizon (managed hosting)

[Prefect Horizon](https://prefect.io/horizon) can host, scale, and secure this MCP server for you. It supports Google OAuth 2.1, TLS, and dynamic client registration out of the box.

The easiest integration is to let Horizon manage authentication:

1. Use `horizon_server.py` instead of `server.py`.
2. Add, commit, and push the repo to GitHub.
3. In Prefect Horizon, create a new project and set the entry point to:
   ```text
   horizon_server.py:mcp
   ```
4. In the Horizon dashboard, connect **Google OAuth** as the identity provider and add your Google Client ID / Secret.
5. Horizon will deploy the server and give you a URL like:
   ```text
   https://your-project.fastmcp.app/mcp
   ```
6. Use that URL in CogSol with Authentication set to **OAuth 2.1** and leave Client ID, Client Secret, and Scopes blank.

> **Note:** `horizon_server.py` intentionally contains no auth code, no `uvicorn.run()`, and no `if __name__ == "__main__":` block. Horizon manages the HTTP lifecycle directly.

## Important notes

- **Transport:** Authentication only works with HTTP or SSE transports, not STDIO.
- **Redirect URI:** The URI configured in Google Cloud Console must match `BASE_URL` + `/auth/callback` exactly.
- **DCR bridge:** Google does not support Dynamic Client Registration (DCR). `OIDCProxy` presents a DCR-compliant interface to MCP clients while using your fixed Google OAuth credentials upstream.
- **Security:** For production, provide an explicit `jwt_signing_key` and use a shared encrypted storage backend instead of the default disk store.
