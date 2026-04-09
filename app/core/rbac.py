READ = "read"
WRITE = "write"
ADMIN = "admin"


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {READ, WRITE, ADMIN},
    "operator": {READ, WRITE},
    "auditor": {READ},
}


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
