import sqlite3
import time

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_size=10 if _is_sqlite and ":memory:" not in settings.database_url else 5,
    max_overflow=20 if _is_sqlite and ":memory:" not in settings.database_url else 10,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def commit_with_retry(db: Session, max_attempts: int = 3, backoff: float = 0.05) -> None:
    """Commit, retrying on 'database is locked' (SQLite writer contention under WAL)."""
    attempt = 0
    while True:
        try:
            db.commit()
            return
        except OperationalError as exc:
            if "database is locked" in str(exc) and attempt < max_attempts - 1:
                attempt += 1
                time.sleep(backoff * attempt)
                continue
            raise
