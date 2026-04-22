"""
GTM Triggers.

Tools:
  list_triggers   — list all triggers in a workspace
  get_trigger     — get trigger details
  create_trigger  — create trigger (dry_run)
  update_trigger  — update trigger (dry_run)
  delete_trigger  — delete trigger (dry_run)

Common trigger types:
  pageview        — Page View
  domReady        — DOM Ready
  windowLoaded    — Window Loaded
  click           — All Elements Click
  linkClick       — Just Links Click
  formSubmit      — Form Submission
  jsError         — JavaScript Error
  historyChange   — History Change
  scrollDepth     — Scroll Depth
  timer           — Timer
  customEvent     — Custom Event (needs eventName)
  always          — Consent Initialization - All Pages
  consentInit     — Consent Initialization

NOTE: autoEventFilter (click/form filters) is silently dropped by GTM API v2.
Configure click filter conditions manually in GTM UI after creating the trigger.

Trigger body example:
  {
    "name": "All Page Views",
    "type": "pageview"
  }

Custom event example:
  {
    "name": "Purchase Event",
    "type": "customEvent",
    "customEventFilter": [
      {"type": "equals", "parameter": [
        {"type": "template", "key": "arg0", "value": "{{_event}}"},
        {"type": "template", "key": "arg1", "value": "purchase"}
      ]}
    ]
  }
"""
from typing import Any, Dict, Optional

from gtm_client import get_gtm_client
from audit import audit_log
from tools._helpers import resolve_container_path, workspace_path


def _triggers_path(cp: str, workspace_id: str) -> str:
    return f"{workspace_path(cp, workspace_id)}/triggers"


def list_triggers(workspace_id: str, container_path: Optional[str] = None,
                  user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(_triggers_path(cp, workspace_id))
        if "error" in result:
            return result
        triggers = result.get("trigger", [])
        return {
            "workspace": workspace_path(cp, workspace_id),
            "count": len(triggers),
            "triggers": [
                {
                    "triggerId": t.get("triggerId"),
                    "name":      t.get("name"),
                    "type":      t.get("type"),
                    "path":      t.get("path"),
                }
                for t in triggers
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def get_trigger(workspace_id: str, trigger_id: str, container_path: Optional[str] = None,
                user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_triggers_path(cp, workspace_id)}/{trigger_id}"
        client = get_gtm_client(user_id)
        result = client.get(path)
        if "error" in result:
            return result
        return result
    except Exception as e:
        return {"error": str(e)}


def create_trigger(workspace_id: str, body: dict, container_path: Optional[str] = None,
                   dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a trigger. body must have at minimum: name (str), type (str).
    WARNING: autoEventFilter is silently dropped by GTM API. Use filter/customEventFilter.
    """
    try:
        cp = resolve_container_path(container_path, user_id)
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"workspace": workspace_path(cp, workspace_id), "body": body},
                "warning": "autoEventFilter is silently dropped by GTM API v2 — configure click filter conditions in GTM UI.",
                "next_step": "Pass dry_run=False to create this trigger.",
            }
        client = get_gtm_client(user_id)
        result = client.post(_triggers_path(cp, workspace_id), json_data=body)
        if "error" in result:
            return result
        audit_log("create_trigger", cp, {"name": body.get("name"), "type": body.get("type")},
                  user_id or "", dry_run)
        return {"triggerId": result.get("triggerId"), "name": result.get("name"),
                "path": result.get("path"), "created": True}
    except Exception as e:
        return {"error": str(e)}


def update_trigger(workspace_id: str, trigger_id: str, body: dict,
                   container_path: Optional[str] = None, dry_run: bool = True,
                   user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_triggers_path(cp, workspace_id)}/{trigger_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"trigger_path": path, "body": body},
                "next_step": "Pass dry_run=False to update this trigger.",
            }
        client = get_gtm_client(user_id)
        result = client.put(path, json_data=body)
        if "error" in result:
            return result
        audit_log("update_trigger", cp, {"trigger_id": trigger_id, "name": body.get("name")},
                  user_id or "", dry_run)
        return {"triggerId": result.get("triggerId"), "name": result.get("name"), "updated": True}
    except Exception as e:
        return {"error": str(e)}


def delete_trigger(workspace_id: str, trigger_id: str, container_path: Optional[str] = None,
                   dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_triggers_path(cp, workspace_id)}/{trigger_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"trigger_path": path, "action": "delete"},
                "next_step": "Pass dry_run=False to delete this trigger.",
            }
        client = get_gtm_client(user_id)
        result = client.delete(path)
        if "error" in result:
            return result
        audit_log("delete_trigger", cp, {"trigger_id": trigger_id}, user_id or "", dry_run)
        return {"trigger_id": trigger_id, "deleted": True}
    except Exception as e:
        return {"error": str(e)}
