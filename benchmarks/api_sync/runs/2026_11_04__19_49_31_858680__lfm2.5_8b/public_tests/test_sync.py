import sqlite3
import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

import pytest
import sync_app as app


def item(key, name="Name"):
    return {"id": key, "name": name, "updated_at": "2026-01-01T00:00:00+00:00"}


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    yield connection
    connection.close()


def test_paginated_upsert_and_idempotency(db):
    pages = {None: {"items": [item("a")], "next_cursor": "next"}, "next": {"items": [item("a", "new"), item("b")], "next_cursor": None}}
    fetch = Mock(side_effect=lambda cursor: pages[cursor])
    assert app.sync(db, fetch, lambda _: None) == 2
    assert db.execute("SELECT id, name FROM records ORDER BY id").fetchall() == [("a", "new"), ("b", "Name")]
    assert app.sync(db, fetch, lambda _: None) == 2
    assert db.execute("SELECT count(*) FROM records").fetchone()[0] == 2


def test_retry_per_page_and_backoff(db):
    fetch = Mock(side_effect=[app.TransientError(), app.TransientError(), {"items": [item("a")], "next_cursor": None}])
    sleep = Mock()
    assert app.sync(db, fetch, sleep, max_attempts=3, base_delay=0.25) == 1
    assert [call.args[0] for call in sleep.call_args_list] == [0.25, 0.5]


def test_invalid_later_page_leaves_database_unchanged(db):
    db.execute("CREATE TABLE records (id TEXT PRIMARY KEY, name TEXT NOT NULL, updated_at TEXT NOT NULL)")
    db.execute("INSERT INTO records VALUES ('old', 'old', '2026-01-01T00:00:00Z')")
    db.commit()
    pages = iter([{"items": [item("new")], "next_cursor": "p2"}, {"items": [{"id": "bad"}], "next_cursor": None}])
    with pytest.raises(ValueError):
        app.sync(db, lambda _: next(pages), lambda _: None)
    assert db.execute("SELECT id FROM records").fetchall() == [("old",)]


def test_repeated_cursor_rejected(db):
    with pytest.raises(ValueError):
        app.sync(db, lambda _: {"items": [], "next_cursor": "same"}, lambda _: None)


def test_cli_requires_configuration(monkeypatch, capsys):
    monkeypatch.delenv("SYNC_URL", raising=False)
    monkeypatch.delenv("SYNC_DB", raising=False)
    assert app.main([]) == 2
    assert capsys.readouterr().err


def test_http_pagination_and_existing_query(monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps({"items": [], "next_cursor": None}).encode()
    opener = Mock(return_value=response)
    monkeypatch.setattr(app, "urlopen", opener)
    assert app.fetch_http_page("https://example.test/items?key=value", "a b") == {"items": [], "next_cursor": None}
    request = opener.call_args.args[0]
    assert parse_qs(urlsplit(request.full_url).query) == {"key": ["value"], "cursor": ["a b"]}
    assert request.get_method() == "GET"


@pytest.mark.parametrize("code,retryable", [(429, True), (500, True), (503, True), (404, False)])
def test_http_error_classification(monkeypatch, code, retryable):
    error = HTTPError("https://example.test", code, "failed", {}, None)
    monkeypatch.setattr(app, "urlopen", Mock(side_effect=error))
    with pytest.raises(app.TransientError if retryable else HTTPError):
        app.fetch_http_page("https://example.test", None)


def test_http_network_error_is_transient(monkeypatch):
    monkeypatch.setattr(app, "urlopen", Mock(side_effect=URLError("offline")))
    with pytest.raises(app.TransientError):
        app.fetch_http_page("https://example.test", None)


@pytest.mark.parametrize("kwargs", [{"max_attempts": 0}, {"max_attempts": True}, {"base_delay": -1}, {"base_delay": float("nan")}])
def test_bad_retry_configuration_fails_before_fetch(db, kwargs):
    fetch = Mock()
    with pytest.raises(ValueError):
        app.sync(db, fetch, lambda _: None, **kwargs)
    fetch.assert_not_called()


def test_exhausted_retries_do_not_create_table(db):
    fetch = Mock(side_effect=app.TransientError())
    with pytest.raises(app.TransientError):
        app.sync(db, fetch, lambda _: None, max_attempts=2)
    assert fetch.call_count == 2
    assert db.execute("SELECT name FROM sqlite_master WHERE name='records'").fetchone() is None


@pytest.mark.parametrize("bad", [None, {}, {"items": []}, {"items": "bad", "next_cursor": None}, {"items": [], "next_cursor": ""}])
def test_bad_page_rejected(db, bad):
    with pytest.raises(ValueError):
        app.sync(db, lambda _: bad, lambda _: None)


@pytest.mark.parametrize("bad", [None, {}, {"id": "a", "name": "n", "updated_at": "not-a-date"}, {"id": "a", "name": "n", "updated_at": "2026-01-01T00:00:00"}])
def test_bad_record_rejected(db, bad):
    with pytest.raises(ValueError):
        app.sync(db, lambda _: {"items": [bad], "next_cursor": None}, lambda _: None)


def test_active_transaction_is_preserved(db):
    db.execute("CREATE TABLE pending (value TEXT)")
    db.execute("INSERT INTO pending VALUES ('keep')")
    with pytest.raises(ValueError):
        app.sync(db, Mock(), lambda _: None)
    assert db.in_transaction
    assert db.execute("SELECT value FROM pending").fetchall() == [("keep",)]


def test_cli_success_and_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("SYNC_URL", "https://example.test")
    monkeypatch.setenv("SYNC_DB", str(tmp_path / "out.db"))
    monkeypatch.setattr(app, "fetch_http_page", Mock(return_value={"items": [item("a")], "next_cursor": None}))
    assert app.main([]) == 0
    assert sqlite3.connect(tmp_path / "out.db").execute("SELECT count(*) FROM records").fetchone()[0] == 1
    monkeypatch.setattr(app, "fetch_http_page", Mock(side_effect=RuntimeError("secret")))
    assert app.main([]) == 1
    assert "secret" not in capsys.readouterr().err
    assert app.main(["--max-attempts", "nope"]) == 2
