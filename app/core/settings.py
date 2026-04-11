from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Control Plane API")
    app_version: str = Field(default="0.1.0")
    app_description: str = Field(default="Control Plane backend for agent configuration management.")
    environment: str = Field(default="dev")
    api_v1_prefix: str = Field(default="/api/v1")
    openapi_url: str = Field(default="/openapi.json")
    docs_url: str = Field(default="/docs")
    redoc_url: str = Field(default="/redoc")
    storage_backend: str = Field(default="database")
    database_url: str = Field(default="sqlite:///./control_plane.db")
    database_echo: bool = Field(default=False)
    artifact_storage_backend: str = Field(default="local")
    artifacts_root: str = Field(default=".artifacts")
    s3_endpoint_url: str | None = Field(default=None)
    s3_bucket: str | None = Field(default=None)
    s3_access_key: str | None = Field(default=None)
    s3_secret_key: str | None = Field(default=None)
    s3_region: str = Field(default="us-east-1")
    s3_force_path_style: bool = Field(default=True)
    agent_registration_token: str = Field(default="bootstrap-secret")
    inventory_retention_limit: int = Field(default=5, ge=1)
    execution_retention_days: int = Field(default=30, ge=1)
    audit_retention_days: int = Field(default=90, ge=1)
    admin_jwt_secret: str = Field(default="dev-admin-secret")
    admin_access_token_ttl_seconds: int = Field(default=3600)
    admin_refresh_token_ttl_seconds: int = Field(default=86400)
    bootstrap_admin_username: str | None = Field(default=None)
    bootstrap_admin_password: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_prefix="CONTROL_PLANE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
