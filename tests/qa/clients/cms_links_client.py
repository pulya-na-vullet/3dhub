"""HTTP client for POST /v1/sign/cms-links."""

from __future__ import annotations

from typing import Any

import requests


class CmsLinksClient:
    """Thin wrapper around corp-ncins cms-links endpoint."""

    PATH = "/v1/sign/cms-links"

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str],
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = headers
        self.timeout = timeout
        self.session = session or requests.Session()

    @property
    def url(self) -> str:
        return f"{self.base_url}{self.PATH}"

    def post_cms_links(
        self,
        payload: dict[str, Any],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> requests.Response:
        headers = {**self.headers}
        if extra_headers:
            headers.update(extra_headers)
        return self.session.post(
            self.url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
