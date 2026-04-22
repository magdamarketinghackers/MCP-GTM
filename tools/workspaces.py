"""
GTM Workspaces.

Tools:
  list_workspaces      — list workspaces in a container
  get_workspace        — get workspace details
  create_workspace     — create new workspace (dry_run)
  delete_workspace     — delete workspace (dry_run)
  get_workspace_status — list pending changes in workspace
"""
from typing import Any, Dict, Optional

from gtm_client import get_gtm_client
from audit import audit_log
from tools._helpers import resolve_container_path, workspace_path


def list_workspaces(container_path: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{cp}/workspaces")
        if "error" in result:
            return result
        workspaces = result.get("workspace", [])
        return {
            "container_path": cp,
            "count": len(workspaces),
            "workspaces": [
                {
                    "path":        w.get("path"),
                    "workspaceId": w.get("workspaceId"),
                    "name":        w.get("name"),
                    "description": w.get("description", ""),
                    "fingerprint": w.get("fingerprint"),
                    "tagManagerUrl": w.get("tagManagerUrl"),
                }
                for w in workspaces
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def get_workspace(workspace_id: str, container_path: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        wp = workspace_path(cp, workspace_id)
        client = get_gtm_client(user_id)
        result = client.get(wp)
        if "error" in result:
            return result
        return {
            "path":        result.get("path"),
            "workspaceId": result.get("workspaceId"),
            "name":        result.get("name"),
            "description": result.get("description", ""),
            "fingerprint": result.get("fingerprint"),
            "tagManagerUrl": result.get("tagManagerUrl"),
        }
    except Exception as e:
        return {"error": str(e)}


def create_workspace(name: str, description: str = "", container_path: Optional[str] = None,
                     dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"name": name, "description": description, "container": cp},
                "next_step": "Pass dry_run=False to create this workspace.",
            }
        client = get_gtm_client(user_id)
        result = client.post(f"{cp}/workspaces", json_data={"name": name, "description": description})
        if "error" in result:
            return result
        audit_log("create_workspace", cp, {"name": name}, user_id or "", dry_run)
        return {
            "path":        result.get("path"),
            "workspaceId": result.get("workspaceId"),
            "name":        result.get("name"),
            "created":     True,
        }
    except Exception as e:
        return {"error": str(e)}


def delete_workspace(workspace_id: str, container_path: Optional[str] = None,
                     dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        wp = workspace_path(cp, workspace_id)
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"workspace_path": wp, "action": "delete"},
                "next_step": "Pass dry_run=False to delete this workspace and all its unpublished changes.",
            }
        client = get_gtm_client(user_id)
        result = client.delete(wp)
        if "error" in result:
            return result
        audit_log("delete_workspace", cp, {"workspace_id": workspace_id}, user_id or "", dry_run)
        return {"workspace_path": wp, "deleted": True}
    except Exception as e:
        return {"error": str(e)}


def get_workspace_status(workspace_id: str, container_path: Optional[str] = None,
                         user_id: Optional[str] = None) -> Dict[str, Any]:
    """Return list of entities changed in this workspace (pending changes)."""
    try:
        cp = resolve_container_path(container_path, user_id)
        wp = workspace_path(cp, workspace_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{wp}/status")
        if "error" in result:
            return result
        entities = result.get("workspaceChange", [])
        return {
            "workspace_path": wp,
            "pending_changes": len(entities),
            "changes": [
                {
                    "type":           e.get("type"),
                    "changeStatus":   e.get("changeStatus"),
                    "tag":            e.get("tag", {}).get("name") if e.get("tag") else None,
                    "trigger":        e.get("trigger", {}).get("name") if e.get("trigger") else None,
                    "variable":       e.get("variable", {}).get("name") if e.get("variable") else None,
                }
                for e in entities
            ],
        }
    except Exception as e:
        return {"error": str(e)}
