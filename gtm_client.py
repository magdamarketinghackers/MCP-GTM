"""
Google Tag Manager API v2 client.

Handles:
1. Token refresh: refresh_token → access_token (cached 50min per user)
2. GTM API v2 REST calls (httpx, no SDK)
3. Rate limit: GTM allows ~0.25 QPS — handled via error return for 429/403
"""
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from token_store import get_token_store

logger = logging.getLogger(__name__)

GTM_BASE      = "https://www.googleapis.com/tagmanager/v2"
TOKEN_URL     = "https://oauth2.googleapis.com/token"
REQUEST_TIMEOUT = 30.0

GOOGLE_OAUTH_CLIENT_ID     = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")

# user_id → (access_token, expires_at_unix)
_token_cache: Dict[str, Tuple[str, float]] = {}

_active_user_id: Optional[str] = None


def get_active_user_id() -> str:
    global _active_user_id
    if not _active_user_id:
        stored = get_token_store().get_active_user_id()
        if stored and stored in get_token_store().list_users():
            _active_user_id = stored
        else:
            users = get_token_store().list_users()
            if users:
                _active_user_id = users[0]
            else:
                raise ValueError("No user authorized. Visit /auth/start?user_id=<email> to authorize.")
    return _active_user_id


def set_active_user(user_id: str):
    global _active_user_id
    _active_user_id = user_id
    get_token_store().set_active_user_id(user_id)


def _refresh_access_token(user_id: str) -> str:
    """Exchange stored refresh_token for a fresh access_token (cached 50 min)."""
    if user_id in _token_cache:
        access_token, expires_at = _token_cache[user_id]
        if time.time() < expires_at:
            return access_token

    refresh_token = get_token_store().get_token(user_id)
    if not refresh_token:
        raise ValueError(f"User '{user_id}' not authorized. Visit /auth/start?user_id={user_id}")

    resp = httpx.post(TOKEN_URL, data={
        "client_id":     GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type":    "refresh_token",
    }, timeout=REQUEST_TIMEOUT)

    if resp.status_code != 200:
        raise ValueError(f"Token refresh failed for '{user_id}': {resp.text}")

    body = resp.json()
    access_token = body.get("access_token")
    if not access_token:
        raise ValueError(f"No access_token in refresh response: {body}")

    expires_in = body.get("expires_in", 3600)
    _token_cache[user_id] = (access_token, time.time() + min(expires_in - 60, 3000))
    return access_token


def get_gtm_client(user_id: Optional[str] = None) -> "GTMClient":
    uid = user_id or get_active_user_id()
    access_token = _refresh_access_token(uid)
    return GTMClient(access_token)


class GTMClient:
    """Thin httpx wrapper for Google Tag Manager API v2."""

    def __init__(self, access_token: str):
        self.token = access_token
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, params=None, json_data=None) -> Dict[str, Any]:
        url = f"{GTM_BASE}/{path.lstrip('/')}"
        try:
            r = httpx.request(
                method, url,
                headers=self._headers,
                params=params,
                json=json_data,
                timeout=REQUEST_TIMEOUT,
            )
            body = r.json() if r.text else {}
            if r.status_code == 429:
                return {"error": "GTM API rate limit exceeded (0.25 QPS). Wait a few seconds and retry.", "code": 429}
            if r.status_code >= 400:
                err = body.get("error", {})
                if isinstance(err, dict):
                    return {"error": err.get("message", str(body)), "code": r.status_code}
                return {"error": str(body), "code": r.status_code}
            return body
        except Exception as e:
            return {"error": str(e)}

    def get(self, path: str, params=None) -> Dict[str, Any]:
        return self._request("GET", path, params=params)

    def post(self, path: str, json_data=None, params=None) -> Dict[str, Any]:
        return self._request("POST", path, params=params, json_data=json_data)

    def put(self, path: str, json_data=None) -> Dict[str, Any]:
        return self._request("PUT", path, json_data=json_data)

    def delete(self, path: str, params=None) -> Dict[str, Any]:
        return self._request("DELETE", path, params=params)
