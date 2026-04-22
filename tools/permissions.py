"""
GTM User Permissions.

Manage which users have access to GTM accounts and containers.

Permission levels: read, edit, publish, admin, noAccess

Tools:
  list_user_permissions   — list all user permissions for an account
  get_user_permission     — get a specific user's permission
  create_user_permission  — grant access to a user (dry_run)
  update_user_permission  — update a user's permissions (dry_run)
  delete_user_permission  — revoke a user's access (dry_run)

Permission body example:
  {
    "emailAddress": "user@example.com",
    "accountAccess": {"permission": "admin"},
    "containerAccess": [
      {"containerId": "456", "permission": "publish"}
    ]
  }
"""
from typing import Any, Dict, Optional

from gtm_client import get_gtm_client
from audit import audit_log
from tools._helpers import account_path_from_container, resolve_container_path


def _resolve_account_path(account_path: Optional[str], container_path: Optional[str],
                           user_id: Optional[str]) -> str:
    if account_path:
        return account_path.strip("/")
    cp = resolve_container_path(container_path, user_id)
    return account_path_from_container(cp)


def list_user_permissions(account_path: Optional[str] = None, container_path: Optional[str] = None,
                           user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        ap = _resolve_account_path(account_path, container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{ap}/user_permissions")
        if "error" in result:
            return result
        perms = result.get("userPermission", [])
        return {
            "account": ap,
            "count": len(perms),
            "user_permissions": [
                {
                    "userPermissionId": p.get("userPermissionId"),
                    "emailAddress":     p.get("emailAddress"),
                    "accountAccess":    p.get("accountAccess", {}).get("permission"),
                    "containerCount":   len(p.get("containerAccess", [])),
                }
                for p in perms
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def get_user_permission(permission_id: str, account_path: Optional[str] = None,
                         container_path: Optional[str] = None,
                         user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        ap = _resolve_account_path(account_path, container_path, user_id)
        client = get_gtm_client(user_id)
        result = client.get(f"{ap}/user_permissions/{permission_id}")
        if "error" in result:
            return result
        return result
    except Exception as e:
        return {"error": str(e)}


def create_user_permission(body: dict, account_path: Optional[str] = None,
                            container_path: Optional[str] = None,
                            dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Grant a user access to a GTM account/containers.
    body must include: emailAddress, accountAccess: {permission}, containerAccess: [{containerId, permission}]
    """
    try:
        ap = _resolve_account_path(account_path, container_path, user_id)
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"account": ap, "body": body},
                "next_step": "Pass dry_run=False to grant this user access.",
            }
        client = get_gtm_client(user_id)
        result = client.post(f"{ap}/user_permissions", json_data=body)
        if "error" in result:
            return result
        audit_log("create_user_permission", ap, {"email": body.get("emailAddress")}, user_id or "", dry_run)
        return {
            "userPermissionId": result.get("userPermissionId"),
            "emailAddress":     result.get("emailAddress"),
            "created":          True,
        }
    except Exception as e:
        return {"error": str(e)}


def update_user_permission(permission_id: str, body: dict, account_path: Optional[str] = None,
                            container_path: Optional[str] = None,
                            dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Update a user's GTM permissions. body = full UserPermission resource."""
    try:
        ap = _resolve_account_path(account_path, container_path, user_id)
        path = f"{ap}/user_permissions/{permission_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"permission_path": path, "body": body},
                "next_step": "Pass dry_run=False to update this user's permissions.",
            }
        client = get_gtm_client(user_id)
        result = client.put(path, json_data=body)
        if "error" in result:
            return result
        audit_log("update_user_permission", ap, {"permission_id": permission_id}, user_id or "", dry_run)
        return {"userPermissionId": result.get("userPermissionId"), "updated": True}
    except Exception as e:
        return {"error": str(e)}


def delete_user_permission(permission_id: str, account_path: Optional[str] = None,
                            container_path: Optional[str] = None,
                            dry_run: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Revoke a user's access to a GTM account."""
    try:
        ap = _resolve_account_path(account_path, container_path, user_id)
        path = f"{ap}/user_permissions/{permission_id}"
        if dry_run:
            return {
                "dry_run": True,
                "preview": {"permission_path": path, "action": "delete"},
                "next_step": "Pass dry_run=False to revoke this user's access.",
            }
        client = get_gtm_client(user_id)
        result = client.delete(path)
        if "error" in result:
            return result
        audit_log("delete_user_permission", ap, {"permission_id": permission_id}, user_id or "", dry_run)
        return {"permission_id": permission_id, "deleted": True}
    except Exception as e:
        return {"error": str(e)}
