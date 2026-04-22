"""
GTM Folders.

Folders organise tags, triggers, and variables within a workspace.

Tools:
  list_folders              — list all folders in a workspace
  get_folder                — get folder details
  create_folder             — create folder (dry_run)
  update_folder             — rename folder (dry_run)
  delete_folder             — delete folder (dry_run)
  list_folder_entities      — list all entities (tags/triggers/variables) in a folder
  move_entities_to_folder   — move entities into a folder (dry_run)
"""
from typing import Any, Dict, List, Optional

from gtm_client import get_gtm_client
from audit import audit_log
from tools._helpers import resolve_container_path, workspace_path


def _folders_path(cp: str, workspace_id: str) -> str:
    return f"{workspace_path(cp, workspace_id)}/folders"


def list_folders(workspace_id: str, container_path: Optional[str] = None,
                 user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(_folders_path(cp, workspace_id))
        if "error" in result:
            return result
        folders = result.get("folder", [])
        return {
            "workspace": workspace_path(cp, workspace_id),
            "count": len(folders),
            "folders": [
                {
                    "folderId": f.get("folderId"),
                    "name":     f.get("name"),
                    "path":     f.get("path"),
                }
                for f in folders
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def get_folder(workspace_id: str, folder_id: str, container_path: Optional[str] = None,
               user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{_folders_path(cp, workspace_id)}/{folder_id}")
        if "error" in result:
            return result
        return result
    except Exception as e:
        return {"error": str(e)}


def create_folder(workspace_id: str, name: str, container_path: Optional[str] = None,
                  dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"workspace": workspace_path(cp, workspace_id), "name": name},
                "next_step": "Pass dry_run=False to create this folder.",
            }
        client = get_gtm_client(user_id)
        result = client.post(_folders_path(cp, workspace_id), json_data={"name": name})
        if "error" in result:
            return result
        audit_log("create_folder", cp, {"name": name}, user_id or "", dry_run)
        return {"folderId": result.get("folderId"), "name": result.get("name"),
                "path": result.get("path"), "created": True}
    except Exception as e:
        return {"error": str(e)}


def update_folder(workspace_id: str, folder_id: str, name: str,
                  container_path: Optional[str] = None, dry_run: bool = True,
                  user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_folders_path(cp, workspace_id)}/{folder_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"folder_path": path, "name": name},
                "next_step": "Pass dry_run=False to rename this folder.",
            }
        client = get_gtm_client(user_id)
        result = client.put(path, json_data={"name": name})
        if "error" in result:
            return result
        audit_log("update_folder", cp, {"folder_id": folder_id, "name": name}, user_id or "", dry_run)
        return {"folderId": result.get("folderId"), "name": result.get("name"), "updated": True}
    except Exception as e:
        return {"error": str(e)}


def delete_folder(workspace_id: str, folder_id: str, container_path: Optional[str] = None,
                  dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Delete a folder. Entities inside the folder are NOT deleted — they become unorganised."""
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_folders_path(cp, workspace_id)}/{folder_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"folder_path": path, "action": "delete"},
                "note": "Entities inside the folder are NOT deleted, they become unorganised.",
                "next_step": "Pass dry_run=False to delete this folder.",
            }
        client = get_gtm_client(user_id)
        result = client.delete(path)
        if "error" in result:
            return result
        audit_log("delete_folder", cp, {"folder_id": folder_id}, user_id or "", dry_run)
        return {"folder_id": folder_id, "deleted": True}
    except Exception as e:
        return {"error": str(e)}


def list_folder_entities(workspace_id: str, folder_id: str, container_path: Optional[str] = None,
                          user_id: Optional[str] = None) -> Dict[str, Any]:
    """List all tags, triggers, and variables that belong to a folder."""
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_folders_path(cp, workspace_id)}/{folder_id}:entities"
        client = get_gtm_client(user_id)
        result = client.post(path)
        if "error" in result:
            return result
        return {
            "folder_id": folder_id,
            "tags":      [{"tagId": t.get("tagId"), "name": t.get("name")}
                          for t in result.get("tag", [])],
            "triggers":  [{"triggerId": t.get("triggerId"), "name": t.get("name")}
                          for t in result.get("trigger", [])],
            "variables": [{"variableId": v.get("variableId"), "name": v.get("name")}
                          for v in result.get("variable", [])],
        }
    except Exception as e:
        return {"error": str(e)}


def move_entities_to_folder(workspace_id: str, folder_id: str,
                              tag_ids: Optional[List[str]] = None,
                              trigger_ids: Optional[List[str]] = None,
                              variable_ids: Optional[List[str]] = None,
                              container_path: Optional[str] = None,
                              dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Move tags, triggers, and/or variables into a folder."""
    try:
        cp = resolve_container_path(container_path, user_id)
        path = f"{_folders_path(cp, workspace_id)}/{folder_id}:move_entities_to_folder"
        payload: Dict[str, Any] = {}
        if tag_ids:
            payload["tag"] = [{"tagId": tid} for tid in tag_ids]
        if trigger_ids:
            payload["trigger"] = [{"triggerId": tid} for tid in trigger_ids]
        if variable_ids:
            payload["variable"] = [{"variableId": vid} for vid in variable_ids]
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"folder_id": folder_id, "entities": payload},
                "next_step": "Pass dry_run=False to move these entities.",
            }
        client = get_gtm_client(user_id)
        result = client.post(path, json_data=payload)
        if "error" in result:
            return result
        audit_log("move_entities_to_folder", cp, {"folder_id": folder_id, "entities": payload},
                  user_id or "", dry_run)
        return {"folder_id": folder_id, "moved": True}
    except Exception as e:
        return {"error": str(e)}
