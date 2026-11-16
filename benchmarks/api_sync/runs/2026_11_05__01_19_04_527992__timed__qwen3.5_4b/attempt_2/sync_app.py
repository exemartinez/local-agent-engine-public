import argparse
import json
import os
import re
import sqlite3
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen


class TransientError(Exception):
    """Raised for retryable HTTP or network failures."""
    pass


def fetch_http_page(url: str, cursor) -> dict:
    """Fetch a page from the API and return decoded JSON."""
    params = []
    if cursor is not None:
        params.append(f"cursor={cursor}")

    full_url = url
    if params:
        try:
            parsed = urlsplit(url)
            existing_qs = parse_qs(parsed.query)
            if existing_qs:
                new_qs_parts = []
                for k, v in existing_qs.items():
                    if isinstance(v, list):
                        new_qs_parts.extend([f"{k}={val}" for val in v])
                    else:
                        new_qs_parts.append(f"{k}={v}")

                new_qs_parts.append(params[0])
                full_url = f"{parsed.scheme}:{parsed.netloc}{parsed.path}?{'&'.join(new_qs_parts)}"
        except Exception:
            try:
                existing = url.split('?')[1] if '?' in url else ""
                full_url = f"{url}?{existing}&{params[0]}"
            except Exception:
                full_url = f"{url}?{params[0]}"

    try:
        with urlopen(full_url) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data
    except HTTPError as e:
        if e.code in (429, 500, 501, 502, 503, 504):
            raise TransientError(f"HTTP {e.code}: {e.reason}") from None
        raise
    except URLError as e:
        raise TransientError(f"Network error: {e.reason}") from None


def validate_page(data: dict) -> bool:
    """Validate page structure."""
    if not isinstance(data, dict):
        return False
    if "items" not in data or not isinstance(data["items"], list):
        return False
    if "next_cursor" not in data:
        return False
    return True


def validate_item(item: dict) -> bool:
    """Validate item structure."""
    if not isinstance(item, dict):
        return False
    required = ["id", "name", "updated_at"]
    for key in required:
        if key not in item or not item[key]:
            return False
    return True


def validate_records(records: list) -> bool:
    """Validate all records."""
    return all(validate_item(r) for r in records)


def sync(connection, fetch_page, sleep, *, max_attempts=3, base_delay=0.1, logger=None) -> int:
    """Synchronize data from API to SQLite."""
    if not isinstance(max_attempts, int) or max_attempts <= 0 or isinstance(max_attempts, bool):
        raise ValueError("max_attempts must be a positive integer")
    if not isinstance(base_delay, (int, float)) or base_delay < 0:
        raise ValueError("base_delay must be a nonnegative finite number")

    try:
        cursor = None
        all_records = []
        last_cursor = None

        for attempt in range(max_attempts):
            if attempt > 0:
                sleep(base_delay * (2 ** (attempt - 1)))

            page_data = fetch_page(cursor)
            if not validate_page(page_data):
                raise ValueError("Invalid page structure")

            next_cursor = page_data.get("next_cursor")
            if next_cursor is None:
                break

            if next_cursor == last_cursor:
                raise ValueError("Repeated cursor detected")
            last_cursor = next_cursor

            for item in page_data["items"]:
                if not validate_item(item):
                    raise ValueError("Invalid record structure")
                all_records.append(item)

            cursor = next_cursor

        if not validate_records(all_records):
            raise ValueError("Validation failed during record processing")

        with connection:
            try:
                existing_ids = {r[0] for r in connection.execute("SELECT id FROM records").fetchall()}
                new_ids = set()
                for rec in all_records:
                    if rec["id"] not in existing_ids:
                        new_ids.add(rec["id"])
                        connection.execute(
                            "INSERT INTO records (id, name, updated_at) VALUES (?, ?, ?)",
                            (rec["id"], rec["name"], rec["updated_at"]),
                        )
                return len(new_ids)
            except sqlite3.OperationalError:
                raise ValueError("Database operation failed")

    except TransientError:
        if attempt < max_attempts - 1:
            raise
        raise
    except Exception as e:
        raise


def main(argv=None):
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sync API to SQLite")
    parser.add_argument("--url", default=os.environ.get("SYNC_URL"))
    parser.add_argument("--db", default=os.environ.get("SYNC_DB"))
    parser.add_argument("--max-attempts", type=int, default=int(os.environ.get("SYNC_MAX_ATTEMPTS", 3)))
    parser.add_argument("--base-delay", type=float, default=float(os.environ.get("SYNC_BASE_DELAY", 0.1)))

    args = parser.parse_args(argv)

    if not args.url or not args.db:
        print("Error: --url and --db are required", file=sys.stderr)
        return 2

    try:
        conn = sqlite3.connect(args.db)
        cursor = None

        def fetch_page(c):
            return fetch_http_page(args.url, c)

        def sleep_func(s):
            import time
            time.sleep(s)

        count = sync(conn, fetch_page, sleep_func, max_attempts=args.max_attempts, base_delay=args.base_delay)
        print(f"Synced {count} records")
        return 0
    except Exception as e:
        if isinstance(e, TransientError):
            print(f"Transient error after retries: {e}", file=sys.stderr)
        else:
            print(f"Sync failed: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
