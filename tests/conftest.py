"""Pytest configuration ensuring repository root, engine, tools, and legacy tools are on sys.path."""
import sys
import os
import subprocess

# Ensure UTF-8 I/O across tests
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

# On Windows, default subprocess text decoding to utf-8 with replacement to prevent charmap crashes
if os.name == "nt":
    _orig_popen_init = subprocess.Popen.__init__

    def _patched_popen_init(self, *args, **kwargs):
        if (kwargs.get("text") or kwargs.get("universal_newlines")) and kwargs.get("encoding") is None:
            kwargs["encoding"] = "utf-8"
            kwargs.setdefault("errors", "replace")
        return _orig_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _patched_popen_init

# Set before test module imports so dotenv cannot refill a live account key.
os.environ["XAI_API_KEY"] = ""
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _path in [
    _ROOT,
    _ROOT / "engine",
    _ROOT / "tools",
    _ROOT / "archive" / "legacy_tools",
]:
    _p_str = str(_path)
    if _path.is_dir() and _p_str not in sys.path:
        sys.path.insert(0, _p_str)


import ipaddress
import socket
import urllib.request
from urllib.parse import urlsplit
import pytest


def _is_loopback(host):
    if host in ("localhost", "localhost.localdomain"):
        return True
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def offline_test_network(monkeypatch):
    """Unit tests may use local fixtures; external providers must be mocked."""
    monkeypatch.setenv("XAI_API_KEY", "")
    original_urlopen = urllib.request.urlopen
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded_urlopen(url, *args, **kwargs):
        address = url.full_url if isinstance(url, urllib.request.Request) else str(url)
        parsed = urlsplit(address)
        if parsed.scheme in ("http", "https") and not _is_loopback(parsed.hostname):
            raise RuntimeError("External network disabled in tests; mock the provider transport")
        return original_urlopen(url, *args, **kwargs)

    def guarded_connect(sock, address):
        if isinstance(address, tuple) and not _is_loopback(address[0]):
            raise RuntimeError("External network disabled in tests; mock the provider transport")
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        if isinstance(address, tuple) and not _is_loopback(address[0]):
            raise RuntimeError("External network disabled in tests; mock the provider transport")
        return original_connect_ex(sock, address)

    monkeypatch.setattr(urllib.request, "urlopen", guarded_urlopen)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
