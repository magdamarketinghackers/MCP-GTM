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
    """
    Return container_path from the argument, or fall back to the user's single
    container when exactly one exists. With 0 or 2+ containers, raise with a
    listing — this server keeps no 'active container' state, so the caller must
    pass container_path explicitly.
    """
    if container_path:
        return container_path.strip("/")
    uid = user_id or get_active_user_id()
    containers = get_token_store().get_containers(uid)
    if not containers:
        raise ValueError(
            f"No containers cached for user '{uid}'. Run discover_containers first, "
            f"then pass container_path explicitly."
        )
    if len(containers) > 1:
        paths = [c.get("path", c.get("publicId", "")) for c in containers]
        raise ValueError(
            f"container_path required: user '{uid}' has multiple containers {paths}. "
            f"Pass container_path explicitly (e.g. accounts/X/containers/Y). "
            f"This server keeps no 'active container' state."
        )
    return containers[0].get("path", "").strip("/")


def workspace_path(container_path: str, workspace_id: str) -> str:
    return f"{container_path.strip('/')}/workspaces/{workspace_id}"


def account_path_from_container(container_path: str) -> str:
    """Extract accounts/{id} from accounts/{id}/containers/{id}."""
    parts = container_path.strip("/").split("/")
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]
