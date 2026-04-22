"""
GTM Variables.

Tools:
  list_variables   — list custom variables in workspace
  get_variable     — get variable details
  create_variable  — create variable (dry_run)
  update_variable  — update variable (dry_run)
  delete_variable  — delete variable (dry_run)

Common variable types:
  v       — Data Layer Variable
  k       — First Party Cookie
  jsm     — Custom JavaScript
  smm     — Lookup Table
  f       — HTTP Referrer
  u       — URL
  j       — JavaScript Variable
  c       — Constant String
  e       — Custom Event
  r       — Random Number
  vis     — Element Visibility
  ctv     — Container Version Number

Variable body examples:

Data Layer Variable:
  {"name": "DL - transaction_id", "type": "v",
   "parameter": [
     {"type": "integer", "key": "dataLayerVersion", "value": "2"},
     {"type": "template", "key": "name", "value": "ecommerce.transaction_id"}
   ]}

Custom JavaScript:
  {"name": "JS - Page Category", "type": "jsm",
   "parameter": [
     {"type": "template", "key": "javascript",
      "value": "function() { return document.body.dataset.category || ''; }"}
   ]}

Constant:
  {"name": "Const - GA4 Measurement ID", "type": "c",
   "parameter": [{"type": "template", "key": "value", "value": "G-XXXXXXX"}]}
"""
from typing import Any, Dict, Optional

from gtm_client import get_gtm_client
from audit import audit_log
from tools._helpers import resolve_container_path, workspace_path


def _vars_path(cp: str, workspace_id: str) -> str:
    return f"{workspace_path(cp, workspace_id)}/variables"


def list_variables(workspace_id: str, container_path: Optional[str] = None,
                   user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(_vars_path(cp, workspace_id))
        if "error" in result:
            return result
        variables = result.get("variable", [])
        return {
            "workspace": workspace_path(cp, workspace_id),
            "count": len(variables),
            "variables": [
                {
                    "variableId": v.get("variableId"),
                    "name":       v.get("name"),
                    "type":       v.get("type"),
                    "path":       v.get("path"),
                }
                for v in variables
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def get_variable(workspace_id: str, variable_id: str, container_path: Optional[str] = None,
                 user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_vars_path(cp, workspace_id)}/{variable_id}"
        client = get_gtm_client(user_id)
        result = client.get(path)
        if "error" in result:
            return result
        return result
    except Exception as e:
        return {"error": str(e)}


def create_variable(workspace_id: str, body: dict, container_path: Optional[str] = None,
                    dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a custom variable. body must have at minimum: name (str), type (str), parameter (list).
    """
    try:
        cp = resolve_container_path(container_path, user_id)
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"workspace": workspace_path(cp, workspace_id), "body": body},
                "next_step": "Pass dry_run=False to create this variable.",
            }
        client = get_gtm_client(user_id)
        result = client.post(_vars_path(cp, workspace_id), json_data=body)
        if "error" in result:
            return result
        audit_log("create_variable", cp, {"name": body.get("name"), "type": body.get("type")},
                  user_id or "", dry_run)
        return {"variableId": result.get("variableId"), "name": result.get("name"),
                "path": result.get("path"), "created": True}
    except Exception as e:
        return {"error": str(e)}


def update_variable(workspace_id: str, variable_id: str, body: dict,
                    container_path: Optional[str] = None, dry_run: bool = True,
                    user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_vars_path(cp, workspace_id)}/{variable_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"variable_path": path, "body": body},
                "next_step": "Pass dry_run=False to update this variable.",
            }
        client = get_gtm_client(user_id)
        result = client.put(path, json_data=body)
        if "error" in result:
            return result
        audit_log("update_variable", cp, {"variable_id": variable_id, "name": body.get("name")},
                  user_id or "", dry_run)
        return {"variableId": result.get("variableId"), "name": result.get("name"), "updated": True}
    except Exception as e:
        return {"error": str(e)}


def delete_variable(workspace_id: str, variable_id: str, container_path: Optional[str] = None,
                    dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_vars_path(cp, workspace_id)}/{variable_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"variable_path": path, "action": "delete"},
                "next_step": "Pass dry_run=False to delete this variable.",
            }
        client = get_gtm_client(user_id)
        result = client.delete(path)
        if "error" in result:
            return result
        audit_log("delete_variable", cp, {"variable_id": variable_id}, user_id or "", dry_run)
        return {"variable_id": variable_id, "deleted": True}
    except Exception as e:
        return {"error": str(e)}
