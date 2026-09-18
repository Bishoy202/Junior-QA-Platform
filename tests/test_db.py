import pytest

from app import db


def test_resolve_db_path_uses_data_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "volume"))

    assert db.resolve_db_path() == str((tmp_path / "volume" / "jobs.db").resolve())


def test_resolve_db_path_prefers_sqlite_database_url(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'jobs.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "ignored"))

    assert db.resolve_db_path() == str((tmp_path / "jobs.db").resolve())


d
