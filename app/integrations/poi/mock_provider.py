import json
import logging
from pathlib import Path

from app.integrations.poi.base import BasePOIProvider
from app.schemas.poi import POI

logger = logging.getLogger(__name__)

# Maps user-supplied destination strings to JSON file stems.
# Keys should be lowercase. Add entries here as new cities are added.
_DESTINATION_ALIASES: dict[str, str] = {
    # English
    "beijing": "beijing",
    "shanghai": "shanghai",
    "chengdu": "chengdu",
    # Chinese
    "北京": "beijing",
    "上海": "shanghai",
    "成都": "chengdu",
}

# Location of the mock data directory, relative to the project root.
_MOCK_DATA_DIR = Path(__file__).resolve().parents[3] / "app" / "data" / "mock"


class MockPOIProvider(BasePOIProvider):
    """
    Reads POI data from local JSON files under app/data/mock/.

    No API key or network access required.
    Used as the default provider and as the fallback when a real provider fails.
    """

    async def search_pois(self, destination: str, limit: int = 60) -> list[POI]:
        file_stem = _DESTINATION_ALIASES.get(destination) or _DESTINATION_ALIASES.get(
            destination.lower()
        )

        if file_stem is None:
            logger.warning(
                "MockPOIProvider: no mock data for destination '%s'. "
                "Returning empty list.",
                destination,
            )
            return []

        json_path = _MOCK_DATA_DIR / f"{file_stem}_pois.json"

        if not json_path.exists():
            logger.error("MockPOIProvider: data file not found: %s", json_path)
            return []

        with json_path.open(encoding="utf-8") as fh:
            raw = json.load(fh)

        pois = [POI(**entry) for entry in raw.get("pois", [])]
        logger.info(
            "MockPOIProvider: loaded %d POIs for '%s'", len(pois[:limit]), destination
        )
        return pois[:limit]

    def is_available(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "mock"
