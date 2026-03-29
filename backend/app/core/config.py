from functools import lru_cache
import json
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "TissaTech AI Agent"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: SecretStr = SecretStr("dev-secret-key-change-in-production-32chars")

    API_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]
    DOCS_URL: Optional[str] = "/docs"

    DATABASE_URL: str = "postgresql+asyncpg://tissatech:password@localhost:5432/tissatech"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 5
    DATABASE_POOL_TIMEOUT: int = 30

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[SecretStr] = None
    AWS_SECRET_ACCESS_KEY: Optional[SecretStr] = None

    # Tenant isolation hardening:
    # - OFF by default to prevent accidental cross-workspace data leakage.
    # - If enabled in local dev, multiple workspaces may reuse same global KB/agent.
    BEDROCK_ALLOW_GLOBAL_FALLBACK: bool = False

    # Registration hardening:
    # - By default, disallow registering into an existing workspace slug.
    # - Prevent ambiguous cross-workspace login by enforcing globally unique email.
    ALLOW_WORKSPACE_JOIN_ON_REGISTER: bool = False
    ENFORCE_GLOBAL_UNIQUE_EMAIL: bool = True

    # ── Bedrock defaults (used as fallback when workspace has no provisioned resources) ──
    BEDROCK_AGENT_ID: str = ""
    BEDROCK_AGENT_ALIAS_ID: str = "TSTALIASID"
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-haiku-20240307-v1:0"
    BEDROCK_KNOWLEDGE_BASE_ID: str = ""
    BEDROCK_MAX_TOKENS: int = 2048

    # ── Bedrock provisioning (used when auto-creating per-workspace resources) ──
    # The S3 bucket where crawled pages are stored.
    # Per-org prefix: workspaces/{workspace_id}/
    # Example: tissatech-kb-data
    S3_KNOWLEDGE_BASE_BUCKET: str = ""

    # IAM role ARN that Bedrock uses to read from S3 and invoke the foundation model.
    # This role needs: AmazonBedrockFullAccess + S3 read on S3_KNOWLEDGE_BASE_BUCKET.
    # Example: arn:aws:iam::123456789:role/BedrockAgentRole
    BEDROCK_AGENT_ROLE_ARN: str = ""
    BEDROCK_OPENSEARCH_COLLECTION_ARN: str = ""

    # Embedding model used when creating a Knowledge Base.
    BEDROCK_EMBEDDING_MODEL_ID: str = "amazon.titan-embed-text-v2:0"

    MCP_SERVER_NAME: str = "tissatech-mcp"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8001

    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW: int = 60

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    MAX_MESSAGE_LENGTH: int = 4096
    MAX_CONVERSATION_HISTORY: int = 20

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
