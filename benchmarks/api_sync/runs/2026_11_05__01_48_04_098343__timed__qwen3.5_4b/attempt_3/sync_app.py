```python
import argparse
import json
import math
import os
import sqlite3
import sys
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit


class TransientError(Exception):
    """Raised for transient failures that should be retried."""
    pass


def validate_config(max_attempts: int, base_delay: float) -> None:
    """Validate retry configuration parameters."""
    if isinstance(max_attempts, bool):
        raise ValueError("max_attempts must be a positive integer, not a boolean")
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer")

    if isinstance(base_delay, bool):
        raise ValueError("base_delay must be a nonnegative finite number, not a boolean")
    if not isinstance(base_delay, (int, float)):
        raise ValueError("base_delay must be a nonnegative finite number")
    if base_delay < 0:
        raise ValueError("base_delay must be a nonnegative finite number")
    if not math.isfinite(base
