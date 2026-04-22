"""
Google Tag Manager MCP Server

Starlette + SSE transport, multi-user OAuth, Google Tag Manager API v2.
"""
import json
import logging
import os
import traceback
from urllib.parse import urlencode

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

import contextlib
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool

from gtm_client import get_active_user_id, set_active_user
from token_store import get_token_store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── OAuth config ───────────────────────────────────────────────────────────────
OAUTH_CLIENT_ID     = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
OAUTH_REDIRECT_URI  = os.environ.get(
    "GOOGLE_OAUTH_REDIRECT_URI",
    "https://mcp-gtm.up.railway.app/auth/callback",
)
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.edit.containerversions",
    "https://www.googleapis.com/auth/tagmanager.publish",
    "https://www.googleapis.com/auth/tagmanager.manage.accounts",
]
OAUTH_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"

# ── MCP server ─────────────────────────────────────────────────────────────────
server          = Server("gtm")
session_manager = StreamableHTTPSessionManager(app=server, stateless=True)

# ── Lazy tool imports ──────────────────────────────────────────────────────────
def _accounts():
    from tools import accounts; return accounts

def _workspaces():
    from tools import workspaces; return workspaces

def _tags():
    from tools import tags; return tags

def _triggers():
    from tools import triggers; return triggers

def _variables():
    from tools import variables; return variables

def _builtins():
    from tools import builtins; return builtins

def _versions():
    from tools import versions; return versions

# ── Tool schema helpers ────────────────────────────────────────────────────────
_STR  = {"type": "string"}
_INT  = {"type": "integer"}
_BOOL = {"type": "boolean"}
_OBJ  = {"type": "object"}
_ARR  = {"type": "array", "items": {"type": "string"}}

def _t(name, desc, props, required=None):
    return Tool(
        name=name,
        description=desc,
        inputSchema={
            "type": "object",
            "properties": props,
            **({"required": required} if required else {}),
        },
    )

_DR  = {"dry_run": {"type": "boolean", "default": True,
                    "description": "If True (default), preview only. Pass False to execute."}}
_UID = {"user_id": {"type": "string", "description": "User email (optional, uses active user)"}}
_CP  = {"container_path": {"type": "string",
                            "description": "Container path e.g. accounts/123/containers/456 (optional, uses active container)"}}
_WID = {"workspace_id": {"type": "string", "description": "Workspace ID (numeric string)"}}

ALL_TOOLS = [
    # ── Auth / user management ─────────────────────────────────────────────
    _t("list_users",           "List all authorized Google users and their GTM containers", {}),
    _t("get_active_user",      "Show the current active user and active container", {}),
    _t("set_active_user",      "Set the active user for all operations",
       {"user_id": _STR}, ["user_id"]),
    _t("set_active_container", "Set the active GTM container for a user",
       {"container_path": _STR, **_UID}, ["container_path"]),
    _t("authorize_user",       "Get the OAuth URL to authorize a new Google user",
       {"user_id": _STR}, ["user_id"]),
    _t("get_audit_log",        "View recent write operations log",
       {"lines": _INT}),

    # ── Accounts & Containers ──────────────────────────────────────────────
    _t("list_accounts",      "List all GTM accounts accessible to the user", {**_UID}),
    _t("list_containers",    "List containers in a GTM account",
       {"account_path": _STR, **_UID}, ["account_path"]),
    _t("get_container",      "Get details for a specific container",
       {"container_path": _STR, **_UID}, ["container_path"]),
    _t("discover_containers", "Fetch all GTM accounts and containers, save to store, set first as active",
       {**_UID}),

    # ── Workspaces ─────────────────────────────────────────────────────────
    _t("list_workspaces",      "List workspaces in the active (or specified) container",
       {**_CP, **_UID}),
    _t("get_workspace",        "Get workspace details",
       {**_WID, **_CP, **_UID}, ["workspace_id"]),
    _t("create_workspace",     "Create a new workspace. dry_run=True by default.",
       {"name": _STR, "description": _STR, **_CP, **_DR, **_UID}, ["name"]),
    _t("delete_workspace",     "Delete workspace and all unpublished changes. dry_run=True by default.",
       {**_WID, **_CP, **_DR, **_UID}, ["workspace_id"]),
    _t("get_workspace_status", "List all pending (uncommitted) changes in a workspace",
       {**_WID, **_CP, **_UID}, ["workspace_id"]),

    # ── Tags ───────────────────────────────────────────────────────────────
    _t("list_tags",   "List all tags in a workspace",
       {**_WID, **_CP, **_UID}, ["workspace_id"]),
    _t("get_tag",     "Get full tag details including parameters",
       {"tag_id": _STR, **_WID, **_CP, **_UID}, ["workspace_id", "tag_id"]),
    _t("create_tag",  "Create a tag. body = GTM Tag resource JSON. dry_run=True by default.",
       {"body": _OBJ, **_WID, **_CP, **_DR, **_UID}, ["workspace_id", "body"]),
    _t("update_tag",  "Update a tag (full replacement). dry_run=True by default.",
       {"tag_id": _STR, "body": _OBJ, "fingerprint": _STR, **_WID, **_CP, **_DR, **_UID},
       ["workspace_id", "tag_id", "body"]),
    _t("delete_tag",  "Delete a tag. dry_run=True by default.",
       {"tag_id": _STR, **_WID, **_CP, **_DR, **_UID}, ["workspace_id", "tag_id"]),

    # ── Triggers ───────────────────────────────────────────────────────────
    _t("list_triggers",   "List all triggers in a workspace",
       {**_WID, **_CP, **_UID}, ["workspace_id"]),
    _t("get_trigger",     "Get full trigger details",
       {"trigger_id": _STR, **_WID, **_CP, **_UID}, ["workspace_id", "trigger_id"]),
    _t("create_trigger",  "Create a trigger. body = GTM Trigger resource JSON. dry_run=True by default.",
       {"body": _OBJ, **_WID, **_CP, **_DR, **_UID}, ["workspace_id", "body"]),
    _t("update_trigger",  "Update a trigger (full replacement). dry_run=True by default.",
       {"trigger_id": _STR, "body": _OBJ, **_WID, **_CP, **_DR, **_UID},
       ["workspace_id", "trigger_id", "body"]),
    _t("delete_trigger",  "Delete a trigger. dry_run=True by default.",
       {"trigger_id": _STR, **_WID, **_CP, **_DR, **_UID}, ["workspace_id", "trigger_id"]),

    # ── Variables ──────────────────────────────────────────────────────────
    _t("list_variables",   "List all custom variables in a workspace",
       {**_WID, **_CP, **_UID}, ["workspace_id"]),
    _t("get_variable",     "Get full variable details",
       {"variable_id": _STR, **_WID, **_CP, **_UID}, ["workspace_id", "variable_id"]),
    _t("create_variable",  "Create a variable. body = GTM Variable resource JSON. dry_run=True by default.",
       {"body": _OBJ, **_WID, **_CP, **_DR, **_UID}, ["workspace_id", "body"]),
    _t("update_variable",  "Update a variable (full replacement). dry_run=True by default.",
       {"variable_id": _STR, "body": _OBJ, **_WID, **_CP, **_DR, **_UID},
       ["workspace_id", "variable_id", "body"]),
    _t("delete_variable",  "Delete a variable. dry_run=True by default.",
       {"variable_id": _STR, **_WID, **_CP, **_DR, **_UID}, ["workspace_id", "variable_id"]),

    # ── Built-in Variables ─────────────────────────────────────────────────
    _t("list_builtin_variables",    "List all enabled built-in variables in a workspace",
       {**_WID, **_CP, **_UID}, ["workspace_id"]),
    _t("enable_builtin_variables",  "Enable built-in variables. types = list of type strings. dry_run=True by default.",
       {"types": {"type": "array", "items": {"type": "string"}}, **_WID, **_CP, **_DR, **_UID},
       ["workspace_id", "types"]),
    _t("disable_builtin_variables", "Disable built-in variables. types = list of type strings. dry_run=True by default.",
       {"types": {"type": "array", "items": {"type": "string"}}, **_WID, **_CP, **_DR, **_UID},
       ["workspace_id", "types"]),

    # ── Versions ───────────────────────────────────────────────────────────
    _t("list_version_headers", "List version summaries for a container",
       {**_CP, **_UID}),
    _t("get_version",          "Get full version details (all tags, triggers, variables)",
       {"version_id": _STR, **_CP, **_UID}, ["version_id"]),
    _t("get_live_version",     "Get the currently published (live) container version",
       {**_CP, **_UID}),
    _t("create_version",       "Create a version snapshot from a workspace. dry_run=True by default.",
       {"name": _STR, "notes": _STR, **_WID, **_CP, **_DR, **_UID}, ["workspace_id", "name"]),
    _t("publish_version",      "Publish a version to production (LIVE). dry_run=True by default. WARNING: immediately affects live container.",
       {"version_id": _STR, "fingerprint": _STR, **_CP, **_DR, **_UID}, ["version_id"]),
]


# ── Tool handlers ──────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools():
    return ALL_TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    a = arguments or {}

    def _a(key, default=None):
        return a.get(key, default)

    try:
        result = await _dispatch(name, a)
    except Exception as e:
        logger.error("Tool %s error: %s\n%s", name, e, traceback.format_exc())
        result = {"error": str(e)}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def _dispatch(name: str, a: dict):
    uid = a.get("user_id")
    cp  = a.get("container_path")
    dr  = a.get("dry_run", True)
    wid = a.get("workspace_id")

    # ── Auth / user management ─────────────────────────────────────────────
    if name == "list_users":
        ts = get_token_store()
        users = ts.list_users()
        result = []
        for u in users:
            info = ts.get_user_info(u)
            result.append({
                "user_id":               u,
                "has_token":             info["has_token"],
                "active_container_path": info["active_container_path"],
                "containers":            len(info["containers"]),
            })
        return {"users": result, "count": len(result)}

    if name == "get_active_user":
        try:
            active = get_active_user_id()
            ts = get_token_store()
            cp_active = ts.get_active_container(active)
            return {
                "active_user":       active,
                "active_container":  cp_active,
                "containers":        len(ts.get_containers(active)),
            }
        except ValueError as e:
            return {"error": str(e)}

    if name == "set_active_user":
        set_active_user(a["user_id"])
        return {"active_user": a["user_id"]}

    if name == "set_active_container":
        uid_eff = uid or get_active_user_id()
        get_token_store().set_active_container(uid_eff, a["container_path"])
        return {"active_container": a["container_path"], "user": uid_eff}

    if name == "authorize_user":
        base = OAUTH_REDIRECT_URI.replace("/auth/callback", "")
        return {"auth_url": f"{base}/auth/start?user_id={a['user_id']}"}

    if name == "get_audit_log":
        from audit import read_audit_log
        return {"entries": read_audit_log(a.get("lines", 50))}

    # ── Accounts & Containers ──────────────────────────────────────────────
    if name == "list_accounts":
        return _accounts().list_accounts(uid)

    if name == "list_containers":
        return _accounts().list_containers(a["account_path"], uid)

    if name == "get_container":
        return _accounts().get_container(a["container_path"], uid)

    if name == "discover_containers":
        result = _accounts().discover_containers(uid)
        if "error" not in result and uid:
            set_active_user(uid)
        elif "error" not in result:
            try:
                set_active_user(get_active_user_id())
            except Exception:
                pass
        return result

    # ── Workspaces ─────────────────────────────────────────────────────────
    if name == "list_workspaces":
        return _workspaces().list_workspaces(cp, uid)

    if name == "get_workspace":
        return _workspaces().get_workspace(wid, cp, uid)

    if name == "create_workspace":
        return _workspaces().create_workspace(a["name"], a.get("description", ""), cp, dr, uid)

    if name == "delete_workspace":
        return _workspaces().delete_workspace(wid, cp, dr, uid)

    if name == "get_workspace_status":
        return _workspaces().get_workspace_status(wid, cp, uid)

    # ── Tags ───────────────────────────────────────────────────────────────
    if name == "list_tags":
        return _tags().list_tags(wid, cp, uid)

    if name == "get_tag":
        return _tags().get_tag(wid, a["tag_id"], cp, uid)

    if name == "create_tag":
        return _tags().create_tag(wid, a["body"], cp, dr, uid)

    if name == "update_tag":
        return _tags().update_tag(wid, a["tag_id"], a["body"], cp, a.get("fingerprint"), dr, uid)

    if name == "delete_tag":
        return _tags().delete_tag(wid, a["tag_id"], cp, dr, uid)

    # ── Triggers ───────────────────────────────────────────────────────────
    if name == "list_triggers":
        return _triggers().list_triggers(wid, cp, uid)

    if name == "get_trigger":
        return _triggers().get_trigger(wid, a["trigger_id"], cp, uid)

    if name == "create_trigger":
        return _triggers().create_trigger(wid, a["body"], cp, dr, uid)

    if name == "update_trigger":
        return _triggers().update_trigger(wid, a["trigger_id"], a["body"], cp, dr, uid)

    if name == "delete_trigger":
        return _triggers().delete_trigger(wid, a["trigger_id"], cp, dr, uid)

    # ── Variables ──────────────────────────────────────────────────────────
    if name == "list_variables":
        return _variables().list_variables(wid, cp, uid)

    if name == "get_variable":
        return _variables().get_variable(wid, a["variable_id"], cp, uid)

    if name == "create_variable":
        return _variables().create_variable(wid, a["body"], cp, dr, uid)

    if name == "update_variable":
        return _variables().update_variable(wid, a["variable_id"], a["body"], cp, dr, uid)

    if name == "delete_variable":
        return _variables().delete_variable(wid, a["variable_id"], cp, dr, uid)

    # ── Built-in Variables ─────────────────────────────────────────────────
    if name == "list_builtin_variables":
        return _builtins().list_builtin_variables(wid, cp, uid)

    if name == "enable_builtin_variables":
        return _builtins().enable_builtin_variables(wid, a["types"], cp, dr, uid)

    if name == "disable_builtin_variables":
        return _builtins().disable_builtin_variables(wid, a["types"], cp, dr, uid)

    # ── Versions ───────────────────────────────────────────────────────────
    if name == "list_version_headers":
        return _versions().list_version_headers(cp, uid)

    if name == "get_version":
        return _versions().get_version(a["version_id"], cp, uid)

    if name == "get_live_version":
        return _versions().get_live_version(cp, uid)

    if name == "create_version":
        return _versions().create_version(wid, a["name"], a.get("notes", ""), cp, dr, uid)

    if name == "publish_version":
        return _versions().publish_version(a["version_id"], cp, a.get("fingerprint"), dr, uid)

    return {"error": f"Unknown tool: {name}"}


# ── OAuth routes ───────────────────────────────────────────────────────────────

async def auth_start(request):
    user_id = request.query_params.get("user_id", "")
    if not user_id:
        return HTMLResponse("<h1>Error</h1><p>user_id parameter required.</p>", status_code=400)
    if not OAUTH_CLIENT_ID:
        return JSONResponse({"error": "OAuth not configured — set GOOGLE_OAUTH_CLIENT_ID"}, status_code=500)
    params = {
        "client_id":     OAUTH_CLIENT_ID,
        "redirect_uri":  OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope":         " ".join(OAUTH_SCOPES),
        "access_type":   "offline",
        "prompt":        "select_account consent",
        "state":         user_id.strip(),
    }
    return RedirectResponse(url=f"{OAUTH_AUTH_URL}?{urlencode(params)}")


async def auth_callback(request):
    code  = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        return HTMLResponse(f"<h1>OAuth Error: {error}</h1>")
    if not code or not state:
        return JSONResponse({"error": "Missing code or state"}, status_code=400)

    user_id = state
    async with httpx.AsyncClient() as client:
        resp = await client.post(OAUTH_TOKEN_URL, data={
            "client_id":     OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "redirect_uri":  OAUTH_REDIRECT_URI,
            "code":          code,
            "grant_type":    "authorization_code",
        }, timeout=30)

    if resp.status_code != 200:
        return HTMLResponse(f"<h1>Token exchange failed</h1><p>{resp.text}</p>", status_code=500)

    body = resp.json()
    refresh_token = body.get("refresh_token")
    if not refresh_token:
        return HTMLResponse(
            "<h1>No refresh_token received</h1>"
            "<p>Make sure OAuth consent screen has offline access and prompt=consent.</p>",
            status_code=500
        )

    get_token_store().save_token(user_id, refresh_token)
    return RedirectResponse(url=f"/auth/discover?user_id={user_id}")


async def auth_discover(request):
    """After OAuth: auto-discover GTM accounts+containers, save, redirect to dashboard."""
    user_id = request.query_params.get("user_id")
    if not user_id:
        return RedirectResponse(url="/")
    try:
        from tools.accounts import discover_containers
        result = discover_containers(user_id)
        if "error" not in result:
            set_active_user(user_id)
            logger.info("Discovered %d containers for %s", result.get("containers", 0), user_id)
        else:
            logger.error("discover_containers error: %s", result["error"])
    except Exception as e:
        logger.error("auth_discover error: %s", e)
    return RedirectResponse(url="/")


async def auth_delete(request):
    user_id = request.query_params.get("user_id")
    if not user_id:
        return JSONResponse({"error": "user_id required"}, status_code=400)
    get_token_store().delete_token(user_id)
    return RedirectResponse(url="/")


async def set_user_api(request):
    user_id = request.query_params.get("user_id")
    if not user_id:
        return JSONResponse({"error": "user_id required"}, status_code=400)
    set_active_user(user_id)
    return RedirectResponse(url="/")


async def set_container_api(request):
    user_id        = request.query_params.get("user_id")
    container_path = request.query_params.get("container_path")
    if not user_id or not container_path:
        return JSONResponse({"error": "user_id and container_path required"}, status_code=400)
    get_token_store().set_active_container(user_id, container_path)
    return RedirectResponse(url="/")


# ── Logo ───────────────────────────────────────────────────────────────────────

async def logo(request):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return Response(f.read(), media_type="image/png")
    return Response(status_code=404)


# ── Health ─────────────────────────────────────────────────────────────────────

async def health(request):
    return JSONResponse({"status": "ok", "server": "gtm", "tools": len(ALL_TOOLS)})


# ── Dashboard ──────────────────────────────────────────────────────────────────

async def homepage(request):
    return HTMLResponse(_build_dashboard())


def _build_dashboard() -> str:
    ts    = get_token_store()
    users = ts.list_users()

    def pill(label, color, bg, border):
        return (f'<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 9px;'
                f'background:{bg};border:1px solid {border};border-radius:20px;'
                f'font-size:11px;font-weight:600;color:{color}">{label}</span>')

    cards = ""
    for uid in users:
        containers = ts.get_containers(uid)
        active_cp  = ts.get_active_container(uid)

        container_rows_html = ""
        for c in containers:
            c_path    = c.get("path", "")
            c_name    = c.get("name", c_path)
            c_pub_id  = c.get("publicId", "")
            is_active = c_path == active_cp
            row_style = (f'border-left:3px solid #ff6d00;background:rgba(255,109,0,.04)'
                         if is_active else 'border-left:3px solid transparent')
            active_badge = f'&nbsp;{pill("active","#ff6d00","rgba(255,109,0,.1)","rgba(255,109,0,.3)")}' if is_active else ''
            container_rows_html += (
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:9px 16px;{row_style}">'
                f'<div style="display:flex;align-items:center;gap:10px;min-width:0">'
                f'<span style="font-family:monospace;font-size:11px;color:#7878a8;white-space:nowrap">{c_pub_id}</span>'
                f'<span style="font-size:13px;color:#d0d0ec">{c_name}</span>'
                f'{active_badge}'
                f'</div>'
                f'<a href="/auth/set-container?user_id={uid}&container_path={c_path}" '
                f'style="font-size:11px;color:#505080;text-decoration:none;flex-shrink:0;margin-left:12px">Set active</a>'
                f'</div>'
            )

        if container_rows_html:
            containers_block = (
                f'<div style="margin-top:14px;border-top:1px solid rgba(255,255,255,.07);padding-top:4px">'
                f'<div style="padding:6px 16px 2px;font-size:10px;font-weight:700;color:#505078;'
                f'text-transform:uppercase;letter-spacing:.08em">Containers ({len(containers)})</div>'
                f'{container_rows_html}'
                f'<div style="padding:8px 16px">'
                f'<a href="/auth/discover?user_id={uid}" style="font-size:12px;color:#505080;text-decoration:none">↻ Refresh containers</a>'
                f'</div></div>'
            )
        elif ts.get_token(uid):
            containers_block = (
                f'<div style="margin-top:12px;border-top:1px solid rgba(255,255,255,.07);'
                f'padding-top:12px;padding-left:16px;padding-bottom:4px">'
                f'<a href="/auth/discover?user_id={uid}" style="color:#ff6d00;font-size:13px">↻ Discover containers</a></div>'
            )
        else:
            containers_block = ""

        cards += (
            f'<div style="background:#12121e;border:1px solid rgba(255,109,0,.2);border-radius:12px;'
            f'margin-bottom:12px;overflow:hidden">'
            f'<div style="padding:18px 20px;display:flex;justify-content:space-between;'
            f'align-items:flex-start;flex-wrap:wrap;gap:8px">'
            f'<div>'
            f'<span style="font-size:15px;font-weight:700;color:#e8e8f4">{uid}</span>'
            f'<div style="margin-top:4px;font-size:12px;color:#606090">'
            f'{len(containers)} {"container" if len(containers)==1 else "containers"}'
            f'</div></div>'
            f'<div style="display:flex;align-items:center;gap:6px">'
            f'<a href="/auth/start?user_id={uid}" style="color:#7878a8;font-size:13px;text-decoration:none">Re-auth</a>'
            f'<span style="color:#303050">&nbsp;·&nbsp;</span>'
            f'<a href="/auth/delete?user_id={uid}" style="color:#ff4d5e;font-size:13px;text-decoration:none"'
            f' onclick="return confirm(\'Delete token for {uid}?\')">Delete</a>'
            f'</div></div>'
            f'{containers_block}</div>'
        )

    if not users:
        cards = '<p style="color:#606090;font-size:14px">No users authorized yet.</p>'

    total_containers = sum(len(ts.get_containers(u)) for u in users)
    tool_count = len(ALL_TOOLS)

    return f"""<!DOCTYPE html>
<html><head><title>GTM MCP</title>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#09090f;color:#e8e8f4;min-height:100vh}}
.wrap{{max-width:900px;margin:0 auto;padding:40px 24px}}
.logo-bar{{margin-bottom:32px;display:flex;align-items:center;gap:16px;padding-bottom:24px;border-bottom:1px solid rgba(255,109,0,.12)}}
.logo-bar img{{height:42px;border-radius:10px}}
.subtitle{{color:#ff6d00;font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}}
.card{{background:#12121a;border:1px solid rgba(255,109,0,.15);border-radius:12px;padding:24px;margin-bottom:14px}}
.sec{{font-size:11px;font-weight:700;color:#505080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:16px}}
.stats{{display:flex;gap:14px;margin-bottom:20px;flex-wrap:wrap}}
.stat{{background:#0e0e1a;border:1px solid rgba(255,109,0,.1);border-radius:8px;padding:12px 18px;flex:1;min-width:80px}}
.stat-val{{font-size:22px;font-weight:700;color:#ff6d00}}
.stat-lbl{{font-size:11px;color:#505080;margin-top:2px;text-transform:uppercase;letter-spacing:.06em}}
.form-row{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
input[type=text]{{padding:10px 14px;background:#0e0e18;border:1px solid rgba(255,109,0,.3);border-radius:7px;color:#e8e8f4;font-size:14px;width:100%;max-width:280px}}
input[type=text]:focus{{outline:none;border-color:#ff6d00}}
input[type=text]::placeholder{{color:#404060}}
.btn{{display:inline-block;padding:10px 22px;background:linear-gradient(135deg,#c43e00,#ff6d00);color:white;text-decoration:none;border-radius:7px;border:none;cursor:pointer;font-size:14px;font-weight:600;white-space:nowrap}}
.footer{{margin-top:20px;display:flex;gap:20px;flex-wrap:wrap}}
.footer a{{color:#505080;font-size:13px;text-decoration:none}}
.footer a:hover{{color:#ff6d00}}
@media(max-width:600px){{
  .wrap{{padding:20px 14px}}
  .stats{{gap:10px}}
  .stat{{padding:10px 12px}}
  .stat-val{{font-size:18px}}
  .form-row{{flex-direction:column;align-items:stretch}}
  input[type=text]{{max-width:100%}}
  .logo-bar img{{height:34px}}
}}
</style>
</head><body>
<div class="wrap">
  <div class="logo-bar">
    <img src="/logo.png" alt="Marketing Hackers">
    <div>
      <div style="font-size:18px;font-weight:700;color:#e8e8f4">GTM MCP</div>
      <div class="subtitle">Google Tag Manager API v2</div>
    </div>
  </div>

  <div class="stats">
    <div class="stat"><div class="stat-val">{tool_count}</div><div class="stat-lbl">Tools</div></div>
    <div class="stat"><div class="stat-val">{len(users)}</div><div class="stat-lbl">Users</div></div>
    <div class="stat"><div class="stat-val">{total_containers}</div><div class="stat-lbl">Containers</div></div>
    <div class="stat"><div class="stat-val">v2</div><div class="stat-lbl">API</div></div>
  </div>

  <div class="card">
    <div class="sec">Authorized Users &amp; Containers</div>
    {cards}
  </div>

  <div class="card">
    <div class="sec">Add User</div>
    <form action="/auth/start" method="get" class="form-row">
      <input type="text" name="user_id" placeholder="your@email.com" required>
      <button type="submit" class="btn">Authorize with Google</button>
    </form>
  </div>

  <div class="footer">
    <a href="/health">Health</a>
  </div>
</div>
</body></html>"""


# ── SSE / App ──────────────────────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def lifespan(app):
    async with session_manager.run():
        yield


_starlette_app = Starlette(
    routes=[
        Route("/",                      endpoint=homepage),
        Route("/logo.png",              endpoint=logo),
        Route("/health",                endpoint=health),
        Route("/auth/start",            endpoint=auth_start),
        Route("/auth/callback",         endpoint=auth_callback),
        Route("/auth/discover",         endpoint=auth_discover),
        Route("/auth/delete",           endpoint=auth_delete),
        Route("/auth/set-user",         endpoint=set_user_api),
        Route("/auth/set-container",    endpoint=set_container_api),
    ],
    lifespan=lifespan,
)
_starlette_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


async def app(scope, receive, send):
    """Top-level ASGI: /mcp → session_manager, rest → Starlette."""
    if scope["type"] == "http" and scope.get("path", "").rstrip("/") == "/mcp":
        await session_manager.handle_request(scope, receive, send)
        return
    await _starlette_app(scope, receive, send)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
