import socket
import threading
import time

import httpx
import pytest
import uvicorn

from axiomn.api.main import app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def live_server_url():
    """Runs the real AXIOMN FastAPI app on loopback so the SDK is tested
    the way it's actually used: as an HTTP client against a running server."""
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            httpx.get(f"{url}/health", timeout=0.2)
            break
        except httpx.TransportError:
            time.sleep(0.1)
    else:
        raise RuntimeError("live server did not start in time")

    yield url

    server.should_exit = True
    thread.join(timeout=5)
