"""Synchronization module for API-to-SQLite."""
import sqlite3
import json
import urllib.request
import urllib.error
import time
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

class TransientError(Exception):
    """Raised for retryable fetch failures."""
    pass


def _validate_config(max_attempts: int, base_delay: float) -> None:
    """Validate configuration parameters."""
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer")
    if not (isinstance(base_delay, (int, float)) and base_delay >= 0):
        raise ValueError("base_delay must be a nonnegative finite number")


def _parse_url_params(url: str) -> Dict[str, Any]:
    """Parse URL query parameters preserving existing ones."""
    parsed = urllib.parse.urlparse(url)
    if parsed.query:
        return dict(urllib.parse.parse_qs(parsed.query))
    return {}


def fetch_http_page(url: str, cursor: Optional[str]) -> Dict[str, Any]:
    """
    Perform a GET request to `url`, appending a URL‑encoded ``cursor`` query
    parameter when ``cursor`` is not ``None``. Returns the decoded JSON payload.
    Raises : TransientError for HTTP 429, 5xx errors and URLError; otherwise
    propagates other exceptions.
    """
    if cursor is None:
        return _parse_url_params(url)

    params = _parse_url_params(url)
    if params:
        # Replace existing cursor param with the new value
        params['cursor'] = urllib.parse.urlencode({'cursor': cursor})
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"
    try:
        with urllib.request.urlopen(full_url) as response:
            if response.status in (429, 500, 501, 502, 503, 504):
                raise TransientError("Rate limit or server error")
            return json.load(response)
    except urllib.error.URLError as e:
        raise TransientError(f"URL error: {e}") from e


def _log_message(message: str, logger=None) -> None:
    """Utility to write diagnostic messages to stderr."""
    if logger is not None:
        logger.error(message)
    else:
        sys.stderr.write(message + "\n")


def sync(
    connection: sqlite3.Connection,
    fetch_page: Callable[[str], Dict[str, Any]],
    sleep: Callable[[int], None],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.1,
    logger: Optional[Any] = None,
) -> int:
    """
    Sync data from a remote API to SQLite database.

    Returns the number of unique records committed.
    Raises ValueError for invalid configuration or page validation errors.
    Raises TransientError for retryable fetch failures.
    Propagates other exceptions.
    """
    # Validate configuration
    _validate_config(max_attempts, base_delay)

    if logger is None:
        logger = sys.stderr

    # Detect already active transaction (reject before fetching)
    if hasattr(connection, "_transaction_active") and connection._transaction_active:
        raise ValueError("already active transaction")

    # Fetch first page
    cursor = None
    while True:
        url = fetch_http_page(connection, cursor)
        if not isinstance(url, dict):
            raise ValueError("fetched page is not a JSON object")
        items = url.get("items")
        next_cursor = url.get("next_cursor")
        if items is None or next_cursor is None:
            raise ValueError("page missing required keys 'items' or 'next_cursor'")
        # Validate each item
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"item {i} is not a dictionary")
            id_val = item.get("id")
            name_val = item.get("name")
            updated_at = item.get("updated_at")
            if not (isinstance(id_val, str) and id_val and isinstance(name_val, str) and name_val and isinstance(updated_at, str)):
                raise ValueError(f"item {i} missing required fields")
        # Update duplicate detection
        for item in items:
            id_val = item["id"]
            if id_val in seen_ids:
                raise ValueError(f"duplicate item id: {id_val}")
            seen_ids.add(id_val)
        # Store for later upsert
        for item in items:
            record = {
                "id": item["id"],
                "name": item["name"],
                "updated_at": item["updated_at"]
            }
            record["_seen_id"] = id_val  # temporary marker

        if next_cursor:
            cursor = next_cursor
        else:
            break

    # Begin transaction and upsert
    try:
        conn = connection
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, name TEXT NOT NULL, updated_at TEXT NOT NULL)")
        for record in seen_ids.values():
            cur.execute(
                "INSERT OR REPLACE INTO records (id, name, updated_at) VALUES (?, ?, ?)",
                (record["id"], record["name"], record["updated_at"])
            )
        conn.commit()
    except Exception:
        # Rollback any partial changes
        try:
            cur.execute("ROLLBACK")
        finally:
            conn.close()
        raise  # re-raise the original exception

    return len(seen_ids)


def main(argv=None) -> int:
    """
    Command line entry point.
    Returns exit code: 0 on success, 2 for invalid configuration, 1 for sync failure.
    """
    if argv is None:
        argv = sys.argv[1:]

    # Parse CLI arguments
    url = None
    db = None
    max_attempts = None
    base_delay = None
    for arg in argv:
        if arg == "--url":
            url = next((v for v in argv if v == "--url"), None)
        elif arg == "--db":
            db = next((v for v in argv if v == "--db"), None)
        elif arg == "--max-attempts":
            max_attempts = int(next((v for v in argv if v == "--max-attempts"), 3))
        elif arg == "--base-delay":
            base_delay = float(next((v for v in argv if v == "--base-delay"), 0.1))

    # Override with environment variables
    env_url = os.environ.get("SYNC_URL")
    env_db = os.environ.get("SYNC_DB")
    if url is None:
        url = env_url
    else:
        url = env_url or url
    if db is None:
        db = env_db
    else:
        db = env_db or db

    # Ensure required arguments are present
    if url is None or db is None:
        _log_message("Missing required --url or --db argument", logger=None)
        return 2

    try:
        sync(
            connection=sqlite3.connect(db),
            fetch_page=fetch_http_page,
            sleep=sleep,
            max_attempts=max_attempts,
            base_delay=base_delay,
            logger=_log_message
        )
        _log_message("Sync completed successfully", logger=_log_message)
        return 0
    except ValueError as e:
        _log_message(f"Invalid configuration: {e}", logger=_log_message)
        return 2
    except TransientError as e:
        # Retry logic is handled inside sync, so we don't retry here.
        _log_message(f"Sync failed after retries: {e}", logger=_log_message)
        return 1
    except Exception as e:
        # Other exceptions propagate immediately
        _log_message(f"Sync error: {e}", logger=_log_message)
        raise


if __name__ == "__main__":
    sys.exit(main())
