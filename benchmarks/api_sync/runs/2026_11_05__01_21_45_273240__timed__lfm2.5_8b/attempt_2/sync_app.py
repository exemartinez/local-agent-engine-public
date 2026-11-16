"""Synchronize a SQLite database with paginated HTTP pages."""
import sqlite3
import json
import urllib.request
import urllib.error
import time
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Callable


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
    full_url = url + '?' + params.get('cursor', '')
    try:
        with urllib.request.urlopen(full_url) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        if e.code in (429, 500, 501, 502, 503, 504):
            raise TransientError(e)
        else:
            raise
    except urllib.error.URLError as e:
        raise TransientError(e)


def _validate_item(item: Dict[str, Any]) -> None:
    """Validate that an item has required fields and types."""
    if not isinstance(item, dict):
        raise ValueError("item must be a dictionary")
    required = {'id', 'name', 'updated_at'}
    if set(item.keys()) != required:
        raise ValueError(f"item keys must be {required}, got {set(item.keys())}")
    if not item['id'] or not isinstance(item['id'], str) or not item['id'].strip():
        raise ValueError("item.id must be a non‑empty string")
    if not item['name'] or not isinstance(item['name'], str) or not item['name'].strip():
        raise ValueError("item.name must be a non‑empty string")
    if not item['updated_at']:
        raise ValueError("item.updated_at must be a non‑empty ISO 8601 timestamp")


def sync(
    connection: sqlite3.Connection,
    fetch_page: Callable[[str, Optional[str]], Any],
    sleep: Callable[int, None],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.1,
    logger: Optional[Any] = None,
) -> int:
    """
    Sync a SQLite database with paginated HTTP pages.

    Returns the number of unique records that were committed.
    Raises ValueError for configuration errors, duplicate cursors,
    validation failures, or already‑active transactions.
    """
    _validate_config(max_attempts, base_delay)

    if connection.is_autocommit:
        raise ValueError("already active transaction")

    url = None
    next_cursor = None
    seen_cursors = set()
    unique_ids = set()

    def _commit():
        with connection.cursor() as cur:
            cur.execute('BEGIN')
            try:
                return True
            except sqlite3.IntegrityError:
                cur.execute('ROLLBACK')
                raise

    attempts = 0
    while True:
        if next_cursor is not None:
            page = fetch_page(url, next_cursor)
            next_cursor = page.get('next_cursor')
        else:
            page = fetch_http_page(url, None)

        # Validate page structure
        if not isinstance(page, dict):
            raise ValueError("page must be a dictionary")
        _validate_page(page)
        url = page.get('next_cursor')

        # Detect duplicate cursor
        if next_cursor in seen_cursors:
            raise ValueError(f"duplicate cursor {next_cursor}")

        seen_cursors.add(next_cursor)
        attempts += 1

        if attempts > max_attempts:
            raise ValueError(f"max attempts ({max_attempts}) exceeded")

        # Apply delays for transient errors
        if attempts < max_attempts:
            delay = base_delay * (2 ** (attempts - 1))
            sleep(delay)

    # All pages validated – upsert into records table
    try:
        with connection.cursor() as cur:
            cur.execute('BEGIN')
            for item in unique_ids:
                cur.execute(
                    'INSERT OR REPLACE INTO records (id, name, updated_at) VALUES (?, ?, ?)',
                    (item['id'], item['name'], item['updated_at'])
                )
            commit = _commit()
            if commit:
                return len(unique_ids)
    except Exception:
        # Rollback any partial changes
        try:
            cur.execute('ROLLBACK')
        except sqlite3.Error:
            pass
        raise


def _validate_page(page: Dict[str, Any]) -> None:
    """Validate a page's pagination and item data."""
    if not isinstance(page, dict):
        raise ValueError("page must be a dictionary")
    required_keys = {'items', 'next_cursor'}
    if set(page.keys()) != required_keys:
        raise ValueError(f"page keys must be {required_keys}, got {set(page.keys())}")
    items = page['items']
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    for item in items:
        _validate_item(item)


def main(argv: Optional[list]) -> int:
    """CLI entry point."""
    url = os.getenv('SYNC_URL')
    db_path = os.getenv('SYNC_DB')

    if not url or not db_path:
        sys.stderr.write("ERROR: SYNC_URL and SYNC_DB environment variables must be set\n")
        return 2

    try:
        sync(
            sqlite3.connect(db_path),
            fetch_http_page,
            sleep,
            max_attempts=argv[1] if len(argv) > 1 else 3,
            base_delay=argv[2] if len(argv) > 2 else 0.1,
        )
    except ValueError:
        sys.stderr.write("ERROR: invalid configuration\n")
        return 2
    except Exception:
        sys.stderr.write("ERROR: sync failure\n")
        return 1

    return 0
