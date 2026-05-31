"""Small in-memory HTTP rate limiter for the MVP backend."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from typing import Any, Deque

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    methods: tuple[str, ...]
    path: str
    match: str
    requests: int
    window_seconds: int

    def matches(self, method: str, path: str) -> bool:
        if self.methods and method.upper() not in self.methods:
            return False
        if self.match == "exact":
            return path == self.path
        if self.match == "prefix":
            return path == self.path or path.startswith(f"{self.path.rstrip('/')}/")
        return False


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    rule_name: str
    limit: int
    remaining: int
    retry_after_seconds: int


class InMemoryRateLimiter:
    """Fixed-window-ish limiter using per-client timestamp buckets.

    This is intentionally process-local. It protects the single-worker MVP
    backend. Use proxy/Redis/DB-backed limits when scaling beyond one process.
    """

    def __init__(self, rules: list[RateLimitRule], default_rule: RateLimitRule | None = None) -> None:
        self.rules = rules
        self.default_rule = default_rule
        self._hits: dict[tuple[str, str], Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, *, client_id: str, method: str, path: str) -> RateLimitDecision | None:
        rule = self._match_rule(method, path)
        if rule is None:
            return None

        now = time.monotonic()
        key = (rule.name, client_id)
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - rule.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= rule.requests:
                retry_after = max(1, int(rule.window_seconds - (now - bucket[0])))
                return RateLimitDecision(
                    allowed=False,
                    rule_name=rule.name,
                    limit=rule.requests,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            bucket.append(now)
            return RateLimitDecision(
                allowed=True,
                rule_name=rule.name,
                limit=rule.requests,
                remaining=max(0, rule.requests - len(bucket)),
                retry_after_seconds=0,
            )

    def _match_rule(self, method: str, path: str) -> RateLimitRule | None:
        for rule in self.rules:
            if rule.matches(method, path):
                return rule
        return self.default_rule


class RateLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        rules: list[RateLimitRule],
        default_rule: RateLimitRule | None = None,
        client_ip_header: str = "x-forwarded-for",
        trust_proxy_headers: bool = True,
    ) -> None:
        self.app = app
        self.limiter = InMemoryRateLimiter(rules=rules, default_rule=default_rule)
        self.client_ip_header = client_ip_header.lower()
        self.trust_proxy_headers = trust_proxy_headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", "")).upper()
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))
        client_id = self._client_id(scope)
        decision = self.limiter.check(client_id=client_id, method=method, path=path)
        if decision is None:
            await self.app(scope, receive, send)
            return

        headers = _rate_limit_headers(decision)
        if not decision.allowed:
            response = JSONResponse(
                {
                    "detail": "Rate limit exceeded. Try again later.",
                    "rate_limit": {
                        "bucket": decision.rule_name,
                        "limit": decision.limit,
                        "retry_after_seconds": decision.retry_after_seconds,
                    },
                },
                status_code=429,
                headers=headers,
            )
            await response(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers", []))
                raw_headers.extend((key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in headers.items())
                message["headers"] = raw_headers
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _client_id(self, scope: Scope) -> str:
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        if self.trust_proxy_headers:
            forwarded_for = headers.get(self.client_ip_header, "")
            if forwarded_for:
                return forwarded_for.split(",", 1)[0].strip() or "unknown"

        client = scope.get("client")
        if isinstance(client, tuple) and client:
            return str(client[0])
        return "unknown"


def build_rate_limit_rule(raw_rule: dict[str, Any]) -> RateLimitRule:
    methods = raw_rule.get("methods") or raw_rule.get("method") or []
    if isinstance(methods, str):
        methods = [methods]

    return RateLimitRule(
        name=str(raw_rule.get("name") or raw_rule.get("path") or "unnamed"),
        methods=tuple(str(method).upper() for method in methods),
        path=str(raw_rule.get("path") or "/"),
        match=str(raw_rule.get("match") or "exact").lower(),
        requests=max(1, int(raw_rule.get("requests") or 1)),
        window_seconds=max(1, int(raw_rule.get("window_seconds") or 60)),
    )


def build_default_rate_limit(raw_default: dict[str, Any] | None) -> RateLimitRule | None:
    if not raw_default:
        return None
    return RateLimitRule(
        name="default",
        methods=(),
        path="*",
        match="default",
        requests=max(1, int(raw_default.get("requests") or 120)),
        window_seconds=max(1, int(raw_default.get("window_seconds") or 60)),
    )


def _rate_limit_headers(decision: RateLimitDecision) -> dict[str, str]:
    reset_seconds = decision.retry_after_seconds if not decision.allowed else 0
    headers = {
        "X-RateLimit-Bucket": decision.rule_name,
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
    }
    if reset_seconds:
        headers["Retry-After"] = str(reset_seconds)
        headers["X-RateLimit-Reset"] = str(int(time.time() + reset_seconds))
    return headers
