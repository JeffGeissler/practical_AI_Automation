"""Browser protections for a loopback app: Host and Origin checks, session cookie and CSRF token.

Binding to 127.0.0.1 does not stop a page in another tab (or a DNS-rebinding site) from
sending requests, so every request needs a known Host and every change needs a same-origin
source plus a CSRF token tied to the session.
"""
import hashlib
import hmac
import re
import secrets
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import cookie_parser
from starlette.responses import PlainTextResponse

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
COOKIE = "pa_session"
SESSION_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")
SECURITY_HEADERS = {
    "content-security-policy": "default-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "same-origin",
    "cache-control": "no-store",
}


class LocalGuard:
    def __init__(self, app, port: int):
        self.app = app
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.origins = {f"http://{host}" for host in self.hosts}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        if headers.get("host") not in self.hosts:
            return await PlainTextResponse("Unknown host", 400)(scope, receive, send)
        if scope["method"] not in SAFE_METHODS and not self._same_origin(headers):
            return await PlainTextResponse("Cross-site request refused", 403)(scope, receive, send)
        session = cookie_parser(headers.get("cookie", "")).get(COOKIE, "")
        new_session = None
        if not SESSION_PATTERN.fullmatch(session):
            session = new_session = secrets.token_urlsafe(32)
        scope.setdefault("state", {})["session"] = session

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    response_headers.setdefault(name, value)
                if new_session:
                    response_headers.append(
                        "set-cookie", f"{COOKIE}={new_session}; HttpOnly; SameSite=Strict; Path=/")
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _same_origin(self, headers: Headers) -> bool:
        if headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
            return False
        source = headers.get("origin") or headers.get("referer")
        if source is None:
            return True  # non-browser clients; the CSRF token still applies
        parts = urlsplit(source)
        return f"{parts.scheme}://{parts.netloc}" in self.origins


def csrf_token(request: Request) -> str:
    return hmac.new(request.app.state.secret, request.state.session.encode(), hashlib.sha256).hexdigest()


async def require_csrf(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    token = request.headers.get("x-csrf-token")
    if token is None and request.headers.get("content-type", "").startswith(
            ("application/x-www-form-urlencoded", "multipart/form-data")):
        token = (await request.form()).get("csrf_token")
    if not isinstance(token, str) or not hmac.compare_digest(token, csrf_token(request)):
        raise HTTPException(403, "Missing or invalid CSRF token; reload the page and try again")
