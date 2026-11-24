"""Secure portfolio gateway handoff for WebQA.

The one-time code is removed from the browser URL before exchange. The
resulting short-lived bearer is held only in Streamlit server-side state.
No provider key is accepted or persisted by this application.
"""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from typing import Any

PROJECT = "webqa-intelligence"
TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 64 * 1024
CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


class GatewayHandoffError(RuntimeError):
    """Safe-to-display portfolio session exchange error."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _exchange_endpoint(base_url: str) -> str:
    try:
        parsed = urlsplit((base_url or "").strip())
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise GatewayHandoffError("The portfolio gateway URL is invalid.") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise GatewayHandoffError("The portfolio gateway URL is invalid.")
    if os.getenv("NODE_ENV", "").lower() == "production" and parsed.scheme != "https":
        raise GatewayHandoffError("The portfolio gateway must use HTTPS in production.")
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3].rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, f"{path}/v1/demo/session/exchange", "", ""))


def exchange_handoff_code(code: str, *, gateway_url: str | None = None) -> dict[str, Any]:
    code = str(code or "").strip()
    if not CODE_PATTERN.fullmatch(code):
        raise GatewayHandoffError("The WebQA launch code is invalid or incomplete. Launch again from the website.")
    base_url = (gateway_url or os.getenv("PORTFOLIO_SESSION_GATEWAY_URL", "")).strip()
    if not base_url:
        raise GatewayHandoffError("Portfolio session exchange is not configured on WebQA.")
    endpoint = _exchange_endpoint(base_url)
    request = Request(
        endpoint,
        data=json.dumps({"code": code, "project": PROJECT}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json", "Cache-Control": "no-store", "Pragma": "no-cache"},
        method="POST",
    )
    try:
        with build_opener(_NoRedirectHandler()).open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        if exc.code == 401:
            raise GatewayHandoffError("The WebQA launch code expired, was used, or is invalid. Launch again from the website.") from None
        raise GatewayHandoffError("The portfolio gateway could not complete the WebQA session exchange.") from None
    except (URLError, TimeoutError, OSError):
        raise GatewayHandoffError("The AI gateway could not be reached. Retry the launch from the website.") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise GatewayHandoffError("The gateway returned an invalid WebQA session response.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GatewayHandoffError("The gateway returned an invalid WebQA session response.") from None
    if not isinstance(payload, dict):
        raise GatewayHandoffError("The gateway returned an invalid WebQA session response.")
    token = payload.get("access_token")
    target = payload.get("target_project")
    expires = payload.get("expires_in")
    if not isinstance(token, str) or not token.strip() or len(token) > 8192 or any(c.isspace() for c in token):
        raise GatewayHandoffError("The gateway did not return a valid WebQA session.")
    if target != PROJECT:
        raise GatewayHandoffError("The gateway returned a session for an unexpected project.")
    if isinstance(expires, bool) or not isinstance(expires, int) or not 1 <= expires <= 3600:
        raise GatewayHandoffError("The gateway returned an invalid WebQA session expiry.")
    return {"access_token": token, "expires_in": expires, "target_project": target}
