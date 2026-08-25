from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_APP_ENVS = ("local", "test", "staging", "production")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Mimir API"
    debug: bool = True
    app_env: str = ""
    stashtab_allow_dev_identity: bool = False
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql://mimir:mimir@localhost:5432/mimir"
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Pokemon TCG API (optional key raises rate limits)
    pokemon_tcg_api_key: str = ""
    # Partner config.USD_TO_CAD_RATE — API market prices are USD
    usd_to_cad_rate: float = 1.43

    # Clerk JWT verification
    clerk_secret_key: str = ""
    clerk_jwt_issuer: str = ""
    clerk_jwt_audience: str = ""
    clerk_authorized_parties: str = ""

    # Web Push stays disabled until all VAPID values are configured.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""
    web_push_allowed_host_suffixes: str = ""
    web_push_max_attempts: int = 8
    web_push_retry_backoff_seconds: int = 30
    notifications_backend_enabled: bool = False

    @field_validator("web_push_allowed_host_suffixes")
    @classmethod
    def reject_custom_push_hosts(cls, value: str) -> str:
        if (value or "").strip():
            raise ValueError(
                "Custom Web Push provider hosts are disabled. "
                "Unset WEB_PUSH_ALLOWED_HOST_SUFFIXES. "
                "Amendment 1.1.2 uses the built-in provider allowlist only."
            )
        return ""

    @property
    def web_push_enabled(self) -> bool:
        subject = self.vapid_subject.strip()
        if not subject or subject.lower() == "mailto:ops@example.com":
            return False
        return bool(self.vapid_public_key.strip() and self.vapid_private_key.strip() and subject)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def clerk_authorized_party_list(self) -> list[str]:
        return [p.strip() for p in self.clerk_authorized_parties.split(",") if p.strip()]

    @property
    def parsed_app_env(self) -> str | None:
        raw = (self.app_env or "").strip().lower()
        if raw in SUPPORTED_APP_ENVS:
            return raw
        return None

    @property
    def dev_identity_bypass_allowed(self) -> bool:
        """Headers may substitute identity only for explicit local/test bypass.

        DEBUG alone never authorizes this. Missing, invalid, staging, and
        production APP_ENV values never enable it.
        """
        if self.parsed_app_env not in ("local", "test"):
            return False
        return bool(self.stashtab_allow_dev_identity)


settings = Settings()
