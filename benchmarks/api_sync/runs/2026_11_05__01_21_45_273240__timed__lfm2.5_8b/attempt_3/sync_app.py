import requests
import urllib.parse
from sqlalchemy import create_engine, text

# ----------------------------------------------------------------------
# Helper functions (assumed to be defined elsewhere)
# ----------------------------------------------------------------------
def _parse_url_query_string(url):
    """
    Parse a URL query string into a dictionary of lists.
    Example:  https://example.com?cursor=abc&page=2
    → {'cursor': ['abc'], 'page': ['2']}
    """
    # Implementation omitted – provided by the original module
    return {}

def _validate_page_string(query_string):
    """
    Convert a query string into a Python dict.
    """
    # Implementation omitted – provided by the original module
    pass

def _validate_page(page):
    """
    Validate that a page object contains required keys.
    Raises ValueError on missing or malformed data.
    """
    # Implementation omitted – provided by the original module
    pass

# ----------------------------------------------------------------------
# Core functions
# ----------------------------------------------------------------------
def fetch_pages(url, initial_headers=None):
    """
    Fetch all pages starting from `url` using pagination via a `next_cursor`
    query parameter. Returns a list of page dicts.
    """
    if not initial_headers:
        initial_headers = {}

    headers = {**initial_headers, 'User-Agent': 'Mozilla/5.0'}
    next_cursor = None
    pages = []

    while True:
        # ------------------------------------------------------------------
        # 1️⃣ Fetch the current page (either from URL or from cursor param)
        # ------------------------------------------------------------------
        if next_cursor is not None:
            page = fetch_http_page(url, next_cursor, headers=headers)
        else:
            page = requests.get(url, headers=headers)

        # ------------------------------------------------------------------
        # 2️⃣ Validate the fetched page
        # ------------------------------------------------------------------
        if not isinstance(page, dict):
            raise ValueError("page must be a dictionary")
        _validate_page_string(page)
        pages.append(page)

        # ------------------------------------------------------------------
        # 3️⃣ Extract pagination info for the next request
        # ------------------------------------------------------------------
        next_cursor = page.get('next_cursor')
        if next_cursor is None:
            break

    return pages


def fetch_http_page(url, next_cursor, initial_headers=None):
    """
    Perform a GET request to `url`. If `next_cursor` is provided, append it
    as a URL‑encoded query parameter. When the cursor already exists in the
    URL, replace (rather than append) the existing value to keep the parsed
    query string unchanged.
    """
    headers = {**initial_headers or {}, 'User-Agent': 'Mozilla/5.0'}

    if not next_cursor:
        return requests.get(url, headers=headers)

    # Parse any existing query parameters from the URL
    params = _parse_url_query_string(url)
    if 'cursor' in params:
        # Replace the existing cursor value with the new one
        del params['cursor']
    # Encode the (new) cursor value and add it back to the parameters dict
    params['cursor'] = urllib.parse.urlencode({'cursor': next_cursor})
    return requests.get(url, headers=headers, **params)


def _commit():
    """
    Commit the current SQLite transaction.
    Returns True on success; raises an exception otherwise.
    """
    with connection.cursor() as cur:
        try:
            return True
        except sqlite3.IntegrityError:
            cur.execute('ROLLBACK')
            raise


def sync_pages(url, initial_headers=None):
    """
    Wrapper that fetches all pages from `url` and stores them in a SQLite DB.
    Returns the number of pages retrieved.
    """
    if not initial_headers:
        initial_headers = {}

    # ------------------------------------------------------------------
    # 1️⃣ Initialise connection & cursor
    # ------------------------------------------------------------------
    conn = create_engine('sqlite:///data.db')
    with conn.begin() as cur:          # `conn.begin()` is equivalent to `autocommit`
        for page in fetch_pages(url, initial_headers):
            # --------------------------------------------------------------
            # 2️⃣ Insert / update the record table
            # --------------------------------------------------------------
            name = page.get('name')
            value = page.get('value')
            if not name or not value:
                raise ValueError("record entry must contain 'name' and 'value'")
            cur.execute(
                'INSERT OR REPLACE INTO records (name, value) VALUES (?, ?)',
                (name, value)
            )
        # --------------------------------------------------------------
        # 3️⃣ Commit the transaction after all pages are stored
        # --------------------------------------------------------------
        return _commit()


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def main(args):
    """
    Entry point for command‑line execution.
    Returns exit code (0 = success, non‑zero = failure).
    """
    try:
        app.main()
        return 0
    except Exception as e:
        # Log the error (in real life you would use a logger)
        print(f"Sync failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
