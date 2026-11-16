import argparse
import json
import sqlite3
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

# Import TransientError from the same module to allow circular imports if needed in tests
# However, since we are defining it here, we must be careful. 
# The skeleton defines TransientError at the top level. We will keep it there.
# But wait, the skeleton has `class TransientError(Exception):` at the top.
# So we don't need to import it.

from urllib.request import urlopen as _urlopen


class TransientError(Exception):
    """Raised for retryable HTTP or network failures."""
    pass


def fetch_http_page(url, cursor):
    """Fetch a page from the API and return decoded JSON."""
    params = []
    if cursor is not None:
        params.append(f"cursor={cursor}")
    
    full_url = url
    if params:
        # Check if there are existing query parameters
        try:
            parsed = urlsplit(url)
            existing_qs = parse_qs(parsed.query)
            if existing_qs:
                # Merge existing params with new cursor param
                # We need to preserve existing keys. 
                # Simple approach: append cursor param to the end of the query string
                # But we must ensure it's URL encoded properly.
                # The spec says "appending a URL-encoded cursor query parameter"
                # It implies adding it to the query string.
                
                # Construct new query string
                new_qs_parts = []
                for k, v in existing_qs.items():
                    if isinstance(v, list):
                        new_qs_parts.extend([f"{k}={val}" for val in v])
                    else:
                        new_qs_parts.append(f"{k}={v}")
                
                # Add cursor param last
                new_qs_parts.append(params[0])
                full_url = f"{parsed.scheme}:{parsed.netloc}{parsed.path}?{'&'.join(new_qs_parts)}"
        except Exception:
            # Fallback if parsing fails, just append cursor to end of query string
            try:
                existing = url.split('?')[1] if '?' in url else ""
                full_url = f"{url}?{existing}&{params[0]}"
            except Exception:
                full_url = f"{url}?{params[0]}"

    try:
        with _urlopen(full_url) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data
    except HTTPError as e:
        if e.code in (429, 500, 501, 502, 503, 504):
            raise TransientError(f"HTTP {e.code}: {e.reason}") from None
        raise
    except URLError as e:
        raise TransientError(f"Network error: {e.reason}") from None


def validate_page(page):
    """Validate page structure. Raises ValueError if invalid."""
    if not isinstance(page, dict):
        raise ValueError("Page must be a dictionary")
    
    if "items" not in page or not isinstance(page["items"], list):
        raise ValueError("Page must contain 'items' as a list")
    
    if "next_cursor" not in page:
        raise ValueError("Page must contain 'next_cursor'")
    
    next_cursor = page["next_cursor"]
    if next_cursor is not None and not isinstance(next_cursor, str):
        raise ValueError("'next_cursor' must be a string or null")
    
    return next_cursor


def validate_item(item):
    """Validate an item structure. Raises ValueError if invalid."""
    if not isinstance(item, dict):
        raise ValueError("Item must be a dictionary")
    
    required_keys = {"id", "name", "updated_at"}
    if not required_keys.issubset(item.keys()):
        missing = required_keys - set(item.keys())
        raise ValueError(f"Item missing required keys: {missing}")
    
    for key in required_keys:
        val = item[key]
        if not isinstance(val, str) or not val:
            raise ValueError(f"Field '{key}' must be a non-empty string")
    
    # Validate updated_at format roughly (ISO 8601 with timezone)
    # The spec says "Preserve the timestamp text", implying we don't parse it for logic,
    # but we should ensure it's not obviously broken if we want to be strict.
    # However, tests show "2026-01-01T00:00:00" (no timezone) is rejected as bad_record_rejected?
    # Let's look at test_bad_record_rejected: 
    # {"id": "a", "name": "n", "updated_at": "not-a-date"} -> ValueError
    # {"id": "a", "name": "n", "updated_at": "2026-01-01T00:00:00"} -> ValueError (missing timezone)
    # So we must validate ISO 8601 with timezone.
    import re
    iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})$'
    if not re.match(iso_pattern, item["updated_at"]):
        raise ValueError(f"Field 'updated_at' must be ISO 8601 with timezone: {item['updated_at']}")


def sync(connection, fetch_page, sleep, *, max_attempts=3, base_delay=0.1, logger=None):
    """
    Synchronize data from API to SQLite.
    
    Args:
        connection: sqlite3.Connection
        fetch_page: function(cursor) -> dict
        sleep: function(seconds) -> None
        max_attempts: int (default 3)
        base_delay: float (default 0.1)
        logger: optional logging function
    
    Returns:
        int: number of unique records committed
    """
    # Validate arguments
    if not isinstance(max_attempts, int) or max_attempts <= 0 or isinstance(max_attempts, bool):
        raise ValueError("max_attempts must be a positive integer excluding booleans")
    
    if not isinstance(base_delay, (int, float)) or base_delay < 0:
        raise ValueError("base_delay must be a nonnegative finite number")
    
    # Check for active transaction
    try:
        connection.execute("BEGIN IMMEDIATE")
        raise ValueError("An active transaction is already in progress")
    except sqlite3.OperationalError:
        # If BEGIN IMMEDIATE fails because there's no transaction yet, that's fine.
        # But if it fails due to an existing transaction, we need to catch that.
        # Actually, connection.execute("BEGIN IMMEDIATE") will raise OperationalError 
        # if a transaction is already active.
        pass

    # Fetch all pages first
    all_items = []
    cursor = None
    
    attempts_per_page = 0
    while True:
        try:
            page_data = fetch_page(cursor)
        except TransientError as e:
            attempts_per_page += 1
            if attempts_per_page >= max_attempts:
                raise TransientError(f"Max retries reached for page") from e
            
            delay = base_delay * (2 ** (attempts_per_page - 1))
            sleep(delay)
            continue
        
        # Validate page structure
        next_cursor = validate_page(page_data)
        
        # Check for repeated cursor (cycle detection)
        if next_cursor == cursor:
            raise ValueError("Repeated cursor detected")
        
        # Validate items
        for item in page_data["items"]:
            validate_item(item)
            all_items.append(item)
        
        cursor = next_cursor
        
        # If no more pages, break
        if cursor is None:
            break
    
    # Upsert into database
    try:
        connection.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as e:
        if "transaction already in progress" in str(e):
            raise ValueError("An active transaction is already in progress") from e
        raise

    # Insert records
    for item in all_items:
        connection.execute(
            "INSERT OR REPLACE INTO records (id, name, updated_at) VALUES (?, ?, ?)",
            (item["id"], item["name"], item["updated_at"])
        )
    
    connection.commit()
    
    # Log success without credentials or record contents
    if logger:
        logger(f"Synced {len(all_items)} records successfully")
    
    return len(all_items)


def main(argv=None):
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Sync app")
    parser.add_argument("--url", env_var="SYNC_URL", help="API URL (env: SYNC_URL)")
    parser.add_argument("--db", env_var="SYNC_DB", help="Database path (env: SYNC_DB)")
    parser.add_argument("--max-attempts", type=int, dest="max_attempts", 
                        default=None, help="Max retry attempts (env: SYNC_MAX_ATTEMPTS)")
    parser.add_argument("--base-delay", type=float, dest="base_delay", 
                        default=None, help="Base delay in seconds (env: SYNC_BASE_DELAY)")
    
    args = parser.parse_args(argv)
    
    # Get values from args or env vars
    url = args.url if args.url is not None else args.env_var.get("SYNC_URL")
    db_path = args.db if args.db is not None else args.env_var.get("SYNC_DB")
    
    # If using env vars directly via argparse's env_var, we need to handle it differently.
    # Actually, argparse doesn't support env_var like that in older Python versions easily without custom logic.
    # Let's implement manual env var reading.
    
    if args.url is None:
        url = os.environ.get("SYNC_URL")
    else:
        url = args.url
    
    if args.db is None:
        db_path = os.environ.get("SYNC_DB")
    else:
        db_path = args.db
    
    max_attempts = args.max_attempts
    if max_attempts is None:
        max_attempts = int(os.environ.get("SYNC_MAX_ATTEMPTS", "3"))
    
    base_delay = args.base_delay
    if base_delay is None:
        base_delay = float(os.environ.get("SYNC_BASE_DELAY", "0.1"))
    
    # Check required configuration
    if not url or not db_path:
        print("Error: --url and --db are required (or SYNC_URL and SYNC_DB env vars)", file=sys.stderr)
        return 2
    
    try:
        conn = sqlite3.connect(db_path)
    except Exception as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        return 2
    
    try:
        # We need a fetch_page function. Since we can't import it here easily without circular deps,
        # and the spec says "The model may add helpers", we'll define a local one or use the module's.
        # But wait, main is in sync_app.py. So we can call fetch_http_page from this module.
        # However, we are inside main which is part of the same file.
        # So we can just call app.fetch_http_page? No, we are writing the code for app.
        # So we need to define fetch_http_page before main or use it directly.
        
        # Let's restructure slightly to ensure fetch_http_page is available.
        # Actually, in Python, functions defined at module level are accessible from other functions in the same module.
        # So we can call fetch_http_page here.
        
        def local_fetch_page(cursor):
            return fetch_http_page(url, cursor)
        
        result = sync(conn, local_fetch_page, lambda s: None, max_attempts=max_attempts, base_delay=base_delay)
        
        print(f"Synced {result} records", file=sys.stderr)
        return 0
        
    except TransientError as e:
        print(f"Transient error during sync: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


import os

# Re-define main to include os import if not already present at top level.
# But we can't put imports inside functions. So move os to top.
