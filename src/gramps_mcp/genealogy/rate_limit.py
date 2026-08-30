# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2026 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Provider-keyed synchronous rate limiting for API-backed tools.

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/core/rate_limiter.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.

Trimmed to the four gazetteer providers this project calls (Nominatim,
Swisstopo, GeoApiGouvFr, Wikidata). The source module's finance/OSINT
provider table and its premium-tier env-var override mechanism are out of
scope here and were dropped, not ported.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger("gramps_mcp.rate_limiter")

_WARN_WAIT_SECONDS = 5.0
_DEFAULT_MAX_WAIT = 120.0


class RateLimitExceeded(RuntimeError):
    """Raised when acquiring a token would exceed the caller's max_wait budget."""


@dataclass(frozen=True)
class RateLimit:
    """Token-bucket parameters for one provider."""

    requests_per_minute: int
    burst: int = 5


DEFAULT_RATE_LIMITS: dict[str, RateLimit] = {
    # ODbL: max 1 req/s, no burst - a licence obligation, not a courtesy.
    "Nominatim": RateLimit(requests_per_minute=60, burst=1),
    # ~10 req/s, conservative
    "Swisstopo": RateLimit(requests_per_minute=600, burst=10),
    # ~10 req/s, conservative
    "GeoApiGouvFr": RateLimit(requests_per_minute=600, burst=10),
    # Wikidata Query Service : aucune limite publiée, mais l'endpoint public
    # étrangle agressivement — 502 puis 504 observés pendant la conception
    # du référentiel.
    "Wikidata": RateLimit(requests_per_minute=30, burst=5),
}


class _TokenBucket:
    def __init__(self, limit: RateLimit) -> None:
        self._capacity = float(limit.burst)
        self._tokens = float(limit.burst)
        self._refill_per_sec = limit.requests_per_minute / 60.0
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, provider: str, max_wait: float | None = None) -> None:
        deadline = None if max_wait is None else time.monotonic() + max_wait
        waited = 0.0
        warned = False
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self._capacity,
                    self._tokens + (now - self._updated) * self._refill_per_sec,
                )
                self._updated = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._refill_per_sec
            if deadline is not None and time.monotonic() + wait > deadline:
                raise RateLimitExceeded(
                    f"{provider}: rate-limit wait would exceed {max_wait:.1f}s "
                    f"(waited {waited:.1f}s)"
                )
            if not warned and waited + wait > _WARN_WAIT_SECONDS:
                logger.warning(
                    f"{provider}: rate-limited, waiting {wait:.1f}s for a token "
                    f"(total wait so far {waited:.1f}s)"
                )
                warned = True
            time.sleep(wait)
            waited += wait


class RateLimiterRegistry:
    """Per-provider token buckets. Unknown providers pass through unthrottled."""

    def __init__(self, limits: dict[str, RateLimit] | None = None) -> None:
        base = dict(DEFAULT_RATE_LIMITS if limits is None else limits)
        self._limits = base
        self._buckets = {
            provider: _TokenBucket(limit) for provider, limit in base.items()
        }

    def limit_for(self, provider: str) -> RateLimit | None:
        return self._limits.get(provider)

    def acquire(self, provider: str, max_wait: float | None = None) -> None:
        if os.getenv("CREWAI_TOOLS_RATE_LIMIT_DISABLED", "").lower() in ("1", "true"):
            return
        bucket = self._buckets.get(provider)
        if bucket is None:
            return
        if max_wait is None:
            max_wait = float(
                os.getenv("CREWAI_TOOLS_RATE_LIMIT_MAX_WAIT", str(_DEFAULT_MAX_WAIT))
            )
        bucket.acquire(provider, max_wait)


_registry: RateLimiterRegistry | None = None
_registry_lock = threading.Lock()


def get_rate_limiter() -> RateLimiterRegistry:
    """Return the process-wide registry, creating it on first use."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = RateLimiterRegistry()
    return _registry


def reset_rate_limiter() -> None:
    """Discard the singleton (tests only)."""
    global _registry
    _registry = None
