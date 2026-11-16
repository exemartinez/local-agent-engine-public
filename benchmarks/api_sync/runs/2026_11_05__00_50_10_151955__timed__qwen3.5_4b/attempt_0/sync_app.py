"""Synchronize a paginated HTTP feed into SQLite atomically."""

import argparse
from datetime import datetime
import json
import logging
import math
import os
import sqlite3
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


class TransientError(Exception):
    """A page request can be retried."""


def fetch_http_page(url, cursor):
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if cursor is not None:
        query.append(("cursor", cursor))
    target = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    try:
        with urlopen(Request(target, method="GET")) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429 or 500 <= exc.code <= 599:
            raise TransientError("retryable HTTP response") from exc
        raise
    except URLError as exc:
        raise TransientError("transport failure") from exc


def _record(item):
    if not isinstance(item, dict):
        raise ValueError("record must be an object")
    values = []
    for key in ("id", "name", "updated_at"):
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("record fields must be nonempty strings")
        values.append(value)
    try:
        stamp = datetime.fromisoformat(values[2])
        if stamp.utcoffset() is None:
            raise ValueError("timestamp needs timezone")
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid timestamp") from exc
    return tuple(values)


def sync(connection, fetch_page, sleep, *, max_attempts=3, base_delay=0.1, logger=None):
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")
    if isinstance(base_delay, bool) or not isinstance(base_delay, (int, float)) or not math.isfinite(base_delay) or base_delay < 0:
        raise ValueError("base_delay must be a nonnegative finite number")
    if connection.in_transaction:
        raise ValueError("caller already owns a transaction")
    cursor = None
    seen = set()
    records = {}
    while True:
        for attempt in range(max_attempts):
            try:
                page = fetch_page(cursor)
                break
            except TransientError:
                if attempt + 1 == max_attempts:
                    raise
                sleep(base_delay * 2 ** attempt)
        if not isinstance(page, dict) or not isinstance(page.get("items"), list) or "next_cursor" not in page:
            raise ValueError("invalid page")
        for item in page["items"]:
            record = _record(item)
            records[record[0]] = record
        cursor = page["next_cursor"]
        if cursor is None:
            break
        if not isinstance(cursor, str) or not cursor.strip() or cursor in seen:
            raise ValueError("invalid or repeated cursor")
        seen.add(cursor)
    try:
        connection.execute("BEGIN")
        connection.execute("CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, name TEXT NOT NULL, updated_at TEXT NOT NULL)")
        connection.executemany("INSERT INTO records (id, name, updated_at) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, updated_at=excluded.updated_at", records.values())
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    (logger or logging.getLogger(__name__)).info("Synchronization complete: %d records", len(records))
    return len(records)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv("SYNC_URL"))
    parser.add_argument("--db", default=os.getenv("SYNC_DB"))
    parser.add_argument("--max-attempts", default=os.getenv("SYNC_MAX_ATTEMPTS", "3"))
    parser.add_argument("--base-delay", default=os.getenv("SYNC_BASE_DELAY", "0.1"))
    try:
        args = parser.parse_args(argv)
        if not args.url or not args.db:
            raise ValueError("url and db are required")
        attempts, delay = int(args.max_attempts), float(args.base_delay)
        if attempts < 1 or not math.isfinite(delay) or delay < 0:
            raise ValueError("invalid retry settings")
    except (ValueError, TypeError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    try:
        with sqlite3.connect(args.db) as connection:
            sync(connection, lambda cursor: fetch_http_page(args.url, cursor), time.sleep, max_attempts=attempts, base_delay=delay)
        return 0
    except Exception as exc:
        print(f"Synchronization failed: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
