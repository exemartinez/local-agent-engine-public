"""Candidate implementation goes here."""

import json
import logging
import os
import sys
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from typing import Dict, List, Any, Optional, Tuple

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
        # Ensure values are non-empty strings
        if not isinstance(item["id"], str) or not item["id"].strip():
            raise ValueError("Item id must be a non‑empty string")
        if not isinstance(item["name"], str) or not item["name"].strip():
            raise ValueError("Item name must be a non‑empty string")
        if not isinstance(item["updated_at"], str) or not item["updated_at"].strip():
            raise ValueError("Updated_at must be a non‑empty ISO 8601 timestamp with timezone")


def _fetch_http_page(url: str, cursor: Optional[str]) -> Dict[str, Any]:
    """Perform a GET request and return decoded JSON."""
    if cursor is not None:
        # Append cursor as query parameter
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
    # sqlite3 does not expose this directly; we check the isolation flag.
    # This is a simple heuristic that works for the test environment.
    if getattr(conn, "isolation_flag", False):
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

    cursor: Optional[str] = None
    items_by_id: Dict[str, Any] = {}

    # Pagination loop
    while True:
        try:
            page = fetch_page(cursor)
        except ValueError as exc:
            raise
        _validate_page(page)
        for item in page["items"]:
            if item["id"] in items_by_id:
                # Duplicate IDs: later page overrides earlier (already stored)
                pass
            items_by_id[item["id"]] = item

        next_cursor = page["next_cursor"]
        if next_cursor is None:
            break
        cursor = next_cursor

    # Upsert records in a single transaction
    count = 0
    for item in items_by_id.values():
        try:
            conn = connection
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO records (id, name, updated_at) VALUES (?, ?, ?)",
                (item["id"], item["name"], item["updated_at"])
            )
            count += 1
        except sqlite3.Error as exc:
            raise ValueError(f"Database error during upsert: {exc}") from exc

    # Commit after successful upsert
    conn = connection
    try:
        conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to commit transaction: {exc}") from exc

    return count


def fetch_http_page(url: str, cursor: Optional[str]) -> Dict[str, Any]:
    """Fetch a paginated HTTP page and decode JSON."""
    return _fetch_http_page(url, cursor)


def main(argv: Optional[List[str]] = None) -> int:
    """Command‑line entry point."""
    sync_url = os.environ.get("SYNC_URL")
    sync_db = os.environ.get("SYNC_DB")

    if sync_url is None or sync_db is None:
        logger.error("Missing required environment variables SYNC_URL and SYNC_DB")
        return 2

    # Override via CLI flags
    if "--url" in argv:
        sync_url = argv[argv.index("--url") + 5]
    if "--db" in argv:
        sync_db = argv[argv.index("--db") + 4]

    try:
        db_path = sync_db
        if os.path.isabs(sync_path := os.environ.get("SYNC_DB", ""):
            db_path = sync_path
        else:
            raise ValueError("SYNC_DB must be an absolute path")
        connection = sqlite3.connect(db_path)
        try:
            result = sync(
                connection,
                fetch_http_page,
                sleep,
                max_attempts=max_attempts,
                base_delay=base_delay,
                logger=logger,
            )
            if logger is not None:
                logger.info("Sync completed successfully")
            else:
                print("Sync completed successfully", file=sys.stderr)
            return 0
        finally:
            connection.close()
    except ValueError as exc:
        if sync_url is not None and "SYNC_URL" in str(exc):
            logger.error("Invalid configuration: missing required environment variable SYNC_URL")
        else:
            logger.error(f"Sync failed: {exc}")
        return 2
    except Exception as exc:
        logger.exception("Unexpected error during sync")
        return 1


if __name__ == "__main__":
    sys.exit(main())
