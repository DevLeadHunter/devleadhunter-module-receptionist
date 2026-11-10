"""AI assistant lifecycle statuses."""

from enum import Enum


class AiAssistantStatus(str, Enum):
    """Status of a generated AI assistant (mirror of DemoSiteStatus)."""

    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    UNAVAILABLE = "unavailable"
    EXPIRED = "expired"
    DELETED = "deleted"
    FAILED = "failed"
    # Sold: the demo assistant is taken down and the assistant runs in production,
    # embedded on the client's own website. Excluded from TTL cleanup.
    DELIVERED = "delivered"
