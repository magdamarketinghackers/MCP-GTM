"""
GTM Accounts & Containers.

Tools:
  list_accounts      — list all GTM accounts
  list_containers    — list containers in an account
  get_container      — get container details
  discover_containers — fetch all accounts+containers and save to token store
"""
from typing import Any, Dict, List, Optional

from gtm_client import get_gtm_client, get_active_user_id
from token_store import get_token_store


def list_accounts(user_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        client = get_gtm_client(user_id)
        result = client.get("accounts")
        if "error" in result:
            return result
        accounts = result.get("account", [])
        return {
            "count": len(accounts),
            "accounts": [
                {
                    "path":      a.get("path"),
                    "accountId": a.get("accountId"),
                    "name":      a.get("name"),
                }
                for a in accounts
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def list_containers(account_path: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """List containers for an account. account_path e.g. 'accounts/123'."""
    try:
        client = get_gtm_client(user_id)
        result = client.get(f"{account_path.strip('/')}/containers")
        if "error" in result:
            return result
        containers = result.get("container", [])
        return {
            "count": len(containers),
            "containers": [
                {
                    "path":        c.get("path"),
                    "containerId": c.get("containerId"),
                    "name":        c.get("name"),
                    "publicId":    c.get("publicId"),
                    "usageContext": c.get("usageContext", []),
                }
                for c in containers
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def get_container(container_path: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get details for a single container. container_path e.g. 'accounts/123/containers/456'."""
    try:
        client = get_gtm_client(user_id)
        result = client.get(container_path.strip("/"))
        if "error" in result:
            return result
        return {
            "path":         result.get("path"),
            "containerId":  result.get("containerId"),
            "name":         result.get("name"),
            "publicId":     result.get("publicId"),
            "usageContext": result.get("usageContext", []),
            "tagManagerUrl": result.get("tagManagerUrl"),
        }
    except Exception as e:
        return {"error": str(e)}


def discover_containers(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch all GTM accounts and their containers for a user.
    Saves to token store and sets first container as active.
    """
    try:
        uid = user_id or get_active_user_id()
        client = get_gtm_client(uid)

        # fetch accounts
        acct_result = client.get("accounts")
        if "error" in acct_result:
            return acct_result
        accounts = acct_result.get("account", [])
        get_token_store().save_accounts(uid, accounts)

        # fetch containers for each account
        all_containers: List[dict] = []
        for acct in accounts:
            acct_path = acct.get("path", "")
            cont_result = client.get(f"{acct_path}/containers")
            if "error" not in cont_result:
                for c in cont_result.get("container", []):
                    all_containers.append(c)

        get_token_store().save_containers(uid, all_containers)

        # set first container as active
        if all_containers:
            first_path = all_containers[0].get("path", "")
            get_token_store().set_active_container(uid, first_path)

        return {
            "accounts": len(accounts),
            "containers": len(all_containers),
            "active_container": all_containers[0].get("path") if all_containers else None,
            "containers_list": [
                {
                    "path":     c.get("path"),
                    "name":     c.get("name"),
                    "publicId": c.get("publicId"),
                }
                for c in all_containers
            ],
        }
    except Exception as e:
        return {"error": str(e)}
