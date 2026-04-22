"""
GTM Environments.

Environments let you test changes in staging before publishing to production.
Built-in environments: Live, Latest, Draft.
Custom environments can be created for staging/QA workflows.

Tools:
  list_environments    — list all environments for a container
  get_environment      — get environment details
  create_environment   — create custom environment (dry_run)
  update_environment   — update environment (dry_run)
  delete_environment   — delete environment (dry_run)
  reauthorize_environment — regenerate environment authorization token (dry_run)
"""
from typing import Any, Dict, Optional

from gtm_client import get_gtm_client
from audit import audit_log
from tools._helpers import resolve_container_path


def list_environments(container_path: Optional[str] = None,
                      user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{cp}/environments")
        if "error" in result:
            return result
        envs = result.get("environment", [])
        return {
            "container": cp,
            "count": len(envs),
            "environments": [
                {
                    "environmentId": e.get("environmentId"),
                    "name":          e.get("name"),
                    "type":          e.get("type"),
                    "url":           e.get("url"),
                    "enableDebug":   e.get("enableDebug", False),
                    "path":          e.get("path"),
                }
                for e in envs
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def get_environment(environment_id: str, container_path: Optional[str] = None,
                    user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{cp}/environments/{environment_id}")
        if "error" in result:
            return result
        return result
    except Exception as e:
        return {"error": str(e)}


def create_environment(name: str, url: Optional[str] = None, description: str = "",
                       enable_debug: bool = False, container_path: Optional[str] = None,
                       dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a custom environment. type is always 'user' for custom environments."""
    try:
        cp = resolve_container_path(container_path, user_id)
        body: Dict[str, Any] = {"name": name, "type": "user", "enableDebug": enable_debug}
        if url:
            body["url"] = url
        if description:
            body["description"] = description
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"container": cp, **body},
                "next_step": "Pass dry_run=False to create this environment.",
            }
        client = get_gtm_client(user_id)
        result = client.post(f"{cp}/environments", json_data=body)
        if "error" in result:
            return result
        audit_log("create_environment", cp, {"name": name}, user_id or "", dry_run)
        return {
            "environmentId": result.get("environmentId"),
            "name":          result.get("name"),
            "path":          result.get("path"),
            "created":       True,
        }
    except Exception as e:
        return {"error": str(e)}


def update_environment(environment_id: str, body: dict, container_path: Optional[str] = None,
                       dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Update a custom environment. body = GTM Environment resource."""
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{cp}/environments/{environment_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"environment_path": path, "body": body},
                "next_step": "Pass dry_run=False to update this environment.",
            }
        client = get_gtm_client(user_id)
        result = client.put(path, json_data=body)
        if "error" in result:
            return result
        audit_log("update_environment", cp, {"environment_id": environment_id}, user_id or "", dry_run)
        return {"environmentId": result.get("environmentId"), "name": result.get("name"), "updated": True}
    except Exception as e:
        return {"error": str(e)}


def delete_environment(environment_id: str, container_path: Optional[str] = None,
                       dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Delete a custom environment. Cannot delete built-in environments (Live, Latest, Draft)."""
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{cp}/environments/{environment_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"environment_path": path, "action": "delete"},
                "next_step": "Pass dry_run=False to delete this environment.",
            }
        client = get_gtm_client(user_id)
        result = client.delete(path)
        if "error" in result:
            return result
        audit_log("delete_environment", cp, {"environment_id": environment_id}, user_id or "", dry_run)
        return {"environment_id": environment_id, "deleted": True}
    except Exception as e:
        return {"error": str(e)}


def reauthorize_environment(environment_id: str, container_path: Optional[str] = None,
                             dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Regenerate the authorization token for a GTM environment."""
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{cp}/environments/{environment_id}:reauthorize"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"environment_id": environment_id, "action": "reauthorize"},
                "next_step": "Pass dry_run=False to regenerate the authorization token.",
            }
        client = get_gtm_client(user_id)
        result = client.post(path)
        if "error" in result:
            return result
        audit_log("reauthorize_environment", cp, {"environment_id": environment_id}, user_id or "", dry_run)
        return {
            "environmentId":    result.get("environmentId"),
            "authorizationCode": result.get("authorizationCode"),
            "reauthorized":     True,
        }
    except Exception as e:
        return {"error": str(e)}
