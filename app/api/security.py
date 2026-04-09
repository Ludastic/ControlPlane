from __future__ import annotations

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


admin_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="AdminBearerAuth",
    description="Admin access token in the form: Bearer <access_token>",
)

agent_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="AgentBearerAuth",
    description="Agent token in the form: Bearer <agent_token>",
)


def build_authorization_header(credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials is None:
        return None
    return f"{credentials.scheme} {credentials.credentials}"
