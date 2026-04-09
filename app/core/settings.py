from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Control Plane API")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="dev")
    api_v1_prefix: str = Field(default="/api/v1")

    model_config = SettingsConfigDict(
        env_prefix="CONTROL_PLANE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
