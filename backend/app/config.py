import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    n: int = int(os.getenv("N", "5"))
    x: int = int(os.getenv("X", "10"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        ]
    )


settings = Settings()
