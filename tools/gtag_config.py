"""
GTM Google Tag (gtag) Configuration.

gtag_config represents the configuration for Google Tags (GA4, Google Ads, etc.)
within a GTM server-side or web container's workspace.

Tools:
  list_gtag_configs   — list gtag configurations in a workspace
  get_gtag_config     — get gtag config details
  create_gtag_config  — create gtag config (dry_run)
  update_gtag_config  — update gtag config (dry_run)
  delete_gtag_config  — delete gtag config (dry_run)
"""
from typing import Any, Dict, Optional

from gtm_client import get_gtm_client
from audit import audit_log
from tools._helpers import resolve_container_path, workspace_path


def _gtag_path(cp: str, workspace_id: str) -> str:
    return f"{workspace_path(cp, workspace_id)}/gtag_config"


def list_gtag_configs(workspace_id: str, container_path: Optional[str] = None,
                      user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(_gtag_path(cp, workspace_id))
        if "error" in result:
            return result
        configs = result.get("gtagConfig", [])
        return {
            "workspace": workspace_path(cp, workspace_id),
            "count": len(configs),
            "gtag_configs": [
                {
                    "gtagConfigId": c.get("gtagConfigId"),
                    "type":         c.get("type"),
                    "path":         c.get("path"),
                }
                for c in configs
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def get_gtag_config(workspace_id: str, gtag_config_id: str, container_path: Optional[str] = None,
                    user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{_gtag_path(cp, workspace_id)}/{gtag_config_id}")
        if "error" in result:
            return result
        return result
    except Exception as e:
        return {"error": str(e)}


def create_gtag_config(workspace_id: str, body: dict, container_path: Optional[str] = None,
                       dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a Google Tag configuration. body must include type and parameter."""
    try:
        cp = resolve_container_path(container_path, user_id)
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"workspace": workspace_path(cp, workspace_id), "body": body},
                "next_step": "Pass dry_run=False to create this gtag configuration.",
            }
        client = get_gtm_client(user_id)
        result = client.post(_gtag_path(cp, workspace_id), json_data=body)
        if "error" in result:
            return result
        audit_log("create_gtag_config", cp, {"type": body.get("type")}, user_id or "", dry_run)
        return {"gtagConfigId": result.get("gtagConfigId"), "type": result.get("type"),
                "path": result.get("path"), "created": True}
    except Exception as e:
        return {"error": str(e)}


def update_gtag_config(workspace_id: str, gtag_config_id: str, body: dict,
                       container_path: Optional[str] = None, dry_run: bool = True,
                       user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_gtag_path(cp, workspace_id)}/{gtag_config_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"gtag_config_path": path, "body": body},
                "next_step": "Pass dry_run=False to update this gtag configuration.",
            }
        client = get_gtm_client(user_id)
        result = client.put(path, json_data=body)
        if "error" in result:
            return result
        audit_log("update_gtag_config", cp, {"gtag_config_id": gtag_config_id}, user_id or "", dry_run)
        return {"gtagConfigId": result.get("gtagConfigId"), "updated": True}
    except Exception as e:
        return {"error": str(e)}


def delete_gtag_config(workspace_id: str, gtag_config_id: str, container_path: Optional[str] = None,
                       dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_gtag_path(cp, workspace_id)}/{gtag_config_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"gtag_config_path": path, "action": "delete"},
                "next_step": "Pass dry_run=False to delete this gtag configuration.",
            }
        client = get_gtm_client(user_id)
        result = client.delete(path)
        if "error" in result:
            return result
        audit_log("delete_gtag_config", cp, {"gtag_config_id": gtag_config_id}, user_id or "", dry_run)
        return {"gtag_config_id": gtag_config_id, "deleted": True}
    except Exception as e:
        return {"error": str(e)}
