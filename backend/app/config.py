from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str
    REDIS_URL: str = ""
    OPENAI_API_KEY: str = ""
    DEFAULT_MODEL: str = "gpt-5.6"
    ENCRYPTION_KEY: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GSC_SITE_URL: str = ""
    GA4_PROPERTY_ID: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = ""
    GOOGLE_OAUTH_STATE_SECRET: str = ""
    GITHUB_TOKEN: str = ""
    GITHUB_OWNER: str = ""
    GITHUB_REPO: str = ""
    GITHUB_BASE_BRANCH: str = "main"
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_OAUTH_REDIRECT_URI: str = ""
    GITHUB_OAUTH_STATE_SECRET: str = ""
    VERCEL_TOKEN: str = ""
    VERCEL_PROJECT_ID: str = ""
    VERCEL_TEAM_ID: str = ""
    VERCEL_CLIENT_ID: str = ""
    VERCEL_CLIENT_SECRET: str = ""
    VERCEL_OAUTH_REDIRECT_URI: str = ""
    VERCEL_OAUTH_STATE_SECRET: str = ""
    VERCEL_INTEGRATION_SLUG: str = "autonomous-web-company"
    DASHBOARD_URL: str = "https://autonomous-web-company.vercel.app"
    CORS_ORIGINS: str = "https://autonomous-web-company.vercel.app"
    COOKIE_SECURE: bool = True
    SESSION_TTL_HOURS: int = 24
    RATE_LIMIT_PER_MINUTE: int = 60
    AUTONOMY_DRY_RUN: bool = True
    MAX_FILES_CHANGED: int = 40
    MAX_ADDED_LINES: int = 2000
    MAX_DELETED_LINES: int = 1000
    SCHEDULER_HOURS: int = 24
    WORKSPACE_ROOT: str = "./workspaces"
    PROVISIONING_ENABLED: bool = True
    ALLOW_REPO_CREATION: bool = True
    ALLOW_VERCEL_PROVISIONING: bool = True
    ALLOW_DOMAIN_BINDING: bool = True
    AUTONOMY_MAX_PROJECTS_PER_RUN: int = 5

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, value: str) -> str:
        if not value.strip():
            return value
        from cryptography.fernet import Fernet
        try: Fernet(value.encode("ascii"))
        except Exception as exc: raise ValueError("ENCRYPTION_KEY must be a valid Fernet key") from exc
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip().rstrip("/") for x in self.CORS_ORIGINS.split(",") if x.strip()]

@lru_cache
def settings() -> Settings:
    return Settings()
