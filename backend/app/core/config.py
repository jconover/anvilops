"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://anvilops:anvilops@localhost:5432/anvilops"
    REDIS_URL: str = "redis://localhost:6379/0"
    TERRAFORM_WORK_DIR: str = "/tmp/terraform"
    AWS_DEFAULT_REGION: str = "us-east-1"
    ALLOWED_REGIONS: list[str] = ["us-east-1", "us-west-2"]
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AnvilOps"
    DEBUG: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
