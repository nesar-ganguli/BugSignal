from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BugSignal AI"
    environment: str = "development"
    api_prefix: str = ""
    frontend_origin: str = "http://localhost:5173"
    cors_origins: str = ""
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    log_level: str = "INFO"
    stale_workflow_timeout_seconds: int = 900
    max_request_size_bytes: int = 10 * 1024 * 1024
    max_ticket_upload_size_bytes: int = 5 * 1024 * 1024
    rate_limit_enabled: bool = True
    expensive_rate_limit_requests: int = 10
    expensive_rate_limit_window_seconds: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        configured = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        return configured or [self.frontend_origin]

    @property
    def allowed_host_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"

    oidc_enabled: bool = False
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_algorithms: str = "RS256"
    oidc_organization_claim: str = "org_id"
    oidc_roles_claim: str = "roles"

    database_url: str = "sqlite:///./bugsignal.db"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: int = 30
    chroma_persist_dir: str = "./chroma_data"
    cloned_repos_dir: str = "./repos"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    github_token: str | None = Field(default=None)
    github_repo_owner: str | None = Field(default=None)
    github_repo_name: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
