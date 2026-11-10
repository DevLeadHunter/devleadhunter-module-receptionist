"""The receptionist's own settings, read from the API's .env next to the core's."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ReceptionistSettings(BaseSettings):
    """The keys only the receptionist reads; the core ignores them (its settings accept unknown keys)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, populate_by_name=True, extra="ignore"
    )

    # Estimated prices, in EUR per million tokens, to log the cost of each assistant model call.
    mistral_eur_per_mtok_in: float = Field(default=0.1, alias="MISTRAL_EUR_PER_MTOK_IN")
    mistral_eur_per_mtok_out: float = Field(default=0.3, alias="MISTRAL_EUR_PER_MTOK_OUT")
    groq_eur_per_mtok_in: float = Field(default=0.15, alias="GROQ_EUR_PER_MTOK_IN")
    groq_eur_per_mtok_out: float = Field(default=0.75, alias="GROQ_EUR_PER_MTOK_OUT")
    assistant_daily_visitor_message_cap: int = Field(
        default=400,
        alias="ASSISTANT_DAILY_VISITOR_MESSAGE_CAP",
        description="Visitor messages an assistant answers with the model per business day, before a fixed reply",
    )

    google_calendar_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/ai-assistants/calendar/google/callback",
        alias="GOOGLE_CALENDAR_REDIRECT_URI",
        description="Google OAuth redirect URI of the assistants' agendas (connected from the client space)",
    )
    # Empty: no receptionist can connect a Gmail mailbox.
    google_mailbox_redirect_uri: str = Field(
        default="",
        alias="GOOGLE_MAILBOX_REDIRECT_URI",
        description="Google OAuth redirect URI of the receptionists' Gmail mailboxes (connected from the client space)",
    )


receptionist_settings = ReceptionistSettings()
