from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Control Plane API")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="dev")
    api_v1_prefix: str = Field(default="/api/v1")
    storage_backend: str = Field(default="database")
    database_url: str = Field(default="sqlite:///./control_plane.db")
    database_echo: bool = Field(default=False)
    artifacts_root: str = Field(default=".artifacts")
    agent_registration_token: str = Field(default="bootstrap-secret")
    inventory_retention_limit: int = Field(default=5, ge=1)
    execution_retention_days: int = Field(default=30, ge=1)
    audit_retention_days: int = Field(default=90, ge=1)
    admin_jwt_secret: str = Field(default="dev-admin-secret")
    admin_access_token_ttl_seconds: int = Field(default=3600)
    admin_refresh_token_ttl_seconds: int = Field(default=86400)

    model_config = SettingsConfigDict(
        env_prefix="CONTROL_PLANE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
