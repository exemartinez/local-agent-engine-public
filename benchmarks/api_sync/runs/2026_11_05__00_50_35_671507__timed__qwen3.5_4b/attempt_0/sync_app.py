"""Candidate implementation goes here. See spec.md for the public contract."""


class TransientError(Exception):
    pass


def fetch_http_page(url, cursor):
    raise NotImplementedError


def sync(connection, fetch_page, sleep, *, max_attempts=3, base_delay=0.1, logger=None):
    raise NotImplementedError


def main(argv=None):
    raise NotImplementedError
