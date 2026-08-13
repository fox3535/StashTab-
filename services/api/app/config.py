from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Mimir API"
    debug: bool = True
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql://mimir:mimir@localhost:5432/mimir"
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Pokemon TCG API (optional key raises rate limits)
    pokemon_tcg_api_key: str = ""
    # Partner config.USD_TO_CAD_RATE — API market prices are USD
    usd_to_cad_rate: float = 1.43

    # Clerk JWT verification (wire up in Phase 1)
    clerk_secret_key: str = ""
    clerk_jwt_issuer: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
