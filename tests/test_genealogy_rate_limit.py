"""Tests for the trimmed provider rate limiter."""

from src.gramps_mcp.genealogy.rate_limit import get_rate_limiter


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
