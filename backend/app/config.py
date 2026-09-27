import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent.parent

# Load backend/.env explicitly (not dotenv's default upward-search) so this
# works the same regardless of the process's cwd. Existing environment
# variables still take precedence over anything in the file.
load_dotenv(_BACKEND_DIR / ".env")

# Anchored to the backend/ directory (not the process's cwd) so the default
# DB always lands in the same place regardless of how/where uvicorn is launched.
_DEFAULT_DB_PATH = _BACKEND_DIR / "app.db"


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
