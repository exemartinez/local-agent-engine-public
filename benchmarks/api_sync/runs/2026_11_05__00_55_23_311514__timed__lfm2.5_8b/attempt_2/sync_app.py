<think>
We need to produce the full corrected sync_app.py as Python code only, based on the specification and current code that has an error (missing import of Callable). Also we must ensure it passes tests with coverage >=90%. The current code likely missing import typing. Let's examine.

The error: In main, they use Callable[[str], Dict[str, Any]] but didn't import Callable. Should be from typing import Callable. Also maybe other issues: The sync function signature includes *max_attempts=3, base_delay=0.1, logger=None) -> int. That's fine.

But there may be other missing imports: In the class definition they used Dict, Any, Optional, Tuple but not imported. Actually they have from typing import Dict, Any, Optional, Tuple? At top they didn't include that. They have "from typing import Dict, Any, Optional, Tuple". Yes they have that line. So Callable is missing.

Also need to ensure the function returns int (number of unique records committed). The sync function currently returns len(seen_ids) after upsert. That's correct.

Potential other issues: In main, they call _log_message with logger=_log_message? Actually they pass _log_message as logger argument but also later use _log_message again in return statements. That's fine.

But there is a bug: In sync function, they have "if hasattr(connection, "_transaction_active") and connection._transaction_active:" but they didn't check if attribute exists before accessing? Actually they used hasattr to avoid AttributeError. However later they raise ValueError "already active transaction". That's okay.

But there is also a problem: They open a new connection each time? In main they create sqlite3.connect(db). That's fine.

Now we need to produce corrected code, ensuring all requirements are met. Also ensure that the module can be imported and used without errors. Let's rewrite with proper imports and maybe improve some details:

- Add import Callable from typing.
- Ensure validation of config: max_attempts positive integer, base_delay nonnegative finite number. Already done.

- In sync, they need to detect repeated cursor across pages. They currently store seen_ids but not next_cursor detection? Actually they break when next_cursor is None. However they also need to detect if a cursor repeats before reaching null. The spec: "Detect a repeated cursor and raise ValueError." How to detect? Possibly while fetching pages, if we encounter a cursor that has been seen earlier in the same sync run (i.e., previously fetched page). Since we store seen_ids for items, but cursors are not stored. We need to keep track of cursors encountered. If we see a cursor that is already in a set of seen cursors, raise ValueError. Also need to handle case where next_cursor may be null or empty string? The spec says next_cursor is nonempty string if present. So we can store each cursor value as we fetch pages; if duplicate appears before reaching null, raise.

Implementation: In the while loop, after fetching page and before processing items, check if cursor in seen_cursors; if yes, raise ValueError. Add to seen_cursors set.

Also need to ensure that we don't commit any changes until after all pages processed successfully. That's already done with transaction.

Also need to ensure that if fetch fails (TransientError or other), we rollback and not commit. Already there is try-except around upsert; but what about validation errors before transaction? Those raise ValueError before transaction, so no DB changes. Good.

Now also need to handle the case where max_attempts > 1: they want retry each individual page at most max_attempts total calls, sleeping base_delay * 2**(attempt-1) after each non-final TransientError. The current sync function does not implement per-page retries; it just retries whole sync? Actually the spec says "Retry each individual page at most max_attempts total calls". That means if a fetch fails, we should retry that page up to max_attempts times before moving on. However the current code only retries once (since they call fetch_http_page directly). We need to implement per-page retry logic.

But note: The sync function is called from main with a fetch_page function passed in. That fetch_page may be the original one that raises TransientError for certain errors. However we need to incorporate retry logic inside sync, not just rely on caller-level retries. The spec says "Retry each individual page at most max_attempts total calls". So we must implement a loop around fetching each page with up to max_attempts attempts, using the provided sleep delay.

Implementation plan:

- In sync, before starting transaction, we need to fetch pages sequentially.
- For each page, attempt up to max_attempts times:
   - Try to fetch using fetch_page (which may raise TransientError or other).
   - If success, validate items and store seen_ids.
   - If fails due to TransientError, wait base_delay * 2**(attempt-1) after each non-final error, then retry.
   - After max_attempts, if still failing, raise the last exception (or propagate). The spec says "Retry each individual page at most max_attempts total calls". So we should not continue to next pages until this page is successfully fetched. If fails after attempts, we should abort sync and rollback any partial changes? The spec: "All pages must be validated before any persistent database change." That suggests if a page fails after retries, we should not commit any changes (i.e., rollback). Also we need to raise an error that will cause main to return 1. However the spec also says "Invalid pages or records raise ValueError". For fetch failures, they want to raise TransientError which is caught inside sync and then rollback and re-raise. That's fine.

Thus we need to modify sync accordingly.

Also need to ensure that if any validation error occurs (e.g., missing keys), we rollback before committing. Already there is try-except around transaction; but if validation fails before transaction, no DB changes. However if validation fails after some pages have been inserted? Actually they store seen_ids and upsert after all pages validated. That's fine.

Now about the duplicate cursor detection: We need to keep a set of cursors we've seen. If we encounter a cursor that is already in seen_cursors, raise ValueError. However note that the first page may have next_cursor = "abc". The second page may have next_cursor = "abc" again (i.e., repeated). That would be duplicate across pages. So we need to detect that before fetching the second page? Actually we fetch first page with cursor None, get items and next_cursor "abc". We store seen_ids for items, and also add "abc" to seen_cursors. Then after processing items, if next_cursor is not null, we set cursor = next_cursor. Before fetching the next page, check if cursor in seen_cursors; if yes, raise ValueError. That will detect repeated cursors.

Edge Cases: The spec says "Detect a repeated cursor and raise ValueError." It doesn't specify whether it's across pages or within same page? Probably across pages. So implement as above.

Now we need to ensure that the function returns number of unique records committed (len(seen_ids)). That's after all pages processed successfully, before upsert? Actually they upsert after validation and before commit. The number of unique records is based on items validated earlier; duplicates across pages are resolved by last occurrence in fetch order. So we can compute len(seen_ids) after processing all pages (i.e., after validation). That's fine.

Now about the CLI: They want to log successful completion without credentials or record contents. Already they log "Sync completed successfully". Good.

Now about environment variables: The code already reads SYNC_URL and SYNC_DB from env, with defaults? Actually they require both --url and --db arguments; but also allow overriding via env. If url is None after parsing args, they fallback to env_url else use provided url. Same for db. That's fine.

Now about the return codes: main returns 0 on success, 2 for invalid configuration, 1 for sync failure. Already done.

Now we need to ensure that the code passes tests with coverage >=90%. We'll need to add more test coverage? But we cannot see existing tests. However we can improve by adding docstrings and maybe some inline comments. Also ensure no missing imports.

Potential other issues: In sync, they have "if hasattr(connection, "_transaction_active") and connection._transaction_active:" but they didn't check if attribute exists before accessing? Actually they used hasattr to avoid AttributeError. However later they raise ValueError "already active transaction". That's fine.

But there is also a bug: They open a new connection each time sync is called; but main passes the same connection object (sqlite3.connect(db)). If there is already an active transaction on that connection, they will detect it and raise error. However they also need to ensure that if there is no active transaction, they can start one. That's fine.

Now we need to produce final corrected code. Let's rewrite the entire file with proper imports and modifications.

We'll add:

from typing import Callable

Also maybe from urllib.parse import urlparse, parse_qs? Actually fetch_http_page uses _parse_url_params which uses urllib.parse. So we need to import that inside that function or at top. Already they have import urllib.request, urllib.error, etc. We can add from urllib.parse import urlparse, parse_qs.

But the current code doesn't import them; but they use _parse_url_params which uses urllib.parse. That's okay because it's imported? Actually they didn't import parse_qs or urlparse. However they used `_parse_url_params` defined earlier that uses `urllib.parse.urlparse` and `urllib.parse.urlencode`. Those are used but not imported. Wait, the code includes:

import urllib.request
import urllib.error
import time
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

But they didn't import urlparse or parse_qs. However they use `_parse_url_params` which uses `urllib.parse.urlparse` and `urllib.parse.urlencode`. That would cause NameError at runtime. Indeed the original code had an error: "NameError: name 'Callable' is not defined". But also there may be missing imports for urlparse. However the spec didn't mention that; maybe they omitted import statements inadvertently. We need to add them.

Thus we need to add:

from urllib.parse import urlparse, parse_qs

But note that `_parse_url_params` uses `urllib.parse.urlparse` and `urllib.parse.urlencode`. So we should import those.

Alternatively we could change `_parse_url_params` to use `urlparse` and `parse_qs` directly without extra imports? Actually they already have `import urllib.request` etc. But they didn't import parse_qs. However they used `urllib.parse.urlparse` which is a submodule; need to import it.

Thus we should add:

from urllib.parse import urlparse, parse_qs

Now also need to ensure that the function signature for fetch_http_page uses Callable from typing.

Now incorporate per-page retry logic. Let's design:

def sync(...):
    ...
    # Detect already active transaction
    if hasattr(connection, "_transaction_active") and connection._transaction_active:
        raise ValueError("already active transaction")

    seen_ids = set()
    seen_cursors = set()
    cursor = None

    while True:
        try:
            url_page = fetch_http_page(connection, cursor)
        except TransientError as e:
            # This is a retryable error; we will handle retries
            pass
        else:
            # Validate page
            items = url_page.get("items")
            next_cursor = url_page.get("next_cursor")
            if not isinstance(items, list) or not isinstance(next_cursor, str):
                raise ValueError(...)
            for item in items:
                # validation...
            # duplicate detection for items
            for item in items:
                id_val = item["id"]
                if id_val in seen_ids:
                    raise ValueError(f"duplicate item id: {id_val}")
                seen_ids.add(id_val)
            # store cursor for later detection
            if next_cursor:
                if next_cursor in seen_cursors:
                    raise ValueError(f"repeated cursor: {next_cursor}")
                seen_cursors.add(next_cursor)
                cursor = next_cursor
            else:
                break

        # If we got here, either fetch succeeded or exhausted retries.
        if isinstance(url_page, dict) and not any(issubclass(e, TransientError) for e in exceptions)? Actually we need to know if we have reached max attempts. We'll implement a loop with attempt count.

Simplify: Use a while True loop with attempt variable starting at 1. For each attempt up to max_attempts:
   try:
       url_page = fetch_http_page(connection, cursor)
   except TransientError:
       if attempt == max_attempts:
           raise
       delay = base_delay * (2 ** (attempt - 1))
       time.sleep(delay)
       continue
   else:
       # success
       break

But we also need to handle other exceptions? The spec says "Other exceptions propagate immediately." So if fetch_http_page raises something else (e.g., URLError), it should propagate, not retry. So we can catch only TransientError.

Thus implement:

attempt = 1
while True:
    try:
        url_page = fetch_http_page(connection, cursor)
    except TransientError:
        if attempt == max_attempts:
            raise
        delay = base_delay * (2 ** (attempt - 1))
        time.sleep(delay)
        attempt += 1
        continue
    # success
    break

Now after loop, we have url_page (dict). Then proceed with validation and upsert.

But note that we also need to ensure that if any validation error occurs, we rollback. Since we haven't started transaction yet, there are no changes committed. So fine.

Now we need to ensure that the transaction is begun only after all pages validated. That's already done.

Now about the "seen_ids" set: It includes ids from items across all pages. However if duplicate item id appears across pages, we should raise error before upsert. Already we check duplicates while processing each page. Good.

Now about the "record" dict storing "_seen_id": This is used to detect duplicates? Actually they store a temporary marker to avoid overwriting same id within same page? But they also have duplicate detection across items. The extra field "_seen_id" may be unnecessary but we can keep it for completeness. However note that they add record["_seen_id"] = id_val, which will be overwritten each time the same id appears in different pages (since they process items sequentially). That's fine.

Now about the "seen_ids" set: It is used to detect duplicate item ids across pages? Actually they also check duplicates while iterating items. So we can keep both.

Now we need to ensure that after successful sync, we upsert all seen_ids into DB using INSERT OR REPLACE (or maybe unique constraint ensures no duplicates). That's fine.

Now about the return value: len(seen_ids). That's number of unique records committed. Good.

Now we need to adjust main to use Callable import? Already imported via typing.

Now also ensure that the function signature for sync includes *max_attempts=3, base_delay=0.1, logger=None -> int. It does.

Now about logging: They log errors with _log_message. That's fine.

Now we need to produce final code. Let's write it fully.

Potential missing imports: In main they use Callable? No, they don't. So only need to add import for Callable.

Also note that the original code had a line:

if hasattr(connection, "_transaction_active") and connection._transaction_active:
    raise ValueError("already active transaction")

But they didn't check if attribute exists before accessing? Actually they used hasattr, which is safe. However later they raise ValueError with string "already active transaction". That's fine.

Now we need to ensure that the code doesn't have any syntax errors. Let's rewrite:

"""Synchronization module for API-to-SQLite."""
import sqlite3
import json
import urllib.request
import urllib.error
import time
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs

class TransientError(Exception):
    """Raised for retryable fetch failures."""
    pass


def _validate_config(max_attempts: int, base_delay: float) -> None:
    """Validate configuration parameters."""
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer")
    if not (isinstance(base_delay, (int, float)) and base_delay >= 0):
        raise ValueError("base_delay must be a nonnegative finite number")


def _parse_url_params(url: str) -> Dict[str, Any]:
    """Parse URL query parameters preserving existing ones."""
    parsed = urlparse(url)
    if parsed.query:
        return dict(parse_qs(parsed.query))
    return {}


def fetch_http_page(url: str, cursor: Optional[str]) -> Dict[str, Any]:
    """
    Perform a GET request to `url`, appending a URL‑encoded ``cursor`` query
    parameter when ``cursor`` is not ``None``. Returns the decoded JSON payload.
    Raises : TransientError for HTTP 429, 5xx errors and URLError; otherwise
    propagates other exceptions.
    """
    if cursor is None:
        return _parse_url_params(url)

    params = _parse_url_params(url)
    if params:
        # Replace existing cursor param with the new value
        params['cursor'] = urllib.parse.urlencode({'cursor': cursor})
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"
    try:
        with urllib.request.urlopen(full_url) as response:
            if response.status in (429, 500, 501, 502, 503, 504):
                raise TransientError("Rate limit or server error")
            return json.load(response)
    except urllib.error.URLError as e:
        raise TransientError(f"URL error: {e}") from e


def _log_message(message: str, logger=None) -> None:
    """Utility to write diagnostic messages to stderr."""
    if logger is not None:
        logger.error(message)
    else:
        sys.stderr.write(message + "\n")


def sync(
    connection: sqlite3.Connection,
    fetch_page: Callable[[str], Dict[str, Any]],
    sleep: Callable[[int], None],
    *
