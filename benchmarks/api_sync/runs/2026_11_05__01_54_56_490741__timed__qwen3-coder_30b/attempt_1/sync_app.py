import sqlite3
import json
import urllib.request
import urllib.parse
import os
import sys
import logging
from urllib.error import HTTPError, URLError

class TransientError(Exception):
    pass

def fetch_http_page(url, cursor):
    params = {}
    if cursor is not None:
        params['cursor'] = cursor
    
    parsed_url = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed_url.query)
    query.update(params)
    
    # Reconstruct URL with new query parameters
    new_query = urllib.parse.urlencode(query, doseq=True)
    new_url = urllib.parse.urlunparse((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        parsed_url.params,
        new_query,
        parsed_url.fragment
    ))
    
    try:
        response = urllib.request.urlopen(new_url)
        data = response.read().decode('utf-8')
        return json.loads(data)
    except HTTPError as e:
        if e.code in (429, 500, 502, 503):
            raise TransientError() from e
        else:
            raise
    except URLError:
        raise TransientError()

def sync(connection, fetch_page, sleep, *, max_attempts=3, base_delay=0.1, logger=None):
    # Validate inputs
    if not isinstance(max_attempts, int) or max_attempts <= 0 or isinstance(max_attempts, bool):
        raise ValueError("max_attempts must be a positive integer")
    
    if not isinstance(base_delay, (int, float)) or base_delay < 0 or base_delay != base_delay:  # Check for NaN
        raise ValueError("base_delay must be a non-negative finite number")
    
    # Check if transaction is already active
    if connection.in_transaction:
        raise ValueError("Database connection is already in a transaction")
    
    # Fetch all pages
    pages = []
    current_cursor = None
    seen_cursors = set()
    
    # Fetch first page with retries
    for attempt in range(max_attempts):
        try:
            page = fetch_page(current_cursor)
            break
        except TransientError:
            if attempt == max_attempts - 1:
                raise
            sleep(base_delay * (2 ** attempt))
    else:
        # This shouldn't be reached due to the loop structure, but just in case
        raise TransientError()
    
    while True:
        # Validate page structure
        if not isinstance(page, dict):
            raise ValueError("Invalid page: must be a dictionary")
        
        if 'items' not in page or 'next_cursor' not in page:
            raise ValueError("Invalid page: missing required keys")
        
        items = page['items']
        next_cursor = page['next_cursor']
        
        if not isinstance(items, list):
            raise ValueError("Invalid page: items must be a list")
        
        # Validate each item
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Invalid item: must be a dictionary")
            
            required_keys = ['id', 'name', 'updated_at']
            for key in required_keys:
                if key not in item or not isinstance(item[key], str) or not item[key]:
                    raise ValueError(f"Invalid item: missing or empty {key}")
            
            # Validate timestamp format (basic check)
            timestamp = item['updated_at']
            if not timestamp.endswith(('+00:00', 'Z')) and not any(tz in timestamp for tz in ['+', '-', 'T']):
                raise ValueError("Invalid timestamp format")
        
        pages.append(page)
        
        # Check for repeated cursor
        if next_cursor in seen_cursors:
            raise ValueError("Repeated cursor detected")
        seen_cursors.add(next_cursor)
        
        # Check if we're done
        if next_cursor is None:
            break
        
        # Fetch next page with retries
        current_cursor = next_cursor
        for attempt in range(max_attempts):
            try:
                page = fetch_page(current_cursor)
                break
            except TransientError:
                if attempt == max_attempts - 1:
                    raise
                sleep(base_delay * (2 ** attempt))
        else:
            # This shouldn't be reached due to the loop structure, but just in case
            raise TransientError()
    
    # Prepare data for upsert
    records = {}
    for page in pages:
        for item in page['items']:
            records[item['id']] = (item['name'], item['updated_at'])
    
    # Perform database operation in a transaction
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
            
            for record_id, (name, updated_at) in records.items():
                connection.execute(upsert_sql, (record_id, name, updated_at))
            
            # Return count of unique records
            count = len(records)
            
            if logger:
                logger.info(f"Sync completed successfully, committed {count} unique records")
                
            return count
            
    except Exception as e:
        # If we get here, the transaction was rolled back automatically
        raise

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    
    try:
        # Parse arguments
        url = os.environ.get('SYNC_URL')
        db_path = os.environ.get('SYNC_DB')
        max_attempts = int(os.environ.get('SYNC_MAX_ATTEMPTS', '3'))
        base_delay = float(os.environ.get('SYNC_BASE_DELAY', '0.1'))
        
        i = 0
        while i < len(argv):
            if argv[i] == '--url' and i + 1 < len(argv):
                url = argv[i+1]
                i += 2
            elif argv[i] == '--db' and i + 1 < len(argv):
                db_path = argv[i+1]
                i += 2
            elif argv[i] == '--max-attempts' and i + 1 < len(argv):
                max_attempts = int(argv[i+1])
                i += 2
            elif argv[i] == '--base-delay' and i + 1 < len(argv):
                base_delay = float(argv[i+1])
                i += 2
            else:
                print(f"Unknown argument: {argv[i]}", file=sys.stderr)
                return 2
                i += 1
        
        # Validate required configuration
        if not url or not db_path:
            print("SYNC_URL and SYNC_DB must be set via environment variables or --url/--db arguments", file=sys.stderr)
            return 2
        
        # Setup logging
        logger = logging.getLogger('sync_app')
        logger.setLevel(logging.INFO)
        
        # Create database connection
        try:
            conn = sqlite3.connect(db_path)
            def fetch_page(cursor):
                return fetch_http_page(url, cursor)
            
            def sleep(seconds):
                import time
                time.sleep(seconds)
                
            result = sync(conn, fetch_page, sleep, max_attempts=max_attempts, base_delay=base_delay, logger=logger)
            conn.close()
            return 0
            
        except Exception as e:
            if isinstance(e, ValueError):
                print(f"Sync failed: {e}", file=sys.stderr)
                return 1
            else:
                raise
                
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
