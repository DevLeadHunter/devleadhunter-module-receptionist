"""Where a sold assistant's connected agenda stands."""

from enum import Enum


class AiAssistantCalendarStatus(str, Enum):
    """The agenda books appointments (``connected``) or its client must connect it again (``error``)."""

    CONNECTED = "connected"
    ERROR = "error"


class AiAssistantCalendarConnection(str, Enum):
    """The agenda as the client space shows it (``unavailable``: Google is not configured on the server)."""

    UNAVAILABLE = "unavailable"
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"
