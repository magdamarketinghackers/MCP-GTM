"""
GTM Tags.

Tools:
  list_tags   — list all tags in a workspace
  get_tag     — get tag details
  create_tag  — create tag (dry_run)
  update_tag  — update tag (dry_run)
  delete_tag  — delete tag (dry_run)

Common tag types:
  ua          — Universal Analytics (deprecated)
  gaawc       — GA4 Configuration
  gaawe       — GA4 Event
  html        — Custom HTML
  img         — Custom Image (Pixel)
  googtag     — Google tag
  awct        — Google Ads Conversion Tracking
  sp          — Scrolling Performance Monitoring
  flc         — Floodlight Counter
  fls         — Floodlight Sales

Tag body example:
  {
    "name": "GA4 Configuration",
    "type": "gaawc",
    "parameter": [{"type": "template", "key": "measurementId", "value": "G-XXXXXXX"}],
    "firingTriggerId": ["2147479553"],  # All Pages trigger ID
    "tagFiringOption": "oncePerLoad"
  }
"""
from typing import Any, Dict, Optional

from gtm_client import get_gtm_client
from audit import audit_log
from tools._helpers import resolve_container_path, workspace_path


def _tags_path(cp: str, workspace_id: str) -> str:
    return f"{workspace_path(cp, workspace_id)}/tags"


def list_tags(workspace_id: str, container_path: Optional[str] = None,
              user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(_tags_path(cp, workspace_id))
        if "error" in result:
            return result
        tags = result.get("tag", [])
        return {
            "workspace": workspace_path(cp, workspace_id),
            "count": len(tags),
            "tags": [
                {
                    "tagId":          t.get("tagId"),
                    "name":           t.get("name"),
                    "type":           t.get("type"),
                    "firingTriggerId": t.get("firingTriggerId", []),
                    "tagFiringOption": t.get("tagFiringOption"),
                    "paused":         t.get("paused", False),
                    "path":           t.get("path"),
                }
                for t in tags
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def get_tag(workspace_id: str, tag_id: str, container_path: Optional[str] = None,
            user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_tags_path(cp, workspace_id)}/{tag_id}"
        client = get_gtm_client(user_id)
        result = client.get(path)
        if "error" in result:
            return result
        return result
    except Exception as e:
        return {"error": str(e)}


def create_tag(workspace_id: str, body: dict, container_path: Optional[str] = None,
               dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a tag. body must be a GTM Tag resource with at minimum:
      name (str), type (str), firingTriggerId (list), parameter (list)
    """
    try:
        cp = resolve_container_path(container_path, user_id)
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"workspace": workspace_path(cp, workspace_id), "body": body},
                "next_step": "Pass dry_run=False to create this tag.",
            }
        client = get_gtm_client(user_id)
        result = client.post(_tags_path(cp, workspace_id), json_data=body)
        if "error" in result:
            return result
        audit_log("create_tag", cp, {"name": body.get("name"), "type": body.get("type")},
                  user_id or "", dry_run)
        return {"tagId": result.get("tagId"), "name": result.get("name"), "path": result.get("path"), "created": True}
    except Exception as e:
        return {"error": str(e)}


def update_tag(workspace_id: str, tag_id: str, body: dict, container_path: Optional[str] = None,
               fingerprint: Optional[str] = None, dry_run: bool = True,
               user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Update a tag. body is the full Tag resource (GTM replaces entire resource on PUT).
    fingerprint: optional — current fingerprint for optimistic locking.
    """
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_tags_path(cp, workspace_id)}/{tag_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"tag_path": path, "body": body},
                "next_step": "Pass dry_run=False to update this tag.",
            }
        params = {"fingerprint": fingerprint} if fingerprint else None
        client = get_gtm_client(user_id)
        result = client.put(path, json_data=body)
        if "error" in result:
            return result
        audit_log("update_tag", cp, {"tag_id": tag_id, "name": body.get("name")},
                  user_id or "", dry_run)
        return {"tagId": result.get("tagId"), "name": result.get("name"), "updated": True}
    except Exception as e:
        return {"error": str(e)}


def delete_tag(workspace_id: str, tag_id: str, container_path: Optional[str] = None,
               dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_tags_path(cp, workspace_id)}/{tag_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"tag_path": path, "action": "delete"},
                "next_step": "Pass dry_run=False to delete this tag.",
            }
        client = get_gtm_client(user_id)
        result = client.delete(path)
        if "error" in result:
            return result
        audit_log("delete_tag", cp, {"tag_id": tag_id}, user_id or "", dry_run)
        return {"tag_id": tag_id, "deleted": True}
    except Exception as e:
        return {"error": str(e)}
