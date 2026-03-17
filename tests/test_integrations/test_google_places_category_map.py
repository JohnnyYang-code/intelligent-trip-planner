"""
Regression tests for _map_category() in google_places.py.

Verifies that specific venue types win over the generic tourist_attraction
when both appear in a Google Places types list (first-match logic).
"""

import pytest
from app.integrations.poi.google_places import _map_category
from app.schemas.common import POICategory


@pytest.mark.parametrize(
    "place_types, expected",
    [
        # Restaurant alongside tourist_attraction → food_dining wins
        (["restaurant", "tourist_attraction", "point_of_interest", "establishment"],
         POICategory.food_dining),
        # Cafe alongside tourist_attraction → food_dining wins
        (["cafe", "tourist_attraction", "establishment"],
         POICategory.food_dining),
        # Park alongside tourist_attraction → nature_scenery wins
        (["park", "tourist_attraction", "point_of_interest"],
         POICategory.nature_scenery),
        # Museum → art_museum (no tourist_attraction present)
        (["museum", "point_of_interest", "establishment"],
         POICategory.art_museum),
        # tourist_attraction only → history_culture (generic fallback)
        (["tourist_attraction", "point_of_interest", "establishment"],
         POICategory.history_culture),
        # Shopping mall → shopping
        (["shopping_mall", "tourist_attraction", "establishment"],
         POICategory.shopping),
        # Bar → food_dining
        (["bar", "night_club", "establishment"],
         POICategory.food_dining),
        # Unknown types → None
        (["establishment", "point_of_interest"],
         None),
    ],
)
def test_map_category(place_types: list[str], expected):
    assert _map_category(place_types) == expected
