from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


OPENAPI_DOCUMENT = Path(__file__).with_name("openapi.yaml")


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class UserRecord:
    user_id: str
    email: str
    display_name: str
    status: str = "active"
    password: str = "ChangeMe123!"
    created_at: str = field(default_factory=_timestamp)


USERS: dict[str, UserRecord] = {}
USER_ROLES: dict[str, set[str]] = {}
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": ["users:create", "users:disable", "roles:assign", "roles:revoke"],
    "billing-admin": ["billing:read", "billing:write", "billing:refund"],
    "support": ["tickets:read", "tickets:write"],
    "reader": ["knowledge:read"],
}


def _seed_iam_data() -> None:
    sample_users = [
        UserRecord(user_id="user_jdoe", email="john.doe@acme.com", display_name="John Doe", password="Acm3S3cur3!"),
        UserRecord(user_id="user_asmith", email="alice.smith@acme.com", display_name="Alice Smith", password="Al1c3Pass!"),
        UserRecord(user_id="user_bwayne", email="bruce@wayne-ent.com", display_name="Bruce Wayne", password="B4tC4v3!"),
        UserRecord(user_id="user_ckent", email="clark.kent@globex.com", display_name="Clark Kent", password="Krypt0n1te!"),
        UserRecord(user_id="user_dprince", email="diana.prince@globex.com", display_name="Diana Prince", status="disabled", password="Th3m1sc1ra!"),
    ]
    for user in sample_users:
        USERS[user.user_id] = user

    USER_ROLES.update(
        {
            "user_jdoe": {"admin", "billing-admin"},
            "user_asmith": {"support", "reader"},
            "user_bwayne": {"admin"},
            "user_ckent": {"reader", "support"},
            "user_dprince": {"reader"},
        }
    )


_seed_iam_data()


def _lookup_user(user_id: str) -> UserRecord | None:
    return USERS.get(user_id)


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


def reset_password(user_id: str) -> str:
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


def change_password(user_id: str, old_password: str, new_password: str) -> str:
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


def create_user(user_id: str, email: str, display_name: str) -> str:
    if user_id in USERS:
        return f'{{"error":"User {user_id} already exists"}}'
    USERS[user_id] = UserRecord(user_id=user_id, email=email, display_name=display_name)
    USER_ROLES.setdefault(user_id, {"reader"})
    return _json_response(asdict(USERS[user_id]))


def disable_user(user_id: str, reason: str = "Disabled by administrator") -> str:
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


def enable_user(user_id: str) -> str:
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


def assign_role(user_id: str, role: str) -> str:
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


def revoke_role(user_id: str, role: str) -> str:
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


def get_user_permissions(user_id: str) -> str:
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


def get_user(user_id: str) -> str:
    user = _lookup_user(user_id)
    if not user:
        return f'{{"error":"User {user_id} not found"}}'
    roles = USER_ROLES.get(user_id, set())
    return _json_response(
        {
            "user_id": user.user_id,
            "email": user.email,
            "display_name": user.display_name,
            "status": user.status,
            "roles": sorted(roles),
            "created_at": user.created_at,
        }
    )


class IAMRequestHandler(BaseHTTPRequestHandler):
    server_version = "IAMToolsREST/1.0"

    def do_GET(self) -> None:
        path_parts = self._path_parts()
        if path_parts == ["health"]:
            self._send_json(_json_response({"status": "ok"}))
            return
        if path_parts == ["openapi.yaml"]:
            self._send_text(OPENAPI_DOCUMENT.read_text(encoding="utf-8"), "application/yaml")
            return
        if len(path_parts) == 2 and path_parts[0] == "users":
            self._send_json(get_user(path_parts[1]))
            return
        if len(path_parts) == 3 and path_parts[0] == "users" and path_parts[2] == "permissions":
            self._send_json(get_user_permissions(path_parts[1]))
            return
        self._send_not_found()

    def do_POST(self) -> None:
        path_parts = self._path_parts()
        body = self._read_json_body()

        if path_parts == ["users"]:
            self._send_json(create_user(body.get("user_id", ""), body.get("email", ""), body.get("display_name", "")))
            return
        if len(path_parts) == 3 and path_parts[0] == "users" and path_parts[2] == "reset-password":
            self._send_json(reset_password(path_parts[1]))
            return
        if len(path_parts) == 3 and path_parts[0] == "users" and path_parts[2] == "change-password":
            self._send_json(change_password(path_parts[1], body.get("old_password", ""), body.get("new_password", "")))
            return
        if len(path_parts) == 3 and path_parts[0] == "users" and path_parts[2] == "disable":
            self._send_json(disable_user(path_parts[1], body.get("reason", "Disabled by administrator")))
            return
        if len(path_parts) == 3 and path_parts[0] == "users" and path_parts[2] == "enable":
            self._send_json(enable_user(path_parts[1]))
            return
        if len(path_parts) == 4 and path_parts[0] == "users" and path_parts[2] == "roles":
            self._send_json(assign_role(path_parts[1], path_parts[3]))
            return
        self._send_not_found()

    def do_DELETE(self) -> None:
        path_parts = self._path_parts()
        if len(path_parts) == 4 and path_parts[0] == "users" and path_parts[2] == "roles":
            self._send_json(revoke_role(path_parts[1], path_parts[3]))
            return
        self._send_not_found()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _path_parts(self) -> list[str]:
        path = urlparse(self.path).path.strip("/")
        return [unquote(part) for part in path.split("/") if part]

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw_body = self.rfile.read(length).decode("utf-8")
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            return {}
        if isinstance(body, dict):
            return body
        return {}

    def _send_json(self, payload: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_text(payload, "application/json", status)

    def _send_text(self, payload: str, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        response = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def _send_not_found(self) -> None:
        self._send_json(_json_response({"error": "Endpoint not found"}), HTTPStatus.NOT_FOUND)


def run(host: str = "0.0.0.0", port: int = 8090) -> None:
    server = ThreadingHTTPServer((host, port), IAMRequestHandler)
    print(f"IAM tools REST service listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
