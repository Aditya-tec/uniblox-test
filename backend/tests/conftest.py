import sys
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Fresh app + fresh SQLite file per test.

    Config and the SQLAlchemy engine are module-level singletons (per spec:
    one shared engine, WAL pragma set on connect), so isolating tests means
    reloading the `app` package against a fresh DATABASE_URL rather than
    reusing one process-wide engine across tests.
    """
    db_path = tmp_path / f"test_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("N", "5")
    monkeypatch.setenv("X", "10")

    for mod_name in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
        del sys.modules[mod_name]

    from app.main import app
    from app.seed import seed

    seed()

    with TestClient(app) as test_client:
        yield test_client

    for mod_name in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
        del sys.modules[mod_name]
