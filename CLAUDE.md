# Google Tag Manager MCP Server

## What it is
MCP server enabling Claude to manage Google Tag Manager via GTM API v2.
Architecture mirrors MCP-SearchConsole: Starlette + SSE, Fernet token store, Google OAuth web flow, dry_run safety model, audit log.

## Architecture
- `server.py` — Starlette app + MCP over SSE + OAuth routes + dashboard
- `token_store.py` — Fernet-encrypted tokens per user_id (refresh_token + accounts + containers + active_container_path)
- `gtm_client.py` — GTM API v2 client (httpx, no SDK), handles token refresh + 50min cache
- `audit.py` — log every write operation to /tokens/audit.log
- `tools/accounts.py` — list_accounts, list_containers, get_container, discover_containers
- `tools/workspaces.py` — list/get/create/delete workspaces + workspace status
- `tools/tags.py` — CRUD tags
- `tools/triggers.py` — CRUD triggers
- `tools/variables.py` — CRUD variables
- `tools/builtins.py` — list/enable/disable built-in variables
- `tools/versions.py` — list version headers, get/live version, create + publish version

## Tool count
38 tools total

## Transport
SSE on /mcp. Railway deployment with volume /tokens.

## Auth — Google OAuth
Google issues refresh_token (never expires). Access token obtained on every request by exchanging refresh_token (cached 50 min in memory).

Flow:
1. `GET /auth/start?user_id=<email>` → redirect to Google consent
2. `GET /auth/callback?code=<code>&state=<user_id>` → exchange code → refresh_token → save
3. `GET /auth/discover?user_id=<user_id>` → fetch all GTM accounts+containers → save → set first as active → redirect /
4. `GET /auth/delete?user_id=<email>` → delete token → redirect /
5. `GET /auth/set-user?user_id=<email>` → set active user
6. `GET /auth/set-container?user_id=<email>&container_path=accounts/X/containers/Y` → set active container

## OAuth Scopes
- `tagmanager.edit.containers` — create/update/delete tags, triggers, variables, workspaces
- `tagmanager.edit.containerversions` — create container versions
- `tagmanager.publish` — publish versions to production
- `tagmanager.manage.accounts` — list accounts

## Safety model
ALL write operations have dry_run=True by default.
Every operation logged to /tokens/audit.log.

## GTM API Rate Limits
- 0.25 QPS per project (enforced by Google as 25 requests per 100 seconds)
- 10,000 requests per day
- For interactive Claude use, these limits won't be hit
- 429 responses are returned as {"error": "...", "code": 429}

## Known GTM API Quirks
- `autoEventFilter` field in click/form triggers is silently dropped by the API
  → configure click filter conditions manually in GTM UI after creating the trigger
- The `create_trigger` tool warns about this in dry_run preview

## GTM Path structure
- Account: accounts/{accountId}
- Container: accounts/{accountId}/containers/{containerId}
- Workspace: accounts/{accountId}/containers/{containerId}/workspaces/{workspaceId}
- Tag: ...workspaces/{id}/tags/{tagId}
- Trigger: ...workspaces/{id}/triggers/{triggerId}
- Variable: ...workspaces/{id}/variables/{variableId}

## Env vars (Railway)
- GOOGLE_OAUTH_CLIENT_ID
- GOOGLE_OAUTH_CLIENT_SECRET
- GOOGLE_OAUTH_REDIRECT_URI = https://<url>.railway.app/auth/callback
- TOKEN_ENCRYPTION_KEY (Fernet key)
- PORT=8000

## Google Cloud Console setup
1. Create OAuth 2.0 Client ID (Web Application)
2. Add Authorized redirect URI: https://your-app.railway.app/auth/callback
3. Enable "Tag Manager API" in API Library
4. Add test users in OAuth consent screen

## Accent color
#ff6d00 (orange) — used throughout dashboard
