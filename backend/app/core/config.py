# from functools import lru_cache
# import json
# from typing import Literal, Optional
# from pydantic_settings import BaseSettings, SettingsConfigDict
# from pydantic import field_validator, SecretStr


# class Settings(BaseSettings):
#     model_config = SettingsConfigDict(
#         env_file=".env",
#         env_file_encoding="utf-8",
#         case_sensitive=False,
#         extra="ignore",
#     )

#     APP_NAME: str = "TissaTech AI Agent"
#     APP_VERSION: str = "1.0.0"
#     ENVIRONMENT: Literal["development", "staging", "production"] = "development"
#     DEBUG: bool = False
#     SECRET_KEY: SecretStr = SecretStr("dev-secret-key-change-in-production-32chars")

#     API_PREFIX: str = "/api/v1"
#     ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]
#     DOCS_URL: Optional[str] = "/docs"

#     DATABASE_URL: str = "postgresql+asyncpg://tissatech:password@localhost:5432/tissatech"
#     DATABASE_POOL_SIZE: int = 10
#     DATABASE_MAX_OVERFLOW: int = 5
#     DATABASE_POOL_TIMEOUT: int = 30

#     REDIS_URL: str = "redis://localhost:6379/0"
#     REDIS_CACHE_TTL: int = 3600

#     JWT_ALGORITHM: str = "HS256"
#     ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
#     REFRESH_TOKEN_EXPIRE_DAYS: int = 7

#     AWS_REGION: str = "us-east-1"
#     AWS_ACCESS_KEY_ID: Optional[SecretStr] = None
#     AWS_SECRET_ACCESS_KEY: Optional[SecretStr] = None
#     BEDROCK_AGENT_REGION: str = ""
#     BEDROCK_FALLBACK_REGIONS: list[str] = []
#     BEDROCK_REGION_HINT_HEADER: str = "X-Bedrock-Region"
#     BEDROCK_COUNTRY_HEADER: str = "CloudFront-Viewer-Country"
#     BEDROCK_CONNECT_TIMEOUT_SECONDS: int = 4
#     BEDROCK_READ_TIMEOUT_SECONDS: int = 60
#     BEDROCK_MAX_POOL_CONNECTIONS: int = 150
#     BEDROCK_RETRY_MAX_ATTEMPTS: int = 2
#     BEDROCK_RETRIEVAL_RESULTS: int = 12

#     # Tenant isolation hardening:
#     # - OFF by default to prevent accidental cross-workspace data leakage.
#     # - If enabled in local dev, multiple workspaces may reuse same global KB/agent.
#     BEDROCK_ALLOW_GLOBAL_FALLBACK: bool = False

#     # Registration hardening:
#     # - By default, disallow registering into an existing workspace slug.
#     # - Prevent ambiguous cross-workspace login by enforcing globally unique email.
#     ALLOW_WORKSPACE_JOIN_ON_REGISTER: bool = False
#     ENFORCE_GLOBAL_UNIQUE_EMAIL: bool = True

#     # ── Bedrock defaults (used as fallback when workspace has no provisioned resources) ──
#     BEDROCK_AGENT_ID: str = ""
#     BEDROCK_AGENT_ALIAS_ID: str = "TSTALIASID"
#     BEDROCK_MODEL_ID: str = "anthropic.claude-3-haiku-20240307-v1:0"
#     BEDROCK_KNOWLEDGE_BASE_ID: str = ""
#     BEDROCK_MAX_TOKENS: int = 2048

#     # ── Bedrock provisioning (used when auto-creating per-workspace resources) ──
#     # The S3 bucket where crawled pages are stored.
#     # Per-org prefix: workspaces/{workspace_id}/
#     # Example: tissatech-kb-data
#     S3_KNOWLEDGE_BASE_BUCKET: str = ""

#     # IAM role ARN that Bedrock uses to read from S3 and invoke the foundation model.
#     # This role needs: AmazonBedrockFullAccess + S3 read on S3_KNOWLEDGE_BASE_BUCKET.
#     # Example: arn:aws:iam::123456789:role/BedrockAgentRole
#     BEDROCK_AGENT_ROLE_ARN: str = ""
#     BEDROCK_OPENSEARCH_COLLECTION_ARN: str = ""

#     # Embedding model used when creating a Knowledge Base.
#     BEDROCK_EMBEDDING_MODEL_ID: str = "amazon.titan-embed-text-v2:0"

#     MCP_SERVER_NAME: str = "tissatech-mcp"
#     MCP_HOST: str = "0.0.0.0"
#     MCP_PORT: int = 8001

#     RATE_LIMIT_REQUESTS: int = 60
#     RATE_LIMIT_WINDOW: int = 60

#     CELERY_BROKER_URL: str = "redis://localhost:6379/1"
#     CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

#     MAX_MESSAGE_LENGTH: int = 4096
#     MAX_CONVERSATION_HISTORY: int = 20

#     @field_validator("BEDROCK_FALLBACK_REGIONS", mode="before")
#     @classmethod
#     def parse_bedrock_fallback_regions(cls, value):
#         if value is None:
#             return []
#         if isinstance(value, list):
#             return [str(v).strip() for v in value if str(v).strip()]
#         if isinstance(value, str):
#             raw = value.strip()
#             if not raw:
#                 return []
#             if raw.startswith("["):
#                 try:
#                     parsed = json.loads(raw)
#                     if isinstance(parsed, list):
#                         return [str(v).strip() for v in parsed if str(v).strip()]
#                 except Exception:
#                     pass
#             return [part.strip() for part in raw.split(",") if part.strip()]
#         return []

#     @property
#     def is_production(self) -> bool:
#         return self.ENVIRONMENT == "production"


# @lru_cache
# def get_settings() -> Settings:
#     return Settings()


# settings = get_settings()


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
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    FRONTEND_BASE_URL: str = "http://localhost:3000"
    PASSWORD_RESET_URL_PATH: str = "/reset-password"

    # FIXED: Default to us-east-2 where all resources (agent, KB, S3) live
    AWS_REGION: str = "us-east-2"
    AWS_ACCESS_KEY_ID: Optional[SecretStr] = None
    AWS_SECRET_ACCESS_KEY: Optional[SecretStr] = None

    # FIXED: Agent region hardcoded to us-east-2 — do not set other regions
    BEDROCK_AGENT_REGION: str = "us-east-2"
    # FIXED: No fallback regions — all resources are in us-east-2 only
    BEDROCK_FALLBACK_REGIONS: list[str] = []
    BEDROCK_REGION_HINT_HEADER: str = "X-Bedrock-Region"
    BEDROCK_COUNTRY_HEADER: str = "CloudFront-Viewer-Country"

    # OPTIMIZED: 8s connect timeout (was 4s — too short for cold starts)
    BEDROCK_CONNECT_TIMEOUT_SECONDS: int = 8
    BEDROCK_READ_TIMEOUT_SECONDS: int = 60
    # OPTIMIZED: higher pool for concurrent widget sessions
    BEDROCK_MAX_POOL_CONNECTIONS: int = 200
    BEDROCK_RETRY_MAX_ATTEMPTS: int = 2
    # OPTIMIZED: 5 results is enough and faster than 12
    BEDROCK_RETRIEVAL_RESULTS: int = 5

    # FIXED: Enable global fallback by default so the shared agent (TCQEGI0QQ4)
    # is used when a workspace has no dedicated per-workspace agent provisioned yet.
    # This is safe because retrieval filtering by S3 prefix still isolates workspace data.
    BEDROCK_ALLOW_GLOBAL_FALLBACK: bool = True

    # Registration hardening
    ALLOW_WORKSPACE_JOIN_ON_REGISTER: bool = False
    ENFORCE_GLOBAL_UNIQUE_EMAIL: bool = True

    # ── Bedrock defaults (shared infra — your existing manually-created resources) ──
    BEDROCK_AGENT_ID: str = ""
    BEDROCK_AGENT_ALIAS_ID: str = "TSTALIASID"
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-haiku-20240307-v1:0"
    BEDROCK_KNOWLEDGE_BASE_ID: str = ""
    BEDROCK_MAX_TOKENS: int = 2048

    # ── Bedrock provisioning (auto-creating per-workspace resources) ──
    S3_KNOWLEDGE_BASE_BUCKET: str = ""
    BEDROCK_AGENT_ROLE_ARN: str = ""
    BEDROCK_OPENSEARCH_COLLECTION_ARN: str = ""
    BEDROCK_EMBEDDING_MODEL_ID: str = "amazon.titan-embed-text-v2:0"

    MCP_SERVER_NAME: str = "tissatech-mcp"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8001

    # Public embed/runtime URLs used for script generation.
    WIDGET_PUBLIC_BASE_URL: str = ""
    API_PUBLIC_BASE_URL: str = ""

    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW: int = 60

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    MAX_MESSAGE_LENGTH: int = 4096
    MAX_CONVERSATION_HISTORY: int = 20

    @field_validator("BEDROCK_FALLBACK_REGIONS", mode="before")
    @classmethod
    def parse_bedrock_fallback_regions(cls, value):
        # FIXED: Always return empty — us-east-2 only
        return []

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
