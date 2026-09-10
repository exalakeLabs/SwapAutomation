"""Small, dependency-free client for the Sigma REST API."""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator


class SigmaAPIError(RuntimeError):
    """An HTTP or Sigma API error."""


class SigmaClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30, retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.retries = retries

    @classmethod
    def from_env(cls) -> "SigmaClient":
        base_url = os.getenv("SIGMA_BASE_URL", "https://api.sigmacomputing.com")
        token = os.getenv("SIGMA_ACCESS_TOKEN")
        if not token:
            client_id = os.getenv("SIGMA_CLIENT_ID")
            client_secret = os.getenv("SIGMA_CLIENT_SECRET")
            if not client_id or not client_secret:
                raise ValueError(
                    "Set SIGMA_ACCESS_TOKEN, or both SIGMA_CLIENT_ID and SIGMA_CLIENT_SECRET"
                )
            token = cls._get_access_token(base_url, client_id, client_secret)
        return cls(base_url, token)

    @staticmethod
    def _get_access_token(base_url: str, client_id: str, client_secret: str) -> str:
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/v2/auth/token",
            data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise SigmaAPIError(f"Token request failed ({exc.code}): {detail}") from exc
        if not body.get("access_token"):
            raise SigmaAPIError("Token response did not contain access_token")
        return str(body["access_token"])

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        data = json.dumps(json_body).encode() if json_body is not None else None
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"

        for attempt in range(self.retries + 1):
            try:
                request = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")
                if exc.code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    retry_after = exc.headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                raise SigmaAPIError(f"{method} {path} failed ({exc.code}): {detail}") from exc
            except urllib.error.URLError as exc:
                if attempt < self.retries:
                    time.sleep(2**attempt)
                    continue
                raise SigmaAPIError(f"{method} {path} failed: {exc.reason}") from exc
        raise AssertionError("unreachable")

    def paginate(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        limit: int = 1000,
    ) -> Iterator[dict[str, Any]]:
        query = dict(params or {})
        query["limit"] = limit
        while True:
            body = self.request("GET", path, params=query)
            yield from body.get("entries", [])
            page = body.get("nextPage")
            if not page:
                return
            query["page"] = page

    def paginate_sources(self, path: str) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {"pageSize": 500}
        while True:
            body = self.request("GET", path, params=params)
            yield from body.get("entries", [])
            token = body.get("nextPageToken")
            if not token:
                return
            params["pageToken"] = token
