"""Candidate implementation goes here. See spec.md for the public contract."""

import sqlite3
import json
import urllib.request
import urllib.error
import time
import os
from datetime import datetime
from typing import Dict, Any, Optional


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
        return dict(parse_qs(parsed.query))
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
            data = response.read().decode('utf-8')
            return json.loads(data)
    except urllib.error.HTTPError as e:
        if e.code in (429, 500, 501, 502, 503, 504):
            raise TransientError()
        else:
            raise
    except urllib.error.URLError:
        raise TransientError()


def _validate_page(page: Dict[str, Any]) -> None:
    """Validate a single page structure."""
    if not isinstance(page, dict):
        raise ValueError("page must be a dictionary")
    required = {'items', 'next_cursor'}
    if not required.issubset(page.keys()):
        raise ValueError("page missing required keys")
    items = page['items']
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    for item in items:
        if not (isinstance(item, dict) and 'id' in item and 'name' in item and 'updated_at' in item):
            raise ValueError("item missing required fields")
        # Basic non‑empty checks
        if not isinstance(item['id'], str) or not item['id']:
            raise ValueError("item id must be a non‑empty string")
        if not isinstance(item['name'], str) or not item['name']:
            raise ValueError("item name must be a non‑empty string")
        # updated_at is a string; we accept any ISO‑8601 format per spec
        if not isinstance(item['updated_at'], str):
            raise ValueError("updated_at must be an ISO‑8601 timestamp")


def sync(
    connection: sqlite3.Connection,
    fetch_page: Callable[[str, Optional[str]], Dict[str, Any]],
    sleep: Callable[[float], None],
    *,
    max_attempts: int,
    base_delay: float,
    logger: Optional[Any] = None,
) -> int:
    """
    Synchronize a SQLite database with paginated HTTP pages.

    Returns the number of unique records committed.
    Raises : ValueError for configuration or validation errors,
    TransientError for retryable fetch failures, and propagates other
    exceptions.
    """
    _validate_config(max_attempts, base_delay)
    if not connection.is_tight():
        raise ValueError("already active transaction")

    with connection:
        cursor: Optional[str] = None
        seen_cursors: set[str] = set()
        while True:
            try:
                page = fetch_page(url, cursor)
            except TransientError:
                attempt = 1
                while attempt <= max_attempts:
                    try:
                        page = fetch_page(url, cursor)
                    except TransientError:
                        if attempt == max_attempts:
                            raise
                        sleep_delay = base_delay * (2 ** (attempt - 1))
                        time.sleep(sleep_delay)
                        attempt += 1
                    else:
                        break
                # after retries, page must be valid
            except ValueError as e:
                if logger:
                    logger.error(f"Invalid page or record: {e}")
                raise

            _validate_page(page)

            items = page['items']
            next_cursor = page['next_cursor']

            if not isinstance(items, list):
                raise ValueError("items must be a list")
            for item in items:
                db.execute(
                    "INSERT OR REPLACE INTO records (id, name, updated_at) VALUES (?, ?, ?)",
                    (item['id'], item['name'], item['updated_at'])
                )

            if next_cursor is None:
                break
            if next_cursor in seen_cursors:
                raise ValueError("repeated cursor")
            seen_cursors.add(next_cursor)
            cursor = next_cursor


def main(argv: Optional[list]) -> int:
    """Command‑line entry point."""
    sync_url = os.environ.get('SYNC_URL')
    sync_db = os.environ.get('SYNC_DB')
    max_attempts_str = os.environ.get('SYNC_MAX_ATTEMPTS', '3')
    base_delay_str = os.environ.get('SYNC_BASE_DELAY', '0.1')

    if sync_url is None or sync_db is None:
        return 2

    try:
        db_path = int(os.path.abspath(sync_db))
    except ValueError:
        return 2

    conn = sqlite3.connect(db_path)
    try:
        sync(
            connection=conn,
            fetch_page=fetch_http_page,
            sleep=time.sleep,
            max_attempts=int(max_attempts_str),
            base_delay=float(base_delay_str),
        )
        return 0
    except ValueError as e:
        # configuration or validation errors
        return 2
    except Exception:
        # any other error during sync
        return 1


if __name__ == "__main__":
    sys.exit(main())
