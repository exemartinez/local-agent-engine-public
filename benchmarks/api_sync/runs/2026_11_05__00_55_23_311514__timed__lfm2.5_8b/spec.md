# API-to-SQLite synchronization specification

## Contract

Implement `sync_app.py` using Python's standard library. Expose `sync(connection, fetch_page, sleep, *, max_attempts=3, base_delay=0.1, logger=None) -> int`, `fetch_http_page(url, cursor)`, and `main(argv=None) -> int`. The model may add helpers but must preserve these signatures. `connection` is a `sqlite3.Connection`; `fetch_page(cursor)` returns a decoded page dictionary. `sleep(seconds)` is injectable. The sync result is the number of unique records committed.

Each page has exactly the required keys `items` (list) and `next_cursor` (null or a nonempty string). An item is a dictionary with `id` (nonempty string), `name` (nonempty string), and `updated_at` (nonempty ISO 8601 timestamp including a timezone). Preserve the timestamp text. Extra page or item keys are permitted and ignored. Duplicate IDs across pages are resolved by the last occurrence in fetch order.

Fetch the first page using cursor `None`, then follow `next_cursor` until null. Detect a repeated cursor and raise `ValueError`. Invalid pages or records raise `ValueError`. All pages must be validated before any persistent database change. Upsert into `records(id TEXT PRIMARY KEY, name TEXT NOT NULL, updated_at TEXT NOT NULL)` in one transaction; repeated runs must not duplicate rows. A failed fetch, validation, or database operation leaves the database as it was before the call, including if the table did not previously exist. Do not commit or roll back a transaction already owned by the caller: reject an already-active transaction with `ValueError` before fetching.

Define `TransientError` for retryable fetch failures. Retry each individual page at most `max_attempts` total calls, sleeping `base_delay * 2**(attempt-1)` after each non-final `TransientError`. Other exceptions propagate immediately. Validate `max_attempts` is a positive integer excluding booleans and `base_delay` is a nonnegative finite number before fetching. Log successful completion without logging credentials or record contents.

`fetch_http_page` performs a GET using `urllib.request`, appending a URL-encoded `cursor` query parameter only when cursor is not null, preserving existing query parameters. It decodes UTF-8 JSON. HTTP 429, HTTP 5xx, and `urllib.error.URLError` raise `TransientError`; other HTTP errors propagate. No network access is needed in tests.

CLI: `--url` and `--db` override `SYNC_URL` and `SYNC_DB` environment variables; both are required. `--max-attempts` and `--base-delay` override `SYNC_MAX_ATTEMPTS` and `SYNC_BASE_DELAY`, defaults 3 and 0.1. `main` returns 0 on success, 2 for invalid configuration, 1 for sync failure, and writes useful diagnostics to stderr. Running the file directly exits with that code. Do not log the URL because it may contain credentials.

## Acceptance

Public and hidden tests must pass; line coverage of `sync_app.py` must be at least 90%. Tests must mock all HTTP requests and sleeps, and use in-memory or temporary SQLite databases. A successful run alone does not establish production readiness.
