import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

# Transient errors are retryable (429, 5xx, network errors)
TRANSIENT_STATUS_CODES = {429} | set(str(code) for code in range(500, 600))


class TransientError(Exception):
    """Raised for transient failures that should be retried."""
    pass


def validate_config(max_attempts: int, base_delay: float) -> None:
    """Validate retry configuration parameters."""
    if isinstance(max_attempts, bool):
        raise ValueError("max_attempts must be a positive integer, not a boolean")
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer")
    
    if isinstance(base_delay, bool):
        raise ValueError("base_delay must be a nonnegative finite number, not a boolean")
    if not isinstance(base_delay, (int, float)):
        raise ValueError("base_delay must be a nonnegative finite number")
    if base_delay < 0:
        raise ValueError("base_delay must be a nonnegative finite number")
    if not (isinstance(base_delay, float) and base_delay != float('inf') and base_delay != float('-inf')):
        # Check for NaN specifically using math.isfinite or try/except
        import math
        if not math.isfinite(base_delay):
            raise ValueError("base_delay must be a nonnegative finite number")


def fetch_http_page(url: str, cursor: str) -> dict:
    """Fetch a page from the API."""
    base_url = url.split("?")[0]
    params = parse_qs(urlsplit(url).query)
    
    if cursor is not None and cursor != "":
        params["cursor"] = [cursor]
    
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{base_url}?{query_string}" if query_string else base_url
    
    try:
        with urllib.request.urlopen(full_url) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except HTTPError as e:
        if e.code in TRANSIENT_STATUS_CODES:
            raise TransientError(f"Transient error {e.code}: {e.reason}") from e
        raise
    
    except URLError as e:
        raise TransientError(f"Network error: {e.reason}") from e


def validate_page(page: dict) -> None:
    """Validate a page structure."""
    if not isinstance(page, dict):
        raise ValueError("Page must be a dictionary")
    
    if "items" not in page or not isinstance(page["items"], list):
        raise ValueError("Page must contain 'items' as a list")
    
    if "next_cursor" not in page:
        raise ValueError("Page must contain 'next_cursor'")
    
    next_cursor = page["next_cursor"]
    if next_cursor is not None and not isinstance(next_cursor, str):
        raise ValueError("'next_cursor' must be a string or null")


def validate_item(item: dict) -> None:
    """Validate an item structure."""
    if not isinstance(item, dict):
        raise ValueError("Item must be a dictionary")
    
    required_keys = {"id", "name", "updated_at"}
    missing = required_keys - set(item.keys())
    if missing:
        raise ValueError(f"Item missing required keys: {missing}")
    
    for key in required_keys:
        val = item[key]
        if not isinstance(val, str) or val == "":
            raise ValueError(f"Field '{key}' must be a nonempty string")


def validate_records(records: list) -> None:
    """Validate all records in a page."""
    for i, record in enumerate(records):
        try:
            validate_item(record)
        except ValueError as e:
            raise ValueError(f"Invalid record at index {i}: {e}") from e


def sync(connection: sqlite3.Connection, fetch_page, sleep, *, max_attempts: int = 3, base_delay: float = 0.1, logger=None) -> int:
    """Synchronize data from API to SQLite."""
    validate_config(max_attempts, base_delay)
    
    # Check for active transaction
    try:
        connection.execute("PRAGMA busy_timeout=5000")
    except sqlite3.OperationalError:
        raise ValueError("An active transaction is already in progress") from None
    
    # Fetch all pages first
    cursor = None
    pages = []
    
    while True:
        try:
            page = fetch_page(cursor)
        except TransientError as e:
            if logger:
                logger.warning(f"Transient error fetching page {cursor}: {e}")
            raise
        
        validate_page(page)
        
        # Check for cycle
        if cursor is not None and page["next_cursor"] == cursor:
            raise ValueError("Repeated cursor detected")
        
        pages.append(page)
        
        next_cursor = page.get("next_cursor")
        if next_cursor is None or next_cursor == "":
            break
        
        # Check for cycle before moving to next
        if next_cursor in [p["next_cursor"] for p in pages[:-1]]:
            raise ValueError("Repeated cursor detected")
        
        cursor = next_cursor
    
    # Validate all records across all pages
    all_records = []
    for page in pages:
        validate_page(page)
        validate_records(page["items"])
        all_records.extend(page["items"])
    
    if not all_records:
        return 0
    
    # Upsert into database
    try:
        connection.execute("BEGIN")
        
        for record in all_records:
            conn = connection
            conn.execute(
                "INSERT OR REPLACE INTO records (id, name, updated_at) VALUES (?, ?, ?)",
                (record["id"], record["name"], record["updated_at"])
            )
        
        connection.commit()
        return len(all_records)
    
    except Exception:
        # Rollback on any error
        try:
            connection.rollback()
        except sqlite3.Error:
            pass
        raise


def main(argv=None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sync API data to SQLite")
    parser.add_argument(
        "--url", 
        dest="url", 
        default=os.getenv("SYNC_URL"), 
        help="API URL (env: SYNC_URL)"
    )
    parser.add_argument(
        "--db", 
        dest="db", 
        default=os.getenv("SYNC_DB"), 
        help="SQLite database path (env: SYNC_DB)"
    )
    parser.add_argument(
        "--max-attempts", 
        type=int, 
        default=int(os.getenv("SYNC_MAX_ATTEMPTS", "3")), 
        help="Max retry attempts"
    )
    parser.add_argument(
        "--base-delay", 
        type=float, 
        default=float(os.getenv("SYNC_BASE_DELAY", "0.1")), 
        help="Base delay between retries"
    )
    
    args = parser.parse_args(argv)
    
    # Validate required arguments
    if not args.url or not args.db:
        print("Error: --url and --db are required", file=sys.stderr)
        return 2
    
    try:
        connection = sqlite3.connect(args.db)
    except sqlite3.Error as e:
        print(f"Error opening database: {e}", file=sys.stderr)
        return 2
    
    try:
        # Create table if not exists (idempotent setup)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, 
                name TEXT NOT NULL, 
                updated_at TEXT NOT NULL
            )
        """)
        
        def fetch_page(cursor):
            return fetch_http_page(args.url, cursor)
        
        def sleep(seconds):
            import time
            time.sleep(seconds)
        
        result = sync(connection, fetch_page, sleep, max_attempts=args.max_attempts, base_delay=args.base_delay)
        
        if result == 0:
            print("No records to sync", file=sys.stderr)
            return 0
        
        print(f"Synced {result} records", file=sys.stderr)
        return 0
    
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2
    
    except TransientError as e:
        print(f"Sync failed: {e}", file=sys.stderr)
        return 1
    
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1
    
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
