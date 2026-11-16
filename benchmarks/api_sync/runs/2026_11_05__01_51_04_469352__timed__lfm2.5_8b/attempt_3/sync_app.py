import argparse
import logging
import os
import sys
import sqlite3
from typing import Any, Callable, Dict, List, Optional, Tuple

logger: Optional[logging.Logger] = None  # will be set in main if needed


class TransientError(Exception):
    """Raised for transient network errors."""
    pass


def _validate_config(max_attempts: int, base_delay: float) -> None:
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer")
    if not isinstance(base_delay, (int, float)) or base_delay < 0:
        raise ValueError("base_delay must be a non-negative number")


def _has_active_transaction(connection: Any) -> None:
    try:
        connection.cursor().execute("SELECT 1")
    except Exception:
        raise


def sync(
    connection: Any,
    fetch_page: Callable[[], Any],
    sleep: Callable[[int], None],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.1,
    logger: Optional[logging.Logger] = None) -> int:
    # Validate configuration
    _validate_config(max_attempts, base_delay)

    table_name = "items"
    rows: List[Tuple[int, Dict[str, Any]]] = []

    try:
        cursor = connection.cursor()
        while True:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            distinct_before = cursor.fetchone()[0]
            page_rows = fetch_page(cursor)
            if not page_rows:
                break
            for item in page_rows:
                rows.append((item["id"], item))

            next_cursor = rows[-1].get("next_cursor")  # assume last row has next_cursor key
            if not next_cursor:
                break

        # Upsert all collected rows
        _upsert_items(connection, table_name, rows)

        # Commit transaction
        connection.commit()

        # Count distinct inserted records
        distinct_count = (
            connection.execute(f"SELECT COUNT(DISTINCT id) FROM {table_name}")
            .fetchone()[0]
        )
        return distinct_count

    except Exception:
        # Rollback any partial changes
        if hasattr(connection, "rollback"):
            connection.rollback()
        raise


def _upsert_items(
    connection: Any,
    table_name: str,
    rows: List[Tuple[int, Dict[str, Any]]]
) -> None:
    cursor = connection.cursor()
    for item_id, data in rows:
        cursor.execute(
            f"INSERT OR REPLACE INTO {table_name} (id, name, updated_at) VALUES (?, ?)",
            (item_id, data)
        )
    connection.commit()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronise paginated data from a remote endpoint into SQLite."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--db", required=True)
    return parser.parse_args()


def main() -> int:
    global logger
    # Check required environment variables
    if not os.environ.get("SYNC_URL"):
        print("Missing SYNC_URL environment variable", file=sys.stderr)
        return 2
    if not os.environ.get("SYNC_DB"):
        print("Missing SYNC_DB environment variable", file=sys.stderr)
        return 2

    args = _parse_args()

    try:
        result = sync(
            connection=sqlite3.connect(args.db),
            fetch_page=fetch_page,
            sleep=sleep,
            max_attempts=5,
            base_delay=2.0,
            logger=None
        )
        print(f"Sync completed – inserted {result} unique records", file=sys.stderr)
        return 0
    except Exception as e:
        if args.logger:
            args.logger.error(str(e))
        else:
            print(f"Sync failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.exit(main())
