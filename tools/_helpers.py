"""
GTM path helpers.

GTM API v2 uses resource paths everywhere:
  accounts/{accountId}
  accounts/{accountId}/containers/{containerId}
  accounts/{accountId}/containers/{containerId}/workspaces/{workspaceId}
  ...

active_container_path is stored in token_store as "accounts/123/containers/456".
workspace_path = container_path + "/workspaces/" + workspace_id
"""
from typing import Optional
from token_store import get_token_store
from gtm_client import get_active_user_id


def resolve_container_path(container_path: Optional[str], user_id: Optional[str]) -> str:
    """Return container_path from arg or active container for user."""
    if container_path:
        return container_path.strip("/")
    uid = user_id or get_active_user_id()
    cp = get_token_store().get_active_container(uid)
    if not cp:
        raise ValueError(
            "No active container set. Use set_active_container or pass container_path. "
            "Run discover_containers first."
        )
    return cp.strip("/")


def workspace_path(container_path: str, workspace_id: str) -> str:
    return f"{container_path.strip('/')}/workspaces/{workspace_id}"


def account_path_from_container(container_path: str) -> str:
    """Extract accounts/{id} from accounts/{id}/containers/{id}."""
    parts = container_path.strip("/").split("/")
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]
