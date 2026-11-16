#!/usr/bin/env python3
"""
sync_items.py

A small utility that synchronises paginated data from a remote endpoint into an
SQLite database, respecting retry parameters.  The module can also be used as a
stand‑alone command line tool.

Author:  (your name)
"""

import argparse
import json
import logging
import sqlite3
import sys
from typing import List, Dict, Any, Set, Tuple

import urllib.error
import urllib.request

# ----------------------------------------------------------------------
# Exceptions
# ----------------------------------------------------------------------
class TransientError(Exception):
    """Raised for recoverable network errors (e.g. 429, 500)."""
    pass


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def _has_active_transaction(conn: sqlite3.Connection) -> bool:
    """
    Return True if there is already a transaction on the given connection.
    """
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM pragma_session_list")
        count = cur.fetchone()[0]
        return count > 0
    except sqlite3.Error:
        # If we cannot determine the state, treat it as no active transaction.
        # In a real scenario you might want to abort or raise a more specific error.
        logging.error("Unable to query transaction state")
        return False


def _fetch_page(conn: sqlite3.Connection, url: str) -> List[Dict[str, Any]]:
    """
    Perform an HTTP GET request and return the parsed JSON list of items.

    Raises:
        TransientError – for 429 (Too Many Requests) or 500 (Internal Server Error)
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sync_items/1.0"})
        # Use the connection's timeout if it exists; otherwise default to 30 s.
        timeout = getattr(conn, "timeout", 30)
        with urllib.request.urlopen(conn, req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as e:
        # Retryable errors: 429 (rate limit) and 500 (server error)
        if e.code in (429, 500):
            raise TransientError(f"HTTP {e.code}: {e.reason}") from e
        else:
            raise
    except Exception as e:
        raise TransientError(f"Failed to fetch page: {e}") from e


def _validate_page(page: Dict[str, Any]) -> None:
    """
    Validate that a page contains the required keys and that `items` is a list.
    """
    if not isinstance(page, dict):
        raise ValueError("Page must be a dictionary")
    if "items" not in page:
        raise ValueError("Missing required key: 'items'")
    if "next_cursor" not in page:
        raise ValueError("Missing required key: 'next_cursor'")
    if not isinstance(page["items"], list):
        raise ValueError("'items' must be a list")


def _upsert_items(conn: sqlite3.Connection, table_name: str,
                  rows: List[Tuple[int, Dict[str, Any]]) -> None:
    """
    Insert or replace rows in the given table.

    Assumes each row is (id, data_dict) where `data_dict` contains all columns
    except the primary key column named 'id'.
    """
    for item_id, data in rows:
        # Build a list of column names excluding the presumed primary‑key column.
        cols = [k for k in data.keys() if k != "id"]
        try:
            conn.execute(
                f"INSERT OR REPLACE INTO {table_name} (id, {', '.join(cols)}) "
                f"VALUES (?, ?)",
                (item_id, tuple(data.values()))
            )
        except Exception as e:
            raise RuntimeError(f"Failed to upsert row id={item_id}: {e}") from e


# ----------------------------------------------------------------------
# Core sync logic
# ----------------------------------------------------------------------
def sync(
    conn: sqlite3.Connection,
    host: str | None = None,
    port: int = 80,
    path: str = "/",
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> int:
    """
    Sync paginated data from a remote endpoint into the given SQLite connection.

    Returns
    -------
    int
        Number of distinct records inserted (including previously existing ones).

    Raises
    ------
    ValueError
        If an active transaction is already in progress.
    RuntimeError
        For unexpected database errors.
    """
    # 1. Guard against concurrent use
    if _has_active_transaction(conn):
        raise ValueError("An active transaction is already in progress")

    # 2. Begin a new transaction
    try:
        conn.execute("BEGIN TRANSACTION")
        cursor = conn.cursor()
        rows: List[Tuple[int, Dict[str, Any]]] = []
        seen_cursors: Set[str] = set()
        current_cursor: str | None = None

        while True:
            # Build URL for the next page
            if current_cursor is None:
                url = f"https://{host}:{port}{path}"
            else:
                next_cursor = page["next_cursor"]
                if next_cursor in seen_cursors:
                    raise ValueError("Repeated cursor encountered during pagination")
                seen_cursors.add(next_cursor)
                url = f"https://{host}:{port}{path}?next_cursor={next_cursor}"

            # Fetch and validate the page
            try:
                items = _fetch_page(conn, url)
            except TransientError as te:
                # Roll back any changes made before the transient error
                conn.rollback()
                raise te

            _validate_page(items)

            # Extract rows (each item must contain an 'id')
            for item in items:
                if "id" not in item:
                    raise ValueError(f"Item missing required field 'id': {item}")
                rows.append((item["id"], item))

            current_cursor = items.get("next_cursor")
            if current_cursor is None:
                break

        # 3. Upsert all collected rows
        table_name = "items"  # default target table; could be parameterised
        _upsert_items(conn, table_name, rows)

        # Commit the transaction
        conn.commit()

        # 4. Count distinct inserted records
        distinct_count = (
            conn.execute(f"SELECT COUNT(DISTINCT id) FROM {table_name}")
            .fetchone()[0]
        )
        return distinct_count

    except Exception:
        # Roll back on any error and re‑raise
        conn.rollback()
        raise


# ----------------------------------------------------------------------
# Command line interface
# ----------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronise paginated data from a remote endpoint into SQLite."
    )
    parser.add_argument("--host", help="Hostname (e.g. example.com)")
    parser.add_argument("--port", type=int, default=80, help="Port number")
    parser.add_argument("--path", default="/", help="Path to fetch items from")
    parser.add_argument("--user", help="Database username")
    parser.add_argument("--password", help="Database password")
    parser.add_argument("--database", help="SQLite database file (or path to it)")
    return parser.parse_args


def main() -> int:
    args = _parse_args()

    # Determine connection object
    if args.database:
        conn = sqlite3.connect(args.database)
    else:
        # In‑memory default for quick testing; real usage should provide a file path.
        conn = sqlite3.connect(":memory:")

    try:
        result = sync(
            conn,
            host=args.host,
            port=args.port,
            path=args.path,
            user=args.user,
            password=args.password,
            database=args.database,
            max_attempts=5,
            base_delay=2.0,
        )
        print(f"Sync completed – inserted {result} unique records")
        return 0
    except Exception as e:
        print(f"Sync failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.exit(main())
