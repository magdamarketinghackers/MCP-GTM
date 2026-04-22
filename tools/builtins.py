"""
GTM Built-in Variables.

Tools:
  list_builtin_variables    — list enabled built-in variables in workspace
  enable_builtin_variables  — enable one or more built-in variables (dry_run)
  disable_builtin_variables — disable one or more built-in variables (dry_run)

Common built-in variable types:
  pageUrl, pageHostname, pagePath, referrer
  event, environmentName, containerId, containerVersion, htmlId
  clickElement, clickClasses, clickId, clickTarget, clickUrl, clickText
  formElement, formClasses, formId, formTarget, formUrl, formText
  errorMessage, errorUrl, errorLine, debugMode
  scrollDepthThreshold, scrollDepthUnits, scrollDepthDirection
  videoProvider, videoUrl, videoTitle, videoStatus, videoDuration,
  videoCurrentTime, videoPercent, videoVisible
"""
from typing import Any, Dict, List, Optional

from gtm_client import get_gtm_client
from audit import audit_log
from tools._helpers import resolve_container_path, workspace_path


def _builtins_path(cp: str, workspace_id: str) -> str:
    return f"{workspace_path(cp, workspace_id)}/built_in_variables"


def list_builtin_variables(workspace_id: str, container_path: Optional[str] = None,
                           user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(_builtins_path(cp, workspace_id))
        if "error" in result:
            return result
        builtins = result.get("builtInVariable", [])
        return {
            "workspace": workspace_path(cp, workspace_id),
            "count": len(builtins),
            "builtin_variables": [
                {"type": b.get("type"), "name": b.get("name")}
                for b in builtins
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def enable_builtin_variables(workspace_id: str, types: List[str],
                              container_path: Optional[str] = None,
                              dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Enable one or more built-in variables. types = list of type strings, e.g. ['clickElement', 'clickClasses']."""
    try:
        cp = resolve_container_path(container_path, user_id)
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"workspace": workspace_path(cp, workspace_id), "types": types},
                "next_step": "Pass dry_run=False to enable these built-in variables.",
            }
        client = get_gtm_client(user_id)
        # GTM API: POST with type query params (repeatable)
        params = [("type", t) for t in types]
        # httpx accepts list of tuples for repeatable params
        url_path = _builtins_path(cp, workspace_id)
        result = client.post(url_path, params=params)
        if "error" in result:
            return result
        audit_log("enable_builtin_variables", cp, {"types": types}, user_id or "", dry_run)
        enabled = result.get("builtInVariable", [])
        return {
            "enabled": [b.get("type") for b in enabled],
            "count": len(enabled),
        }
    except Exception as e:
        return {"error": str(e)}


def disable_builtin_variables(workspace_id: str, types: List[str],
                               container_path: Optional[str] = None,
                               dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Disable one or more built-in variables. types = list of type strings."""
    try:
        cp = resolve_container_path(container_path, user_id)
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"workspace": workspace_path(cp, workspace_id), "types": types},
                "next_step": "Pass dry_run=False to disable these built-in variables.",
            }
        client = get_gtm_client(user_id)
        params = [("type", t) for t in types]
        result = client.delete(_builtins_path(cp, workspace_id), params=params)
        if "error" in result:
            return result
        audit_log("disable_builtin_variables", cp, {"types": types}, user_id or "", dry_run)
        return {"disabled": types, "count": len(types)}
    except Exception as e:
        return {"error": str(e)}
