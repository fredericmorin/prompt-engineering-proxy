from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PREN_PROXY_", env_file=".env")

    PROXY_HOST: str = "0.0.0.0"
    PROXY_PORT: int = 8000
    REDIS_URL: str
    DATA_PATH: Path = Path("data")
    LOG_LEVEL: str = "info"
    CORS_ORIGINS: str = "http://localhost:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def _get_settings() -> Settings:
    return Settings()  # type: ignore


class _LazyProxy:
    """Defers Settings instantiation (and env-var reads) until first attribute access."""

    def __getattr__(self, name: str) -> object:
        return getattr(_get_settings(), name)


settings: Settings = _LazyProxy()  # type: ignore
