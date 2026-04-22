"""
Encrypted token storage for Google Tag Manager OAuth tokens.

Each user_id maps to:
  {refresh_token, accounts: [...], containers: [...], active_container_path}
Server-wide:
  {__meta__: {active_user_id: ...}}
"""
import json
import logging
import os
from cryptography.fernet import Fernet
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TOKEN_FILE = "/tokens/tokens.encrypted"


def _load_encryption_key() -> str:
    key = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        key = Fernet.generate_key().decode()
        logger.warning(
            "TOKEN_ENCRYPTION_KEY not set. Generated ephemeral key — "
            "tokens will be lost on restart. Set TOKEN_ENCRYPTION_KEY env var."
        )
    return key


class TokenStore:
    """Encrypted per-user Google Tag Manager token storage."""

    def __init__(self):
        self.token_file = TOKEN_FILE
        self._data: Dict[str, Dict[str, Any]] = {}
        self._meta: Dict[str, Any] = {}

        try:
            self.cipher = Fernet(_load_encryption_key().encode())
        except Exception as e:
            logger.error("ERROR initializing cipher: %s", e)
            self.cipher = None

        self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self):
        if not os.path.exists(self.token_file):
            return
        try:
            with open(self.token_file, "rb") as f:
                encrypted = f.read()
            if self.cipher and encrypted:
                raw = json.loads(self.cipher.decrypt(encrypted))
                self._meta = raw.pop("__meta__", {})
                for uid, val in raw.items():
                    self._data[uid] = val if isinstance(val, dict) else {"refresh_token": val}
                logger.info("Loaded %d users", len(self._data))
        except Exception as e:
            logger.error("Could not load tokens: %s", e)
            self._data = {}

    def _save(self):
        if not self.cipher:
            logger.error("No cipher — cannot save tokens")
            return
        try:
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            payload = dict(self._data)
            if self._meta:
                payload["__meta__"] = self._meta
            encrypted = self.cipher.encrypt(json.dumps(payload).encode())
            with open(self.token_file, "wb") as f:
                f.write(encrypted)
        except Exception as e:
            logger.error("ERROR saving: %s", e)

    # ── token ─────────────────────────────────────────────────────────────────

    def save_token(self, user_id: str, refresh_token: str):
        entry = self._data.get(user_id, {})
        entry["refresh_token"] = refresh_token
        self._data[user_id] = entry
        self._save()

    def get_token(self, user_id: str) -> Optional[str]:
        return self._data.get(user_id, {}).get("refresh_token")

    def delete_token(self, user_id: str):
        if user_id in self._data:
            del self._data[user_id]
            self._save()

    def list_users(self) -> List[str]:
        return list(self._data.keys())

    # ── accounts & containers ─────────────────────────────────────────────────

    def save_accounts(self, user_id: str, accounts: List[dict]):
        if user_id not in self._data:
            self._data[user_id] = {}
        self._data[user_id]["accounts"] = accounts
        self._save()

    def get_accounts(self, user_id: str) -> List[dict]:
        return self._data.get(user_id, {}).get("accounts", [])

    def save_containers(self, user_id: str, containers: List[dict]):
        if user_id not in self._data:
            self._data[user_id] = {}
        self._data[user_id]["containers"] = containers
        self._save()

    def get_containers(self, user_id: str) -> List[dict]:
        return self._data.get(user_id, {}).get("containers", [])

    def set_active_container(self, user_id: str, container_path: str):
        if user_id not in self._data:
            raise ValueError(f"User {user_id} not found")
        self._data[user_id]["active_container_path"] = container_path
        self._save()

    def get_active_container(self, user_id: str) -> Optional[str]:
        return self._data.get(user_id, {}).get("active_container_path")

    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        entry = self._data.get(user_id, {})
        return {
            "user_id": user_id,
            "has_token": bool(entry.get("refresh_token")),
            "active_container_path": entry.get("active_container_path"),
            "accounts": entry.get("accounts", []),
            "containers": entry.get("containers", []),
        }

    # ── server-wide state ─────────────────────────────────────────────────────

    def set_active_user_id(self, user_id: str):
        self._meta["active_user_id"] = user_id
        self._save()

    def get_active_user_id(self) -> Optional[str]:
        return self._meta.get("active_user_id")


_token_store: Optional[TokenStore] = None


def get_token_store() -> TokenStore:
    global _token_store
    if _token_store is None:
        _token_store = TokenStore()
    return _token_store
