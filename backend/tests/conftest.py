import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def isolated_local_db(tmp_path, monkeypatch):
    """Every test gets its own throwaway SQLite file and a clean client
    singleton, so tests never see each other's writes."""
    monkeypatch.setenv("LOCAL_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    import app.db.supabase_client as db_module

    db_module._client_singleton = None
    yield
    db_module._client_singleton = None