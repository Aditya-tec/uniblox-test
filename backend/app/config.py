import os
from dataclasses import dataclass, field
from pathlib import Path

# Anchored to the backend/ directory (not the process's cwd) so the default
# DB always lands in the same place regardless of how/where uvicorn is launched.
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "app.db"


@dataclass
class Settings:
    n: int = int(os.getenv("N", "5"))
    x: int = int(os.getenv("X", "10"))
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        ]
    )


settings = Settings()
