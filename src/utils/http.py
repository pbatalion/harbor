from __future__ import annotations

import logging
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Shared session for connection pooling
_session: requests.Session | None = None


def get_session() -> requests.Session:
    """Get or create a shared requests session with connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        # Set reasonable defaults
        _session.headers.update({
            "User-Agent": "Harbor/0.1",
        })
    return _session


class TransientHTTPError(Exception):
    """Raised for HTTP errors that should be retried."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


def is_transient_status(status_code: int) -> bool:
    """Check if an HTTP status code indicates a transient/retryable error."""
    return status_code in {408, 409, 425, 429} or 500 <= status_code <= 599


@retry(
    retry=retry_if_exception_type((requests.RequestException, TransientHTTPError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    data: str | bytes | None = None,
    timeout: int = 30,
    raise_for_transient: bool = True,
) -> requests.Response:
    """Make an HTTP request with automatic retry on transient failures.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Optional headers dict
        params: Optional query parameters
        json: Optional JSON body (will be serialized)
        data: Optional raw body data
        timeout: Request timeout in seconds
        raise_for_transient: If True, raise TransientHTTPError for retryable status codes

    Returns:
        Response object

    Raises:
        requests.RequestException: On network errors (after retries exhausted)
        TransientHTTPError: On transient HTTP errors (after retries exhausted)
    """
    session = get_session()
    response = session.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json,
        data=data,
        timeout=timeout,
    )

    if raise_for_transient and is_transient_status(response.status_code):
        raise TransientHTTPError(response.status_code, response.text[:200])

    return response


def get(url: str, **kwargs: Any) -> requests.Response:
    """HTTP GET with retry."""
    return request_with_retry("GET", url, **kwargs)


def post(url: str, **kwargs: Any) -> requests.Response:
    """HTTP POST with retry."""
    return request_with_retry("POST", url, **kwargs)
