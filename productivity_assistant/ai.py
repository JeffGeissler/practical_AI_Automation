"""AI gateway: the only way the app reaches a model.

Rules enforced here (docs/ARCHITECTURE.md, "AI gateway"): local provider only, an allowlisted
model pinned to its digest, one request at a time, bounded input and output, a timeout, schema
validation by the caller, and an audit row for every call. Prompt and reply text are never logged.
Any failure returns None so the feature falls back to its non-AI version. There is no cloud path.
"""
import ipaddress
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional, Protocol
from urllib.parse import urlsplit

from .tasks import stamp

# Models the app may use, pinned to the digests measured in docs/PRODUCTIVITY_MODEL_EVALUATION.md.
ALLOWED_MODELS = {
    "qwen3:0.6b": "7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435",
    "llama3.2:latest": "a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72",
}
DEFAULT_MODEL = "qwen3:0.6b"
MAX_INPUT_CHARS = 2000  # the capture note itself is limited to 500 characters
BUSY_WAIT_S = 1.0
PAUSE_AFTER_FAILURE_S = 120  # after a timeout or lost connection, skip the model instead of waiting again


class ProviderError(Exception):
    """Raised by providers. outcome is one of the audit outcomes."""

    def __init__(self, outcome: str, message: str = ""):
        super().__init__(message or outcome)
        self.outcome = outcome


@dataclass
class Reply:
    text: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class Provider(Protocol):
    name: str
    model: str
    digest: str

    def complete(self, system: str, user: str, schema: dict, max_output: int) -> Reply: ...


class OllamaProvider:
    """Ollama on this Mac. Never pulls, starts or reconfigures anything."""

    name = "ollama"

    def __init__(self, model: str = DEFAULT_MODEL, host: str = "http://127.0.0.1:11434",
                 timeout: float = 10.0, keep_alive: str = "10m"):
        if model not in ALLOWED_MODELS:
            raise ValueError(f"Model {model} is not on the allowlist")
        address = urlsplit(host).hostname or ""
        try:
            loopback = ipaddress.ip_address(address).is_loopback
        except ValueError:
            loopback = address == "localhost"
        if not loopback:
            raise ValueError("The model host must be on this Mac (127.0.0.1)")
        self.model, self.digest, self.host = model, ALLOWED_MODELS[model], host.rstrip("/")
        self.timeout, self.keep_alive = timeout, keep_alive
        self._verified = False

    def _call(self, path: str, body: Optional[dict] = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.host + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except (TimeoutError, socket.timeout) as error:  # socket.timeout is separate before Python 3.10
            raise ProviderError("timeout") from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise ProviderError("timeout") from error
            raise ProviderError("unavailable", str(error.reason)) from error
        except (OSError, ValueError) as error:
            raise ProviderError("unavailable", str(error)) from error

    def verify(self) -> None:
        """Refuse a model whose installed digest differs from the pinned one."""
        installed = {m.get("name"): m.get("digest") for m in self._call("/api/tags").get("models", [])}
        if self.model not in installed:
            raise ProviderError("unavailable", f"{self.model} is not installed")
        if installed[self.model] != self.digest:
            raise ProviderError("refused", f"{self.model} digest changed; re-run the evaluation before using it")
        self._verified = True

    def complete(self, system: str, user: str, schema: dict, max_output: int) -> Reply:
        if not self._verified:
            self.verify()
        response = self._call("/api/chat", {
            "model": self.model, "stream": False, "think": False, "format": schema, "keep_alive": self.keep_alive,
            "options": {"temperature": 0, "seed": 42, "num_ctx": 2048, "num_predict": max_output},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        if response.get("done_reason") == "length":
            raise ProviderError("invalid", "reply was cut off")
        return Reply(response.get("message", {}).get("content", ""),
                     response.get("prompt_eval_count"), response.get("eval_count"))


class Gateway:
    def __init__(self, provider: Optional[Provider]):
        self.provider = provider
        self._lock = threading.Lock()
        self._paused_until = 0.0

    @property
    def enabled(self) -> bool:
        return self.provider is not None

    def propose(self, connection, now, feature: str, system: str, user: str, schema: dict,
                max_output: int, check) -> tuple:
        """Return (proposal or None, audit id or None). check(dict) -> dict validates meaning."""
        if self.provider is None:
            return None, None
        if len(system) + len(user) > MAX_INPUT_CHARS:
            return None, self._audit(connection, now, feature, "refused", 0)
        if time.monotonic() < self._paused_until:
            return None, self._audit(connection, now, feature, "paused", 0)
        if not self._lock.acquire(timeout=BUSY_WAIT_S):  # one request at a time
            return None, self._audit(connection, now, feature, "busy", 0)
        started, reply, outcome, proposal = time.monotonic(), None, "ok", None
        try:
            reply = self.provider.complete(system, user, schema, max_output)
            proposal = check(json.loads(reply.text))
        except ProviderError as error:
            outcome = error.outcome
            if outcome in ("timeout", "unavailable"):
                self._paused_until = time.monotonic() + PAUSE_AFTER_FAILURE_S
        except (ValueError, TypeError, KeyError, AttributeError):  # malformed JSON or failed checks
            outcome = "invalid"
        finally:
            self._lock.release()
        elapsed = round((time.monotonic() - started) * 1000)
        return proposal, self._audit(connection, now, feature, outcome, elapsed, reply)

    def _audit(self, connection, now, feature, outcome, duration_ms, reply: Optional[Reply] = None) -> int:
        provider = self.provider
        with connection:
            cursor = connection.execute(
                "INSERT INTO ai_calls (at, feature, provider, model, digest, input_tokens, output_tokens, "
                "duration_ms, outcome) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (stamp(now), feature, provider.name, provider.model, provider.digest,
                 reply.input_tokens if reply else None, reply.output_tokens if reply else None, duration_ms, outcome))
        return cursor.lastrowid


def mark_accepted(connection, call_id: Optional[int]) -> bool:
    """Record that the user saved a draft built from this call. Returns True if the call produced it."""
    if call_id is None:
        return False
    with connection:
        cursor = connection.execute(
            "UPDATE ai_calls SET accepted = 1 WHERE id = ? AND outcome = 'ok' AND accepted IS NULL", (call_id,))
    return cursor.rowcount == 1
