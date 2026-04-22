"""
GTM Container Versions.

GTM version workflow:
  1. Make changes in a workspace (add/update tags, triggers, variables)
  2. create_version  — snapshot workspace → container version (not yet live)
  3. publish_version — push version to production (dry_run=True by default)

Tools:
  list_version_headers — list version summaries for container
  get_version          — get full version details (all tags/triggers/variables)
  get_live_version     — get the currently published version
  create_version       — create version from workspace snapshot (dry_run)
  publish_version      — publish a version to production (dry_run)
"""
from typing import Any, Dict, Optional

from gtm_client import get_gtm_client
from audit import audit_log
from tools._helpers import resolve_container_path, workspace_path


def list_version_headers(container_path: Optional[str] = None,
                          user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{cp}/version_headers")
        if "error" in result:
            return result
        headers = result.get("containerVersionHeader", [])
        return {
            "container": cp,
            "count": len(headers),
            "versions": [
                {
                    "containerVersionId": h.get("containerVersionId"),
                    "name":              h.get("name"),
                    "description":       h.get("description", ""),
                    "deleted":           h.get("deleted", False),
                    "numTags":           h.get("numTags"),
                    "numTriggers":       h.get("numTriggers"),
                    "numVariables":      h.get("numVariables"),
                    "path":              h.get("path"),
                }
                for h in headers
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def get_version(version_id: str, container_path: Optional[str] = None,
                user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get full version details including all tags, triggers, variables."""
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{cp}/versions/{version_id}")
        if "error" in result:
            return result
        cv = result.get("containerVersion", result)
        return {
            "containerVersionId": cv.get("containerVersionId"),
            "name":               cv.get("name"),
            "description":        cv.get("description", ""),
            "path":               cv.get("path"),
            "tag_count":          len(cv.get("tag", [])),
            "trigger_count":      len(cv.get("trigger", [])),
            "variable_count":     len(cv.get("variable", [])),
            "tags":               [{"tagId": t.get("tagId"), "name": t.get("name"), "type": t.get("type")}
                                   for t in cv.get("tag", [])],
            "triggers":           [{"triggerId": t.get("triggerId"), "name": t.get("name"), "type": t.get("type")}
                                   for t in cv.get("trigger", [])],
            "variables":          [{"variableId": v.get("variableId"), "name": v.get("name"), "type": v.get("type")}
                                   for v in cv.get("variable", [])],
        }
    except Exception as e:
        return {"error": str(e)}


def get_live_version(container_path: Optional[str] = None,
                     user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get the currently published (live) container version."""
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{cp}/versions:live")
        if "error" in result:
            return result
        cv = result.get("containerVersion", result)
        return {
            "containerVersionId": cv.get("containerVersionId"),
            "name":               cv.get("name"),
            "description":        cv.get("description", ""),
            "path":               cv.get("path"),
            "tag_count":          len(cv.get("tag", [])),
            "trigger_count":      len(cv.get("trigger", [])),
            "variable_count":     len(cv.get("variable", [])),
        }
    except Exception as e:
        return {"error": str(e)}


def create_version(workspace_id: str, name: str, notes: str = "",
                   container_path: Optional[str] = None,
                   dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new container version from a workspace snapshot.
    This does NOT publish — use publish_version after reviewing.
    """
    try:
        cp = resolve_container_path(container_path, user_id)
        wp = workspace_path(cp, workspace_id)
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"workspace": wp, "version_name": name, "notes": notes},
                "next_step": "Pass dry_run=False to create a version snapshot from this workspace.",
            }
        client = get_gtm_client(user_id)
        body = {"name": name}
        if notes:
            body["notes"] = notes
        result = client.post(f"{wp}:create_version", json_data=body)
        if "error" in result:
            return result
        cv = result.get("containerVersion", result)
        audit_log("create_version", cp, {"workspace_id": workspace_id, "name": name},
                  user_id or "", dry_run)
        return {
            "containerVersionId": cv.get("containerVersionId"),
            "name":               cv.get("name"),
            "path":               cv.get("path"),
            "created":            True,
            "next_step":          f"Review the version, then call publish_version with version_id='{cv.get('containerVersionId')}' and dry_run=False to go live.",
        }
    except Exception as e:
        return {"error": str(e)}


def publish_version(version_id: str, container_path: Optional[str] = None,
                    fingerprint: Optional[str] = None,
                    dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Publish a container version to production (live).
    WARNING: This immediately affects your live GTM container.
    dry_run=True by default — you must explicitly pass dry_run=False.
    """
    try:
        cp = resolve_container_path(container_path, user_id)
        version_path = f"{cp}/versions/{version_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"version_path": version_path, "action": "publish"},
                "warning": "This will immediately update your LIVE GTM container. Cannot be reversed via API.",
                "next_step": "Pass dry_run=False to publish this version.",
            }
        client = get_gtm_client(user_id)
        params = {"fingerprint": fingerprint} if fingerprint else None
        result = client.post(f"{version_path}:publish", params=params)
        if "error" in result:
            return result
        audit_log("publish_version", cp, {"version_id": version_id}, user_id or "", dry_run)
        cv = result.get("containerVersion", result)
        return {
            "containerVersionId": cv.get("containerVersionId"),
            "published":          True,
            "path":               cv.get("path"),
        }
    except Exception as e:
        return {"error": str(e)}


def get_latest_version_header(container_path: Optional[str] = None,
                               user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get the header (summary) of the latest container version."""
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{cp}/version_headers:latest")
        if "error" in result:
            return result
        return {
            "containerVersionId": result.get("containerVersionId"),
            "name":               result.get("name"),
            "description":        result.get("description", ""),
            "numTags":            result.get("numTags"),
            "numTriggers":        result.get("numTriggers"),
            "numVariables":       result.get("numVariables"),
            "path":               result.get("path"),
        }
    except Exception as e:
        return {"error": str(e)}


def update_version(version_id: str, name: str, description: str = "",
                   container_path: Optional[str] = None,
                   dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Update a container version's name and description."""
    try:
        cp = resolve_container_path(container_path, user_id)
        vp = f"{cp}/versions/{version_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"version_path": vp, "name": name, "description": description},
                "next_step": "Pass dry_run=False to update this version.",
            }
        client = get_gtm_client(user_id)
        result = client.put(vp, json_data={"name": name, "description": description})
        if "error" in result:
            return result
        audit_log("update_version", cp, {"version_id": version_id, "name": name}, user_id or "", dry_run)
        cv = result.get("containerVersion", result)
        return {"containerVersionId": cv.get("containerVersionId"), "name": cv.get("name"), "updated": True}
    except Exception as e:
        return {"error": str(e)}


def delete_version(version_id: str, container_path: Optional[str] = None,
                   dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Delete a container version. Cannot delete a published (live) version."""
    try:
        cp = resolve_container_path(container_path, user_id)
        vp = f"{cp}/versions/{version_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"version_path": vp, "action": "delete"},
                "next_step": "Pass dry_run=False to delete this version.",
            }
        client = get_gtm_client(user_id)
        result = client.delete(vp)
        if "error" in result:
            return result
        audit_log("delete_version", cp, {"version_id": version_id}, user_id or "", dry_run)
        return {"version_id": version_id, "deleted": True}
    except Exception as e:
        return {"error": str(e)}


def set_latest_version(version_id: str, container_path: Optional[str] = None,
                       dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Set a version as the 'latest' version (the one workspaces sync against)."""
    try:
        cp = resolve_container_path(container_path, user_id)
        vp = f"{cp}/versions/{version_id}:set_latest"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"version_id": version_id, "action": "set_latest"},
                "next_step": "Pass dry_run=False to set this version as latest.",
            }
        client = get_gtm_client(user_id)
        result = client.post(vp)
        if "error" in result:
            return result
        audit_log("set_latest_version", cp, {"version_id": version_id}, user_id or "", dry_run)
        cv = result.get("containerVersion", result)
        return {"containerVersionId": cv.get("containerVersionId"), "set_as_latest": True}
    except Exception as e:
        return {"error": str(e)}


def undelete_version(version_id: str, container_path: Optional[str] = None,
                     dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Restore a previously deleted container version."""
    try:
        cp = resolve_container_path(container_path, user_id)
        vp = f"{cp}/versions/{version_id}:undelete"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"version_id": version_id, "action": "undelete"},
                "next_step": "Pass dry_run=False to restore this version.",
            }
        client = get_gtm_client(user_id)
        result = client.post(vp)
        if "error" in result:
            return result
        audit_log("undelete_version", cp, {"version_id": version_id}, user_id or "", dry_run)
        cv = result.get("containerVersion", result)
        return {"containerVersionId": cv.get("containerVersionId"), "restored": True}
    except Exception as e:
        return {"error": str(e)}
