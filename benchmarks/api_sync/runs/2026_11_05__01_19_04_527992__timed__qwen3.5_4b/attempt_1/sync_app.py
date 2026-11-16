```python
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


def fetch_http_page(url, cursor):
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
    except HTTP
