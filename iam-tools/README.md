# IAM Tools REST Service

REST service in Python that exposes the same IAM operations and JSON payloads as the IAM agent tools.

## Run

```bash
python iam-tools/main.py
```

The service listens on `http://0.0.0.0:8090` by default.

The OpenAPI document is available in [openapi.yaml](openapi.yaml) and from the running service at `GET /openapi.yaml`.

## Docker

Build and run locally:

```bash
docker build -t iam-tools:local iam-tools
docker run --rm -p 8090:8090 iam-tools:local
```

The GitHub Actions workflow publishes the image to:

```text
ghcr.io/dsanchor/specialist-mesh/iam-tools
```

## Operations

| Tool operation | Method | Endpoint | Body |
| --- | --- | --- | --- |
| `get_user` | `GET` | `/users/{user_id}` | None |
| `get_user_permissions` | `GET` | `/users/{user_id}/permissions` | None |
| `create_user` | `POST` | `/users` | `{"user_id":"user_new","email":"new@example.com","display_name":"New User"}` |
| `reset_password` | `POST` | `/users/{user_id}/reset-password` | None |
| `change_password` | `POST` | `/users/{user_id}/change-password` | `{"old_password":"ChangeMe123!","new_password":"NewPass123!"}` |
| `disable_user` | `POST` | `/users/{user_id}/disable` | Optional: `{"reason":"Disabled by administrator"}` |
| `enable_user` | `POST` | `/users/{user_id}/enable` | None |
| `assign_role` | `POST` | `/users/{user_id}/roles/{role}` | None |
| `revoke_role` | `DELETE` | `/users/{user_id}/roles/{role}` | None |

## Examples

```bash
curl http://localhost:8090/users/user_jdoe
curl http://localhost:8090/users/user_jdoe/permissions
curl -X POST http://localhost:8090/users/user_jdoe/reset-password
curl -X POST http://localhost:8090/users/user_jdoe/roles/support
curl -X DELETE http://localhost:8090/users/user_jdoe/roles/support
```
