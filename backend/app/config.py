"""Application configuration loaded from environment variables.

We use pydantic-settings so the same Settings object reads from .env in
local dev and from real env vars in Docker. The `APP_MODE` flag is the
master switch between live external APIs and offline fixture mode, which
matters because Google Maps and Solar API calls cost real dollars.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Read once at startup, then cached."""

    # External API keys. Empty strings are tolerated so the app boots in
    # mock mode without credentials.
    google_maps_api_key: str = ""
    anthropic_api_key: str = ""

    # Pipeline behavior
    app_mode: Literal["mock", "live"] = "mock"
    default_radius_miles: float = 15.0
    max_results: int = 100

    # Storage and logging
    cache_db_path: str = "/app/cache.db"
    log_level: str = "INFO"
    log_file: str = "/app/logs/app.log"

    # CORS
    frontend_origin: str = "http://localhost:5173"

    # Paths to ship-with-app data files. Resolved relative to the app dir.
    data_dir: Path = Path(__file__).parent / "data"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_live(self) -> bool:
        """True when the app should hit real external APIs."""
        return self.app_mode == "live"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor. Use this everywhere instead of constructing Settings directly."""
    return Settings()
