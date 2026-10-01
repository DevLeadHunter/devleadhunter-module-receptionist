"""Trades the receptionist module recognizes from a business's Google Maps category."""

from enum import Enum


class AiAssistantTrade(str, Enum):
    """A business's trade, as its Google Maps category tells it; ``OTHER`` when no known trade matches."""

    EVENT_VENUE = "event_venue"
    PLUMBER = "plumber"
    LOCKSMITH = "locksmith"
    ELECTRICIAN = "electrician"
    BUILDING = "building"
    BODY_SHOP = "body_shop"
    GARAGE = "garage"
    CARPENTER = "carpenter"
    ROOFER = "roofer"
    JOINER = "joiner"
    PAINTER = "painter"
    HAIRDRESSER = "hairdresser"
    BEAUTY = "beauty"
    RESTAURANT = "restaurant"
    FOOD_TRUCK = "food_truck"
    REAL_ESTATE = "real_estate"
    HEALTH = "health"
    OTHER = "other"
