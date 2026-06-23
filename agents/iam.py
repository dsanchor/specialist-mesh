from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from agent_framework import Agent, tool
from pydantic import BaseModel, Field


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


class UserRecord(BaseModel):
    user_id: str
    email: str
    display_name: str
    status: str = "active"
    password: str = "ChangeMe123!"
    created_at: str = Field(default_factory=_timestamp)


USERS: dict[str, UserRecord] = {}
USER_ROLES: dict[str, set[str]] = {}
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": ["users:create", "users:disable", "roles:assign", "roles:revoke"],
    "billing-admin": ["billing:read", "billing:write", "billing:refund"],
    "support": ["tickets:read", "tickets:write"],
    "reader": ["knowledge:read"],
}


def _lookup_user(user_id: str) -> UserRecord | None:
    return USERS.get(user_id)


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


@tool(approval_mode="never_require")
def reset_password(user_id: str) -> str:
    """Reset a user's password and issue a temporary password."""
    user = _lookup_user(user_id)
    if not user:
        return f'{{"error":"User {user_id} not found"}}'
    user.password = "TempPass123!"
    return _json_response(
        {
            "user_id": user_id,
            "temporary_password": user.password,
            "reset_at": _timestamp(),
        }
    )


@tool(approval_mode="never_require")
def change_password(user_id: str, old_password: str, new_password: str) -> str:
    """Change a user's password when the old password matches."""
    user = _lookup_user(user_id)
    if not user:
        return f'{{"error":"User {user_id} not found"}}'
    if user.password != old_password:
        return f'{{"error":"Old password does not match for user {user_id}"}}'
    user.password = new_password
    return _json_response(
        {
            "user_id": user_id,
            "changed_at": _timestamp(),
            "status": "password_updated",
        }
    )


@tool(approval_mode="never_require")
def create_user(user_id: str, email: str, display_name: str) -> str:
    """Create a new user account."""
    if user_id in USERS:
        return f'{{"error":"User {user_id} already exists"}}'
    USERS[user_id] = UserRecord(user_id=user_id, email=email, display_name=display_name)
    USER_ROLES.setdefault(user_id, {"reader"})
    return USERS[user_id].model_dump_json(indent=2)


@tool(approval_mode="never_require")
def disable_user(user_id: str, reason: str = "Disabled by administrator") -> str:
    """Disable a user account."""
    user = _lookup_user(user_id)
    if not user:
        return f'{{"error":"User {user_id} not found"}}'
    user.status = "disabled"
    return _json_response(
        {
            "user_id": user_id,
            "status": user.status,
            "reason": reason,
            "updated_at": _timestamp(),
        }
    )


@tool(approval_mode="never_require")
def enable_user(user_id: str) -> str:
    """Enable a disabled user account."""
    user = _lookup_user(user_id)
    if not user:
        return f'{{"error":"User {user_id} not found"}}'
    user.status = "active"
    return _json_response(
        {
            "user_id": user_id,
            "status": user.status,
            "updated_at": _timestamp(),
        }
    )


@tool(approval_mode="never_require")
def assign_role(user_id: str, role: str) -> str:
    """Assign a role to a user."""
    user = _lookup_user(user_id)
    if not user:
        return f'{{"error":"User {user_id} not found"}}'
    roles = USER_ROLES.setdefault(user_id, set())
    roles.add(role)
    return _json_response(
        {
            "user_id": user_id,
            "roles": sorted(roles),
            "updated_at": _timestamp(),
        }
    )


@tool(approval_mode="never_require")
def revoke_role(user_id: str, role: str) -> str:
    """Revoke a role from a user."""
    user = _lookup_user(user_id)
    if not user:
        return f'{{"error":"User {user_id} not found"}}'
    roles = USER_ROLES.setdefault(user_id, set())
    roles.discard(role)
    return _json_response(
        {
            "user_id": user_id,
            "roles": sorted(roles),
            "updated_at": _timestamp(),
        }
    )


@tool(approval_mode="never_require")
def get_user_permissions(user_id: str) -> str:
    """Get effective permissions for a user based on assigned roles."""
    user = _lookup_user(user_id)
    if not user:
        return f'{{"error":"User {user_id} not found"}}'
    roles = USER_ROLES.get(user_id, set())
    permissions = sorted({permission for role in roles for permission in ROLE_PERMISSIONS.get(role, [])})
    return _json_response(
        {
            "user_id": user_id,
            "roles": sorted(roles),
            "permissions": permissions,
            "retrieved_at": _timestamp(),
        }
    )


def create_iam_agent(client: Any) -> Agent:
    return Agent(
        name="iam_specialist",
        client=client,
        instructions=(
            "You are the IAM specialist. Handle identity, account lifecycle, password, and "
            "role management requests only by using the provided tools. Finish the IAM task "
            "and then hand control back to the coordinator."
        ),
        tools=[
            reset_password,
            change_password,
            create_user,
            disable_user,
            enable_user,
            assign_role,
            revoke_role,
            get_user_permissions,
        ],
        default_options={"store": False},
        require_per_service_call_history_persistence=True,
    )
