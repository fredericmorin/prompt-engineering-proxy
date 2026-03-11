from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    proxy_host: str = "0.0.0.0"
    proxy_port: int = 8000
    redis_url: str = "redis://localhost:6379"
    database_path: str = "data/proxy.db"
    log_level: str = "info"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
