"""Candidate implementation goes here. See spec.md for the public contract."""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

class TransientError(Exception):
    pass


def fetch_http_page(url: str, cursor: Optional[str]) -> Dict[str, Any]:
    if cursor is not None:
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)
        query_params['cursor'] = [cursor]
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        url = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
    
    try:
        response = urllib.request.urlopen(url)
        data = response.read().decode('utf-8')
        return json.loads(data)
    except urllib.error.HTTPError as e:
        if e.code in (429, 500, 503):
            raise TransientError() from e
        raise
    except urllib.error.URLError as e:
        raise TransientError() from e


def sync(connection: sqlite3.Connection, fetch_page, sleep, *, max_attempts=3, base_delay=0.1, logger=None) -> int:
    # Validate inputs
    if not isinstance(max_attempts, int) or max_attempts <= 0 or isinstance(max_attempts, bool):
        raise ValueError("max_attempts must be a positive integer")
    if not isinstance(base_delay, (int, float)) or base_delay < 0 or base_delay != base_delay:  # NaN check
        raise ValueError("base_delay must be a nonnegative finite number")
    
    # Check for active transaction
    if connection.in_transaction:
        raise ValueError("Database connection has an active transaction")
    
    # Fetch all pages
    pages = []
    current_cursor = None
    seen_cursors = set()
    
    while True:
        # Retry logic per page
        attempt = 0
        while True:
            try:
                page = fetch_page(current_cursor)
                break
            except TransientError as e:
                attempt += 1
                if attempt >= max_attempts:
                    raise
                sleep(base_delay * (2 ** (attempt - 1)))
        
        # Validate page structure
        if not isinstance(page, dict):
            raise ValueError("Page must be a dictionary")
        if 'items' not in page or 'next_cursor' not in page:
            raise ValueError("Page must have 'items' and 'next_cursor' keys")
        if not isinstance(page['items'], list):
            raise ValueError("'items' must be a list")
        if page['next_cursor'] is not None and (not isinstance(page['next_cursor'], str) or not page['next_cursor']):
            raise ValueError("'next_cursor' must be null or a non-empty string")
        
        # Check for repeated cursor
        if current_cursor in seen_cursors:
            raise ValueError("Repeated cursor detected")
        seen_cursors.add(current_cursor)
        
        pages.append(page)
        
        # Move to next cursor
        current_cursor = page['next_cursor']
        if current_cursor is None:
            break
    
    # Validate all items before any database changes
    records = {}
    for page in pages:
        for item in page['items']:
            # Validate item structure
            if not isinstance(item, dict):
                raise ValueError("Item must be a dictionary")
            if 'id' not in item or 'name' not in item or 'updated_at' not in item:
                raise ValueError("Item must have 'id', 'name', and 'updated_at'")
            if not isinstance(item['id'], str) or not item['id']:
                raise ValueError("'id' must be a non-empty string")
            if not isinstance(item['name'], str) or not item['name']:
                raise ValueError("'name' must be a non-empty string")
            if not isinstance(item['updated_at'], str) or not item['updated_at']:
                raise ValueError("'updated_at' must be a non-empty string")
            
            # Store the latest version of each record
            records[item['id']] = {
                'id': item['id'],
                'name': item['name'],
                'updated_at': item['updated_at']
            }
    
    # Perform database transaction
    try:
        with connection:
            # Create table if it doesn't exist
            connection.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Upsert records
            upsert_sql = """
                INSERT OR REPLACE INTO records (id, name, updated_at)
                VALUES (?, ?, ?)
            """
            for record in records.values():
                connection.execute(upsert_sql, (record['id'], record['name'], record['updated_at']))
            
            return len(records)
    except Exception:
        # Any exception during database operation should rollback the transaction
        raise


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="Override SYNC_URL environment variable")
    parser.add_argument("--db", help="Override SYNC_DB environment variable")
    parser.add_argument("--max-attempts", type=int, help="Override SYNC_MAX_ATTEMPTS environment variable")
    parser.add_argument("--base-delay", type=float, help="Override SYNC_BASE_DELAY environment variable")
    
    args = parser.parse_args(argv)
    
    # Get configuration from environment or CLI
    url = args.url or os.environ.get("SYNC_URL")
    db_path = args.db or os.environ.get("SYNC_DB")
    max_attempts = args.max_attempts or int(os.environ.get("SYNC_MAX_ATTEMPTS", 3))
    base_delay = args.base_delay or float(os.environ.get("SYNC_BASE_DELAY", 0.1))
    
    if not url or not db_path:
        print("Error: --url and --db are required", file=sys.stderr)
        return 2
    
    try:
        connection = sqlite3.connect(db_path)
        result = sync(connection, fetch_http_page, time.sleep, max_attempts=max_attempts, base_delay=base_delay)
        connection.close()
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
