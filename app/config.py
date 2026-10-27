import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    portal_url: str = os.getenv("URJA_PORTAL_URL", "https://urja-ops.flockenergy.tech").rstrip("/")
    portal_username: str = os.getenv("URJA_USERNAME", "operator@urja.local")
    portal_password: str = os.getenv("URJA_PASSWORD", "urja-ops-2026")
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "900"))
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "15.0"))
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))

settings = Settings()
