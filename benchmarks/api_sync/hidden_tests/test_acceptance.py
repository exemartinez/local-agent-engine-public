import sqlite3
from unittest.mock import Mock
from urllib.error import HTTPError
import urllib.request

import pytest
import sync_app as app


def test_database_failure_rolls_back_all_changes():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE records (id TEXT PRIMARY KEY, name TEXT NOT NULL CHECK(name != 'bad'), updated_at TEXT NOT NULL)")
    db.execute("INSERT INTO records VALUES ('old', 'original', '2026-01-01T00:00:00Z')")
    db.commit()
    page = {"items": [{"id": "old", "name": "changed", "updated_at": "2026-01-01T00:00:00Z"}, {"id": "new", "name": "bad", "updated_at": "2026-01-01T00:00:00Z"}], "next_cursor": None}
    with pytest.raises(sqlite3.IntegrityError):
        app.sync(db, lambda _: page, lambda _: None)
    assert db.execute("SELECT id, name FROM records").fetchall() == [("old", "original")]


def test_nontransient_failure_is_not_retried():
    db = sqlite3.connect(":memory:")
    fetch = Mock(side_effect=RuntimeError("fail"))
    sleep = Mock()
    with pytest.raises(RuntimeError):
        app.sync(db, fetch, sleep)
    assert fetch.call_count == 1
    sleep.assert_not_called()


def test_retry_resets_per_page():
    db = sqlite3.connect(":memory:")
    fetch = Mock(side_effect=[app.TransientError(), {"items": [], "next_cursor": "next"}, app.TransientError(), {"items": [], "next_cursor": None}])
    sleep = Mock()
    assert app.sync(db, fetch, sleep, max_attempts=2, base_delay=0.5) == 0
    assert [call.args[0] for call in sleep.call_args_list] == [0.5, 0.5]


def test_logging_does_not_include_record_values():
    db = sqlite3.connect(":memory:")
    logger = Mock()
    page = {"items": [{"id": "secret-id", "name": "secret-name", "updated_at": "2026-01-01T00:00:00Z"}], "next_cursor": None}
    app.sync(db, lambda _: page, lambda _: None, logger=logger)
    assert "secret" not in str(logger.mock_calls)


@pytest.mark.parametrize("stamp", ["2026-02-30T12:00:00Z", "2026-13-01T12:00:00+00:00", "2026-01-01T25:00:00Z"])
def test_invalid_calendar_dates_rejected_without_creating_table(stamp):
    db = sqlite3.connect(":memory:")
    page = {"items": [{"id": "a", "name": "n", "updated_at": stamp}], "next_cursor": None}
    fetch = Mock(return_value=page)
    with pytest.raises(ValueError):
        app.sync(db, fetch, lambda _: None)
    fetch.assert_called_once_with(None)
    assert db.execute("SELECT name FROM sqlite_master WHERE name='records'").fetchone() is None


@pytest.mark.parametrize("code", [501, 502, 504, 599])
def test_all_server_errors_are_retryable(monkeypatch, code):
    error = HTTPError("https://example.test", code, "failed", {}, None)
    opener = Mock(side_effect=error)
    monkeypatch.setattr(urllib.request, "urlopen", opener)
    monkeypatch.setattr(app, "urlopen", opener, raising=False)
    with pytest.raises(app.TransientError):
        app.fetch_http_page("https://example.test", None)


def test_infinite_retry_delay_rejected_before_fetch():
    db = sqlite3.connect(":memory:")
    fetch = Mock()
    with pytest.raises(ValueError):
        app.sync(db, fetch, lambda _: None, base_delay=float("inf"))
    fetch.assert_not_called()
