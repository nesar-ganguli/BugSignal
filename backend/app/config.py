from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BugSignal AI"
    api_prefix: str = ""
    frontend_origin: str = "http://localhost:5173"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    database_url: str = "sqlite:///./bugsignal.db"
    chroma_persist_dir: str = "./chroma_data"
    cloned_repos_dir: str = "./repos"

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
