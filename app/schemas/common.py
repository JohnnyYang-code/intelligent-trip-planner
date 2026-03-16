from enum import Enum


class TravelPace(str, Enum):
    relaxed = "relaxed"        # 2–3 POIs per day
    moderate = "moderate"      # 3–4 POIs per day
    intensive = "intensive"    # 5–6 POIs per day


class BudgetLevel(str, Enum):
    budget = "budget"
    mid_range = "mid_range"
    luxury = "luxury"


class POICategory(str, Enum):
    history_culture = "history_culture"
    nature_scenery = "nature_scenery"
    food_dining = "food_dining"
    shopping = "shopping"
    art_museum = "art_museum"
    entertainment = "entertainment"
    local_life = "local_life"
