"""Tests for the trimmed provider rate limiter."""

from src.gramps_mcp.genealogy.rate_limit import _DEFAULT_MAX_WAIT, get_rate_limiter


class TestRateLimit:
    def test_the_four_providers_in_scope_are_known(self):
        limiter = get_rate_limiter()
        for provider in ("Nominatim", "Swisstopo", "GeoApiGouvFr", "Wikidata"):
            limiter.acquire(provider)

    def test_nominatim_keeps_its_odbl_limit(self):
        from src.gramps_mcp.genealogy import rate_limit

        limit = rate_limit.DEFAULT_RATE_LIMITS["Nominatim"]
        assert limit.requests_per_minute == 60
        assert limit.burst == 1


class TestMaxWaitFromEnv:
    """float(os.getenv(...)) used to raise ValueError inside the worker
    thread that calls acquire() (see tools/detection.py's
    asyncio.to_thread(resolve_place, ...)) whenever the environment held a
    non-numeric GRAMPS_MCP_RATE_LIMIT_MAX_WAIT - a container
    misconfiguration would fail every gazetteer call.
    """

    def test_unset_uses_the_default(self, monkeypatch):
        from src.gramps_mcp.genealogy.rate_limit import _max_wait_from_env

        monkeypatch.delenv("GRAMPS_MCP_RATE_LIMIT_MAX_WAIT", raising=False)
        assert _max_wait_from_env() == _DEFAULT_MAX_WAIT

    def test_non_numeric_falls_back_to_the_default_instead_of_raising(
        self, monkeypatch
    ):
        from src.gramps_mcp.genealogy.rate_limit import _max_wait_from_env

        monkeypatch.setenv("GRAMPS_MCP_RATE_LIMIT_MAX_WAIT", "not-a-number")
        assert _max_wait_from_env() == _DEFAULT_MAX_WAIT

    def test_a_valid_value_is_still_honoured(self, monkeypatch):
        from src.gramps_mcp.genealogy.rate_limit import _max_wait_from_env

        monkeypatch.setenv("GRAMPS_MCP_RATE_LIMIT_MAX_WAIT", "42.5")
        assert _max_wait_from_env() == 42.5

    def test_acquire_does_not_raise_on_a_bad_env_value(self, monkeypatch):
        """End-to-end proof at the public seam: a bad env value must not
        surface as a ValueError out of acquire() itself.
        """
        from src.gramps_mcp.genealogy.rate_limit import RateLimit, RateLimiterRegistry

        monkeypatch.setenv("GRAMPS_MCP_RATE_LIMIT_MAX_WAIT", "not-a-number")
        registry = RateLimiterRegistry({"Test": RateLimit(requests_per_minute=6000)})
        registry.acquire("Test")  # must not raise
