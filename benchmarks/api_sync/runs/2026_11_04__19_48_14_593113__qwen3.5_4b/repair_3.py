import sqlite3, urllib.request, json, logging, sys, argparse, time, types
from urllib.parse import urlencode

class TransientError(Exception):
    pass

def fetch_http_page(url: str, cursor: str | None) -> dict:
    # Preserve existing query parameters
    params = {}
    if cursor is not None:
        params['cursor'] = cursor
    
    try:
        req = urllib.request.Request(url)
        if params:
            req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, ValueError):
        raise TransientError("Fetch failed") from None
    
    # Check for HTTP error status codes that should propagate
    if resp.status_code == 404:
        raise Exception(f"HTTP 404 Not Found")
    
    if resp.status_code >= 500 or resp.status_code == 429:
        raise TransientError(f"HTTP {resp.status_code}") from None
    
    # Validate page structure
    if 'items' not in data or 'next_cursor' not in data:
        raise ValueError("Invalid page structure")
    
    return data

def validate_page(page: dict) -> list:
    items = page.get('items', [])
    next_cursor = page.get('next_cursor')
    seen_ids = set()
    
    for item in items:
        if 'id' not in item or 'name' not in item or 'updated_at' not in item:
            raise ValueError("Invalid record structure")
        
        rid = str(item['id'])
        if rid in seen_ids:
            raise ValueError(f"Duplicate ID {rid}")
        seen_ids.add(rid)
    
    return items, next_cursor

def upsert_records(conn, records: list[dict]) -> int:
    try:
        conn.execute("BEGIN")
        stmt = "INSERT OR REPLACE INTO records(id TEXT PRIMARY KEY, name TEXT NOT NULL, updated_at TEXT NOT NULL) VALUES (?, ?, ?)"
        conn.executemany(stmt, [(r['id'], r['name'], r['updated_at']) for r in records])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    
    return len(records)

def sync(connection, fetch_page, sleep, *, max_attempts=3, base_delay=0.1, logger=None) -> int:
    # Validate parameters before fetching
    if not isinstance(max_attempts, int) or bool(max_attempts):
        raise ValueError("max_attempts must be positive integer")
    
    if not isinstance(base_delay, (int, float)) or base_delay < 0:
        raise ValueError("base_delay must be nonnegative finite number")
    
    # Check for active transaction - sqlite3 doesn't have in_transaction() method
    try:
        cursor = connection.execute("PRAGMA table_info(records)")
        if cursor.fetchone():
            raise ValueError("Active transaction detected")
    except Exception:
        pass
    
    seen_cursors = set()
    all_records = []
    page_cursor = None
    
    while True:
        # Retry logic for each page
        attempt = 0
        last_transient_error = None
        
        while attempt < max_attempts:
            try:
                page = fetch_page(page_cursor)
                break
            except TransientError as e:
                attempt += 1
                if attempt >= max_attempts:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                sleep(delay)
                last_transient_error = e
        
        # Check for next_cursor and handle pagination
        if 'next_cursor' in page and page['next_cursor'] is not None:
            next_cursor = str(page['next_cursor'])
            if next_cursor in seen_cursors:
                raise ValueError("Cursor cycle detected")
            seen_cursors.add(next_cursor)
        else:
            break
        
        items, next_cursor = validate_page(page)
        all_records.extend(items)
        page_cursor = next_cursor
    
    # Upsert records atomically
    try:
        count = upsert_records(connection, all_records)
        if logger:
            logger.info("Sync completed")
        return count
    except Exception:
        raise

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default=None)
    parser.add_argument('--db', default=None)
    parser.add_argument('--max-attempts', type=int, default=3)
    parser.add_argument('--base-delay', type=float, default=0.1)
    
    args = parser.parse_args(argv)
    
    # Get URL and DB from args or environment variables
    url = args.url or os.environ.get('SYNC_URL')
    db = args.db or os.environ.get('SYNC_DB')
    
    if not url or not db:
        print("Missing URL or DB", file=sys.stderr)
        return 2
    
    try:
        conn = sqlite3.connect(db)
        count = sync(conn, fetch_http_page, time.sleep, max_attempts=args.max_attempts, base_delay=args.base_delay)
        conn.close()
        return 0
    except Exception as e:
        print(f"Sync failed: {e}", file=sys.stderr)
        return 1

import os
