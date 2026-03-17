"""Unit tests for MockPOIProvider — verifies accommodation filtering."""

import pytest

from app.integrations.poi.mock_provider import MockPOIProvider


@pytest.fixture
def provider() -> MockPOIProvider:
    return MockPOIProvider()


@pytest.mark.asyncio
async def test_accommodation_pois_are_excluded(provider):
    """POIs with is_accommodation=True must not appear in search results."""
    pois = await provider.search_pois("beijing")
    accommodation_ids = [p.id for p in pois if p.is_accommodation]
    assert accommodation_ids == [], (
        f"Accommodation POIs leaked into results: {accommodation_ids}"
    )


@pytest.mark.asyncio
async def test_all_cities_exclude_accommodations(provider):
    """Every POI returned for any city must have is_accommodation=False."""
    for city in ("beijing", "shanghai", "chengdu"):
        pois = await provider.search_pois(city)
        bad = [p.id for p in pois if p.is_accommodation]
        assert bad == [], f"Accommodation POIs found in {city}: {bad}"


@pytest.mark.asyncio
async def test_demo_hotel_not_in_results(provider):
    """The demo hotel entry (bj_hotel_001) must be filtered out."""
    pois = await provider.search_pois("beijing")
    ids = [p.id for p in pois]
    assert "bj_hotel_001" not in ids
