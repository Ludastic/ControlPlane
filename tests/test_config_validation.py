from app.core.config_validation import validate_runtime_settings
from app.core.errors import AppError
from app.core.settings import Settings


def test_validate_runtime_settings_allows_dev_defaults() -> None:
    validate_runtime_settings(
        Settings(
            environment="dev",
            admin_jwt_secret="dev-admin-secret",
            agent_registration_token="bootstrap-secret",
        )
    )


def test_validate_runtime_settings_rejects_default_admin_secret_in_production() -> None:
    try:
        validate_runtime_settings(
            Settings(
                environment="production",
                admin_jwt_secret="dev-admin-secret",
                agent_registration_token="custom-registration-token",
            )
        )
    except AppError as exc:
        assert exc.code == "INVALID_RUNTIME_CONFIGURATION"
    else:
        raise AssertionError("Expected production config validation to fail")


def test_validate_runtime_settings_rejects_default_registration_token_in_production() -> None:
    try:
        validate_runtime_settings(
            Settings(
                environment="production",
                admin_jwt_secret="custom-admin-secret",
                agent_registration_token="bootstrap-secret",
            )
        )
    except AppError as exc:
        assert exc.code == "INVALID_RUNTIME_CONFIGURATION"
    else:
        raise AssertionError("Expected production config validation to fail")
