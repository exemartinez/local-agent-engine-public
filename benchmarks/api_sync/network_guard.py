"""Pytest plugin: reject real socket connections during candidate evaluation."""
import socket


def pytest_sessionstart(session):
    def denied(*args, **kwargs):
        raise RuntimeError("Network connections are disabled in benchmark tests")

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied
