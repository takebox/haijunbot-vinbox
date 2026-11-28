# -*- coding: utf-8 -*-

from typing import Any
from typing import Dict
from typing import Generator
from typing import Optional

import requests


def get_requests_session() -> requests.Session:
    """
    Get a configured requests.Session object

    Returns:
        A requests.Session object
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        }
    )
    return session


# Enhanced version of the HTTP request methods (implemented using requests)
def post(
    url: str,
    data: Optional[Any] = None,
    json: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> requests.Response:
    """
    Send an enhanced POST request that never times out, implemented using requests

    Parameters:
        url: The request URL
        data: (Optional) Request body data (form data or raw data)
        json: (Optional) JSON data; Content-Type will be set automatically
        **kwargs: Other parameters passed to requests.post

    Returns:
        A requests.Response object

    Note:
        This method is implemented using requests. To implement retries, consider using a Session and HTTPAdapter.
        Never-timing-out is set via timeout=None.
    """
    kwargs.setdefault("timeout", None)
    with get_requests_session() as session:
        response = session.post(url=url, data=data, json=json, **kwargs)
        response.raise_for_status()
        return response


def get(url: str, **kwargs: Any) -> requests.Response:
    """
    Send an enhanced GET request that never times out, implemented using requests

    Parameters:
        url: The request URL
        **kwargs: Other parameters passed to requests.get

    Returns:
        A requests.Response object

    Note:
        This method is implemented using requests.
        Never-timing-out is set via timeout=None.
    """
    kwargs.setdefault("timeout", None)
    with get_requests_session() as session:
        response = session.get(url=url, **kwargs)
        response.raise_for_status()
        return response


def put(url: str, data: Optional[Any] = None, **kwargs: Any) -> requests.Response:
    """
    Send an enhanced PUT request that never times out, implemented using requests

    Parameters:
        url: The request URL
        data: (Optional) Request body data (form data or raw data)
        **kwargs: Other parameters passed to requests.put

    Returns:
        A requests.Response object

    Note:
        This method is implemented using requests.
        Never-timing-out is set via timeout=None.
    """
    kwargs.setdefault("timeout", None)
    with get_requests_session() as session:
        response = session.put(url=url, data=data, **kwargs)
        response.raise_for_status()
        return response


def delete(url: str, **kwargs: Any) -> requests.Response:
    """
    Send an enhanced DELETE request that never times out, implemented using requests

    Parameters:
        url: The request URL
        **kwargs: Other parameters passed to requests.delete

    Returns:
        A requests.Response object

    Note:
        This method is implemented using requests.
        Never-timing-out is set via timeout=None.
    """
    kwargs.setdefault("timeout", None)
    with get_requests_session() as session:
        response = session.delete(url=url, **kwargs)
        response.raise_for_status()
        return response


# Synchronous streaming POST request method
def stream_post(
    url: str,
    data: Optional[Any] = None,
    json: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Generator[str, None, None]:
    """
    Send a streaming POST request, implemented using requests, returning a generator of decoded string lines

    Parameters:
        url: The request URL
        data: (Optional) Request body data (form data or raw data)
        json: (Optional) JSON data; Content-Type will be set automatically
        **kwargs: Other parameters passed to requests.post

    Returns:
        Generator[str, None, None]: A generator of string lines

    Note:
        This method uses requests to implement a streaming request, suitable for handling large file downloads or streaming responses
    """
    kwargs.setdefault("timeout", None)
    with get_requests_session() as session:
        with session.post(url, data=data, json=json, stream=True, **kwargs) as response:
            response.raise_for_status()
            for line in response.iter_lines(chunk_size=1):
                if line:
                    yield line.decode("utf-8", errors="ignore")
