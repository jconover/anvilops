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

    # AWX Configuration
    AWX_BASE_URL: str = "http://localhost:8052"
    AWX_USERNAME: str = "admin"
    AWX_PASSWORD: str = "password"
    AWX_VERIFY_SSL: bool = False
    AWX_JOB_TIMEOUT: int = 600
    AWX_POLL_INTERVAL: int = 10
    AWX_ORGANIZATION_ID: int = 1

    # Puppet Enterprise Configuration
    PUPPET_BASE_URL: str = "https://puppet.anvilops.internal"
    PUPPET_API_TOKEN: str = ""
    PUPPET_VERIFY_SSL: bool = False
    PUPPET_CA_PORT: int = 8140
    PUPPET_CLASSIFIER_PORT: int = 4433
    PUPPET_PUPPETDB_PORT: int = 8081
    PUPPET_ORCHESTRATOR_PORT: int = 8143
    PUPPET_NODE_CHECKIN_TIMEOUT: int = 600
    PUPPET_NODE_CHECKIN_POLL: int = 30
    PUPPET_DEFAULT_ENVIRONMENT: str = "production"
    PUPPET_CERTNAME_DOMAIN: str = "anvilops.internal"

    # Slack Configuration
    SLACK_WEBHOOK_URL: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_ENABLED: bool = False
    SLACK_CHANNEL: str = "#anvilops-builds"
    SLACK_APP_URL: str = "http://localhost:3000"  # Frontend URL for links

    # ServiceNow CMDB Integration
    SERVICENOW_INSTANCE_URL: str = ""
    SERVICENOW_USERNAME: str = ""
    SERVICENOW_PASSWORD: str = ""
    SERVICENOW_ENABLED: bool = False
    SERVICENOW_TABLE: str = "cmdb_ci_server"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
