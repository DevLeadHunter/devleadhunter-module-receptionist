"""The trades the receptionist module tells apart, read from a business's Google Maps category."""

from enum import Enum


class AiAssistantTrade(str, Enum):
    """A business's trade as the receptionist module groups them; ``OTHER`` when its category names none of them."""

    FOOD_TRUCK = "food_truck"
    CATERER = "caterer"
    EVENT_VENUE = "event_venue"
    EVENT_SERVICE = "event_service"
    PLUMBER = "plumber"
    LOCKSMITH = "locksmith"
    ELECTRICIAN = "electrician"
    DOORS_AND_WINDOWS = "doors_and_windows"
    BODYWORK = "bodywork"
    GARAGE = "garage"
    CARPENTER = "carpenter"
    ROOFER = "roofer"
    JOINER = "joiner"
    PAINTER = "painter"
    MASON = "mason"
    LANDSCAPER = "landscaper"
    HAIRDRESSER = "hairdresser"
    BEAUTY = "beauty"
    RESTAURANT = "restaurant"
    REAL_ESTATE = "real_estate"
    HEALTH = "health"
    OTHER = "other"
