from __future__ import annotations

import io
import sqlite3
import urllib.error

import pytest

from engine.providers import gemini_webapi as gemini


@pytest.mark.parametrize("error", [TimeoutError("timed out"), urllib.error.URLError(TimeoutError("timed out")),
                                  RuntimeError("database is locked"), RuntimeError("502 Bad Gateway")])
def test_recoverable_error_gets_one_heal_and_retry(monkeypatch, error):
    events = []
    monkeypatch.setattr(gemini, "ensure_server_running", lambda: events.append("ensure"))
    monkeypatch.setattr(gemini, "heal_gemini_server", lambda: events.append("heal"))

    def open_request(*args, **kwargs):
        events.append("post")
        if events.count("post") == 1:
            raise error
        return io.BytesIO(b'{"ok": true}')

    monkeypatch.setattr(gemini.urllib.request, "urlopen", open_request)
    assert gemini._post_with_retry({}) == {"ok": True}
    assert events == ["ensure", "post", "heal", "post"]


def test_retry_is_bounded_and_propagates_failure(monkeypatch):
    events = []
    monkeypatch.setattr(gemini, "ensure_server_running", lambda: None)
    monkeypatch.setattr(gemini, "heal_gemini_server", lambda: events.append("heal"))
    def fail(*args, **kwargs):
        events.append("post")
        raise TimeoutError("timed out")
    monkeypatch.setattr(gemini.urllib.request, "urlopen", fail)
    with pytest.raises(TimeoutError):
        gemini._post_with_retry({})
    assert events == ["post", "heal", "post"]


def test_nonrecoverable_error_does_not_restart(monkeypatch):
    monkeypatch.setattr(gemini, "ensure_server_running", lambda: None)
    monkeypatch.setattr(gemini, "heal_gemini_server", lambda: pytest.fail("unexpected recovery"))
    def fail(*args, **kwargs):
        raise ValueError("unrelated error")
    monkeypatch.setattr(gemini.urllib.request, "urlopen", fail)
    with pytest.raises(ValueError):
        gemini._post_with_retry({})


def test_heal_delegates_one_sync_to_startup_and_preserves_requested_port(monkeypatch):
    events = []
    monkeypatch.setattr(gemini, "kill_server", lambda: events.append("stop"))
    monkeypatch.setattr(gemini, "check_and_repair_db", lambda: events.append("check"))
    monkeypatch.setattr(gemini, "sync_cookies_sync", lambda *a, **k: pytest.fail("duplicate sync"))
    monkeypatch.setattr(gemini, "ensure_server_running", lambda **kw: events.append(kw))
    gemini.heal_gemini_server(cdp_port=1234)
    assert events == ["stop", "check", {"cdp_port": 1234, "force_refresh": True}]


def test_locked_database_and_sidecars_are_preserved(monkeypatch, tmp_path):
    vendor = tmp_path / "vendor"
    (vendor / "data").mkdir(parents=True)
    db = vendor / "data" / "gemini.db"
    with sqlite3.connect(db) as conn:
        conn.execute("create table existing (x)")
    monkeypatch.setattr(gemini, "VENDOR_DIR", vendor)
    monkeypatch.setattr(gemini.config, "ROOT", tmp_path / "other")
    conn = sqlite3.connect(db)
    try:
        conn.execute("begin exclusive")
        with pytest.raises(RuntimeError, match="files preserved"):
            gemini.check_and_repair_db()
        assert db.exists()
    finally:
        conn.rollback()
        conn.close()
    gemini.check_and_repair_db()
    with sqlite3.connect(db) as conn:
        assert conn.execute("select count(*) from existing").fetchone() == (0,)


def test_corrupt_database_and_wal_are_preserved(monkeypatch, tmp_path):
    vendor = tmp_path / "vendor"
    (vendor / "data").mkdir(parents=True)
    db = vendor / "data" / "gemini.db"
    wal = vendor / "data" / "gemini.db-wal"
    db.write_bytes(b"original corrupt data")
    wal.write_bytes(b"original wal data")
    monkeypatch.setattr(gemini, "VENDOR_DIR", vendor)
    monkeypatch.setattr(gemini.config, "ROOT", tmp_path / "other")
    with pytest.raises(RuntimeError, match="files preserved"):
        gemini.check_and_repair_db()
    assert db.read_bytes() == b"original corrupt data"
    assert wal.read_bytes() == b"original wal data"
