```python
"""Synchronization module for API-to-SQLite."""
import argparse
import json
import sqlite3
import urllib.request
import urllib.error
import time
import os
import sys
from datetime import datetime
from typing import Callable, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs


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
    parsed = urlparse(url)
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
    max_attempts: int = 3,
    base_delay: float = 0.1,
    logger=None,
) -> int:
    """
    Synchronize data from the API to SQLite.

    Returns the number of unique records committed.
    Raises ValueError for invalid configuration or fetch failures.
    """
    # Ensure no active transaction on this connection
    if hasattr(connection, "_transaction_active") and connection._transaction_active:
        raise ValueError("already active transaction")

    seen_ids = set()
    seen_cursors = set()
    cursor = None

    attempts = 0
    while True:
        try:
            url_page = fetch_page(connection, cursor)
        except TransientError:
            if attempts == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempts)
            time.sleep(delay)
            attempts += 1
            continue
        else:
            break

    # Validate all pages before committing
    for item in seen_ids:
        conn.execute(
            'INSERT OR REPLACE INTO records (id, name, updated_at) VALUES (?, ?, ?)',
            (item['id'], item['name'], item['updated_at'])
        )

    try:
        conn.execute('BEGIN TRANSACTION')
        conn.commit()
        return len(seen_ids)
    except Exception:
        # Rollback any partial changes
        conn.rollback()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description='Sync API data to SQLite')
    parser.add_argument('--url', help='Base URL for synchronization')
    parser.add_argument('--db', help='Path to SQLite database file')
    env_url = os.environ.get('SYNC_URL')
    env_db = os.environ.get('SYNC_DB')
    url = env_url if env_url is not None else parser.get
