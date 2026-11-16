```python
"""Sync application using SQLite."""

import json
import logging
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
import sqlite3
from typing import Dict, Any, Optional, Callable


logger = logging.getLogger(__name__)


class TransientError(Exception):
    """Raised for retryable fetch failures."""


def _validate_page(page: Dict[str, Any]) -> None:
    """Validate a page structure and its items."""
    if not isinstance(page, dict):
        raise ValueError("Page must be a dictionary")
    if "items" not in page or not isinstance(page["items"], list):
        raise ValueError("Page must contain an 'items' list")
    if "next_cursor" not in page:
        raise ValueError("Page must contain a 'next_cursor' string")
    for item in page["items"]:
        if not isinstance(item, dict) or "id" not in item or "name" not in item or "updated_at" not in item:
            raise ValueError("Each item must be a dictionary with id, name, updated_at")
        if not isinstance(item["id"], str) or not item["id"].strip():
            raise ValueError("Item id must be a non‑empty string")
        if not isinstance(item["name"], str) or not item["name"].strip():
            raise ValueError("Item name must be a non‑empty string")
        if not isinstance(item["updated_at"], str) or not item["updated_at"].strip():
            raise ValueError("Updated_at must be a non‑empty ISO 8601 timestamp with timezone")


def _fetch_http_page(url: str, cursor: Optional[str]) -> Dict[str, Any]:
    """Perform a GET request and return decoded JSON."""
    if cursor is not None:
        parsed = parse_qs(urlsplit(url).query)
        parsed["cursor"] = [cursor]
        full_url = urlsplit(url).with_query(parsed)
    try:
        with urllib.request.urlopen(full_url) as response:
            data = response.read().decode("utf-8")
    except (HTTPError, URLError) as e:
        if isinstance(e.code, int) and (e.code // 100 == 4 or e.code // 100 == 5):
            raise TransientError(f"HTTP {e.code}") from e
        raise
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e


def _ensure_no_active_transaction(conn: sqlite3.Connection) -> None:
    """Raise ValueError if another transaction is already active."""
    if hasattr(conn, "cursor") and conn.cursor().execute("SELECT 1").fetchone() is not None:
        raise ValueError("already-active transaction")


def sync(
    connection: sqlite3.Connection,
    fetch_page: Callable[[Optional[str], Dict[str, Any]], Dict[str, Any]],
    sleep: Callable[[int], None],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.1,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Synchronize a SQLite database from paginated HTTP pages.

    Returns the number of unique records committed.
    """
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer")
    if base_delay < 0 or not (isinstance(base_delay, (int, float)) and base_delay >= 0):
        raise ValueError("base_delay must be a non‑negative number")

    _ensure_no_active_transaction(connection)

    items_by_id: Dict[str, Any] = {}
    seen_cursors: set = set()
    cursor: Optional[str] = None

    while True:
        for attempt in range(1, max_attempts + 1):
            try:
                page = fetch_page(cursor)
            except TransientError:
                if attempt == max_attempts:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                time.sleep(delay)
                continue
            for item in page["items"]:
                if item["id"] in items_by_id:
                    pass
                items_by_id[item["id"]] = item

            next_cursor = page["next_cursor"]
            if next_cursor is None:
                break
            if next_cursor in seen_cursors:
                raise ValueError("Repeated cursor detected")
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        try:
            cur = connection.cursor()
            for item in items_by_id.values():
                cur.execute(
                    "INSERT OR REPLACE INTO records (id, name, updated_at) VALUES (?, ?, ?)",
                    (item["id"], item["name"], item["updated_at"])
                )
            connection.commit()
            return len(items_by_id)
        except Exception:
            try:
                connection.rollback()
            finally:
                raise


def fetch_http_page(url: str, cursor: Optional[str]) -> Dict[str, Any]:
    """Perform a GET request and return decoded JSON."""
    if cursor is not None:
        parsed = parse_qs(urlsplit(url).query)
        parsed["cursor"] = [cursor]
        full_url = urlsplit(url).with_query(parsed)
    try:
        with urllib.request.urlopen(full_url) as response:
            data = response.read().decode("utf-8")
    except (HTTPError, URLError) as e:
        if isinstance(e.code, int) and (e.code // 100 == 4 or e.code // 100 == 5):
            raise TransientError(f"HTTP {e.code}") from e
        raise
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Sync application")
    parser.add_argument("--url", help="Override SYNC_URL")
    parser.add_argument("--db", help="Override SYNC_DB")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum retry attempts")
    parser.add_argument("--base-delay", type=float, default=0.1, help="Base delay between retries")
    args = parser.parse_args(argv)

    sync_url = os.environ.get("SYNC_URL") or args.url
    sync_db = os.environ.get("SYNC_DB") or args.db

    if not sync_url or not sync_db:
        logger.error("Missing required --url or
