"""
Local user ID for multi-tenant memory isolation.

Generates a random UUID on first use and caches it to disk, OR 
reads the dynamically injected user_id from the current request's auth context.
"""

import json
import uuid
import os
from pathlib import Path

from core.auth.context import get_current_user_id

_USER_ID_PATH = Path(__file__).parent.parent / "memory" / "remme_index" / "user_id.json"
_CACHED_USER_ID: str | None = None


def is_auth_enabled() -> bool:
    """Check if Phase 5 Auth mechanism (JWT/Header context) is enabled."""
    return os.environ.get("AUTH_ENABLED", "true").lower() == "true"


def get_user_id() -> str:
    """
    Return the local user ID. 
    1. Reads from FastAPI Auth Context / headers if Phase 5 Auth is enabled.
    2. Falls back to generating a UUID on first call and caching to file (legacy).
    """
    
    # 1. First, check if there's a user_id injected into the request context via AuthMiddleware
    if is_auth_enabled():
        ctx_user_id = get_current_user_id()
        if ctx_user_id:
            return ctx_user_id
        # Note: AuthMiddleware protects the routes. If we reach here without a user,
        # it might be a background task or public route. Allow fallback below for safety
        # or tests but consider rejecting in the future.

    # 2. Legacy fallback
    global _CACHED_USER_ID
    if _CACHED_USER_ID is not None:
        return _CACHED_USER_ID
    _USER_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _USER_ID_PATH.exists():
        try:
            data = json.loads(_USER_ID_PATH.read_text())
            _CACHED_USER_ID = data.get("user_id", "")
            if _CACHED_USER_ID:
                return _CACHED_USER_ID
        except Exception:
            pass
    uid = str(uuid.uuid4())
    _USER_ID_PATH.write_text(json.dumps({"user_id": uid}, indent=2))
    _CACHED_USER_ID = uid
    return uid
