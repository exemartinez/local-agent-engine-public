import sqlite3
import urllib.request
import urllib.parse
import json
import sys
import os
import logging
from typing import Optional, Dict, List, Any
import time


class TransientError(Exception):
    """Exception for retryable fetch failures."""
    pass


def validate_page(page: Dict[str, Any]) -> None:
    """Validate a page structure. Raises ValueError if invalid."""
    if not isinstance(page, dict):
        raise ValueError("Page must be a dictionary")
    
    if "items" not in page or not isinstance(page["items"], list):
        raise ValueError("Page must contain 'items' as a list")
    
    if "next_cursor" not in page:
        raise ValueError("Page must contain 'next_cursor'")
    
    for item in page["items"]:
        if not isinstance(item, dict):
            raise ValueError("Item must be a dictionary")
        
        if "id" not in item or not item["id"]:
            raise ValueError("Item must have non-empty 'id'")
        
        if "name" not in item or not item["name"]:
            raise ValueError("Item must have non-empty 'name'")
        
        if "updated_at" not in item or not item["updated_at"]:
            raise ValueError("Item must have non-empty 'updated_at'")


def fetch_http_page(url: str, cursor: Optional[str]) -> Dict[str, Any]:
    """Fetch a page from the API. Raises TransientError on retryable failures."""
    try:
        query_params = urllib.parse.urlencode({"cursor": cursor}) if cursor else ""
        full_url = f"{url}?{query_params}" if query_params else url
        
        req = urllib.request.Request(full_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        raise TransientError(f"Network error while fetching {url}")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON response from API")


def sync(connection: sqlite3.Connection, fetch_page: callable, sleep: callable, *, max_attempts: int = 3, base_delay: float = 0.1, logger: Optional[logging.Logger] = None) -> int:
    """Synchronize records from API to SQLite database."""
    if not isinstance(max_attempts, int) or max_attempts <= 0 or isinstance(max_attempts, bool):
        raise ValueError("max_attempts must be a positive integer")
    
    if not isinstance(base_delay, (int, float)) or base_delay < 0:
        raise ValueError("base_delay must be a non-negative number")
    
    # Check for active transaction
    try:
        connection.execute("BEGIN")
        raise ValueError("Active transaction detected")
    except sqlite3.OperationalError:
        pass
    
    all_records = []
    cursor = None
    
    while True:
        try:
            page = fetch_page(cursor)
        except TransientError as e:
            if logger:
                logger.warning(f"Transient error fetching page {cursor}: {e}")
            
            attempt = 0
            while attempt < max_attempts:
                try:
                    sleep(base_delay * (2 ** attempt))
                    page = fetch_page(cursor)
                    break
                except TransientError as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    time.sleep(base_delay * (2 ** attempt))
        
        validate_page(page)
        
        for item in page["items"]:
            all_records.append(item)
        
        next_cursor = page.get("next_cursor")
        if next_cursor is None:
            break
        
        cursor = next_cursor
    
    # Upsert records into database
    try:
        connection.execute("BEGIN")
        for record in all_records:
            connection.execute(
                "INSERT OR REPLACE INTO records (id, name, updated_at) VALUES (?, ?, ?)",
                (record["id"], record["name"], record["updated_at"])
            )
        connection.commit()
    except sqlite3.OperationalError as e:
        raise ValueError(f"Database error: {e}")
    
    return len(all_records)


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync API to SQLite")
    parser.add_argument("--url", help="API URL (overrides SYNC_URL)")
    parser.add_argument("--db", help="SQLite database path (overrides SYNC_DB)")
    parser.add_argument("--max-attempts", type=int, default=3, help="Max retry attempts")
    parser.add_argument("--base-delay", type=float, default=0.1, help="Base delay between retries")
    
    args = parser.parse_args(argv)
    
    url = os.environ.get("SYNC_URL") or args.url
    db_path = os.environ.get("SYNC_DB") or args.db
    
    if not url or not db_path:
        print("Error: Both --url and --db are required", file=sys.stderr)
        return 2
    
    try:
        connection = sqlite3.connect(db_path)
        result = sync(connection, fetch_http_page, time.sleep, max_attempts=args.max_attempts, base_delay=args.base_delay)
        connection.close()
        
        if result > 0:
            print(f"Synced {result} records", file=sys.stderr)
            return 0
        else:
            print("No records synced", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
