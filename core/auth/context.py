from contextvars import ContextVar
from typing import Optional

# This context variable will hold the user_id (as a string) for the current request context.
# It defaults to None if not set.
request_user_id: ContextVar[Optional[str]] = ContextVar("request_user_id", default=None)

def set_current_user_id(user_id: Optional[str]) -> None:
    """Set the user_id for the current request context."""
    request_user_id.set(user_id)

def get_current_user_id() -> Optional[str]:
    """Get the user_id from the current request context."""
    return request_user_id.get()
