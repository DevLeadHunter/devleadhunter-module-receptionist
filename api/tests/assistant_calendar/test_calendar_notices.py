"""
The messages about a booked appointment: the visitor's confirmation and J-1 reminder, the owner's alert.

Google is a fake client; the email sender, the SMS provider and the activity log are mocked; the database
is an in-memory SQLite. Business time is Paris (UTC+2 in September).
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from enums.ai_assistant_request import AiAssistantRequestType
from models.ai_assistant_appointment import AiAssistantAppointment
from services.ai_assistant.alert_sms import AlertSms
from services.ai_assistant.appointment_notices import ai_assistant_appointment_notices
from services.ai_assistant.appointment_reminder import AppointmentReminderWindow
from services.ai_assistant.appointment_texts import AppointmentTexts, BusinessCard
from services.ai_assistant.calendar_booking import AiAssistantCalendarBooking
from services.ai_assistant.google_calendar_client import CalendarEventState
from services.ai_assistant.request_email import AiAssistantRequestEmail, RequestEmailContent
from services.sms.gsm_segments import segment_count, to_gsm7
from tests.assistant_calendar.calendar_fakes import (
    MONDAY_10H,
    FakeGoogle,
    add_assistant,
    add_calendar,
    add_request,
    paris,
    utc,
)


def test_the_reminder_leaves_the_day_before_within_the_day_or_not_at_all() -> None:
    booked_monday = utc(MONDAY_10H)

    assert AiAssistantCalendarBooking.reminder_due_at(utc(paris(24, 8)), booked_at=booked_monday) == utc(paris(23, 9))
    assert AiAssistantCalendarBooking.reminder_due_at(utc(paris(24, 21)), booked_at=booked_monday) == utc(paris(23, 19))
    assert AiAssistantCalendarBooking.reminder_due_at(utc(paris(22, 11)), booked_at=booked_monday) is None


def test_the_reminder_is_planned_until_19h_and_still_sent_until_20h() -> None:
    evening_appointment = utc(paris(24, 21))

    assert AppointmentReminderWindow.due_at(evening_appointment, booked_at=utc(MONDAY_10H)) == utc(paris(23, 19))
    assert not AppointmentReminderWindow.is_sending_time(paris(23, 8, 59))
    assert AppointmentReminderWindow.is_sending_time(paris(23, 9))
    assert AppointmentReminderWindow.is_sending_time(paris(23, 19, 30))
    assert not AppointmentReminderWindow.is_sending_time(paris(23, 20))


def test_the_confirmation_and_the_reminder_fit_one_sms_in_every_language() -> None:
    card = BusinessCard(
        name="Garage Morel & Fils Carrosserie",
        phone="+33 3 83 12 34 56",
        email=None,
        address="12 rue des Lilas, 54000 Nancy",
    )
    for language in AppointmentTexts.LANGUAGES:
        confirmation = AppointmentTexts.confirmation_sms(
            card=card, start_local=paris(24, 14), type_label="Contrôle technique complet", language=language
        )
        reminder = AppointmentTexts.reminder_sms(card=card, start_local=paris(24, 14), language=language)

        assert segment_count(to_gsm7(confirmation)) == 1
        assert segment_count(to_gsm7(reminder)) == 1
        assert "14:00" in confirmation and "14:00" in reminder

    assert AppointmentTexts.confirmation_sms(
        card=card, start_local=paris(24, 14), type_label="Révision", language="fr"
    ) == (
        "Garage Morel & Fils Carrosserie : votre rendez-vous du jeu. 24/09 à 14:00 (Révision) est confirmé. "
        "Empeché ? Appelez le +33 3 83 12 34 56."
    )
    assert "Ihr Termin am Do. 24.09. um 14:00" in AppointmentTexts.confirmation_sms(
        card=card, start_local=paris(24, 14), type_label=None, language="de"
    )
    assert AppointmentTexts.language("lb") == "fr"


def test_a_business_name_outside_gsm7_never_costs_the_visitor_their_sms() -> None:
    card = BusinessCard(name="Garage Auto Service N°1 🚗", phone="03 83 12 34 56", email=None, address="1 rue Haute")

    confirmation = AppointmentTexts.confirmation_sms(
        card=card, start_local=paris(24, 14), type_label="Révision", language="fr"
    )
    reminder = AppointmentTexts.reminder_sms(card=card, start_local=paris(24, 14), language="fr")

    for text in (confirmation, reminder):
        assert segment_count(text) == 1
        assert "Garage Auto Service N1" in text and "°" not in text and "🚗" not in text
    assert "(Révision)" in confirmation and "03 83 12 34 56" in reminder


def test_the_confirmation_email_never_asks_to_reply_and_carries_the_ics(
    db: Session, google: FakeGoogle, outbox: dict[str, Any]
) -> None:
    assistant = add_assistant(db)
    request = add_request(db, assistant, contact="julie@example.fr", language="en")
    appointment = AiAssistantAppointment(
        user_id=7,
        assistant_id=assistant.id,
        request_id=request.id,
        starts_at=utc(paris(24, 14)),
        ends_at=utc(paris(24, 15)),
        type_label="Révision",
        google_event_id="dlh1abcd",
        visitor_email="julie@example.fr",
        language="en",
    )
    db.add(appointment)
    db.commit()

    assert asyncio.run(ai_assistant_appointment_notices.send_confirmation(db, appointment))
    assert not asyncio.run(ai_assistant_appointment_notices.send_confirmation(db, appointment))

    [sent] = outbox["email"].calls
    assert sent["recipient_email"] == "julie@example.fr"
    assert sent["subject"] == "Your appointment at Garage Morel: Thursday 24 September at 14:00"
    assert "please do not reply" in sent["body_html"]
    assert "03 83 12 34 56" in sent["body_html"]
    [attachment] = sent["attachments"]
    ics = attachment.content.decode()
    assert attachment.content_type == "text/calendar"
    assert "DTSTART:20260924T120000Z" in ics and "DTEND:20260924T130000Z" in ics
    assert "LOCATION:12 rue des Lilas\\, 54000 Nancy" in ics
    assert outbox["sms"].texts == []


def test_the_runner_sends_due_reminders_once_and_skips_late_ones(
    db: Session, google: FakeGoogle, outbox: dict[str, Any]
) -> None:
    assistant = add_assistant(db)
    now = utc(paris(23, 14, 5))

    def appointment(start: datetime, due: datetime, **fields: Any) -> AiAssistantAppointment:
        # One request per appointment: the table allows no second appointment on a request.
        request = add_request(db, assistant, session_id=f"session-{start.day}-{start.hour}")
        row = AiAssistantAppointment(
            user_id=7,
            assistant_id=assistant.id,
            request_id=request.id,
            starts_at=utc(start),
            ends_at=utc(start + timedelta(hours=1)),
            google_event_id=f"dlh{start.day}{start.hour}",
            visitor_phone_e164="+33611223344",
            language="fr",
            confirmation_sent_at=datetime(2026, 9, 21, 8, 0),
            reminder_due_at=utc(due),
            created_at=datetime(2026, 9, 21, 8, 0),
            **fields,
        )
        db.add(row)
        db.commit()
        return row

    due = appointment(paris(24, 14), paris(23, 14))
    appointment(paris(23, 14, 30), paris(22, 14, 30))
    appointment(paris(25, 14), paris(24, 14))

    assert asyncio.run(ai_assistant_appointment_notices.run_pass(db, now=now)) == 1
    assert asyncio.run(ai_assistant_appointment_notices.run_pass(db, now=now)) == 0

    [sms] = outbox["sms"].texts
    assert sms.startswith("Rappel : rendez-vous demain, 14:00, chez Garage Morel.")
    db.refresh(due)
    assert due.reminder_sent_at is not None


def test_a_reminder_follows_what_the_agenda_says_of_the_event(
    db: Session, google: FakeGoogle, outbox: dict[str, Any]
) -> None:
    assistant = add_assistant(db)
    add_calendar(db, assistant)
    now = utc(paris(23, 14, 5))

    def appointment(start: datetime, due: datetime, event_id: str) -> AiAssistantAppointment:
        request = add_request(db, assistant, session_id=f"session-{event_id}")
        row = AiAssistantAppointment(
            user_id=7,
            assistant_id=assistant.id,
            request_id=request.id,
            starts_at=utc(start),
            ends_at=utc(start + timedelta(hours=1)),
            google_event_id=event_id,
            visitor_phone_e164="+33611223344",
            language="fr",
            confirmation_sent_at=datetime(2026, 9, 21, 8, 0),
            reminder_due_at=utc(due),
            created_at=datetime(2026, 9, 21, 8, 0),
        )
        db.add(row)
        db.commit()
        return row

    appointment(paris(24, 14), paris(23, 14), "dlh-cancelled")
    moved = appointment(paris(24, 10), paris(23, 10), "dlh-moved")
    appointment(paris(24, 11), paris(23, 11), "dlh-deleted")
    appointment(paris(24, 12), paris(23, 12), "dlh-postponed")
    google.event_states["dlh-cancelled"] = CalendarEventState(cancelled=True, start=None)
    google.event_states["dlh-moved"] = CalendarEventState(cancelled=False, start=utc(paris(24, 16, 30)))
    google.event_states["dlh-deleted"] = None
    google.event_states["dlh-postponed"] = CalendarEventState(cancelled=False, start=utc(paris(28, 12)))

    # Every reminder is claimed; only the one still tomorrow leaves, at the time the agenda now holds.
    assert asyncio.run(ai_assistant_appointment_notices.run_pass(db, now=now)) == 4
    [sms] = outbox["sms"].texts
    assert sms.startswith("Rappel : rendez-vous demain, 16:30, chez Garage Morel.")
    db.refresh(moved)
    assert (moved.starts_at, moved.ends_at) == (utc(paris(24, 16, 30)), utc(paris(24, 17, 30)))
    assert sorted(google.event_reads) == ["dlh-cancelled", "dlh-deleted", "dlh-moved", "dlh-postponed"]
    assert asyncio.run(ai_assistant_appointment_notices.run_pass(db, now=now)) == 0


def test_a_confirmation_lost_by_a_restart_is_sent_by_the_runner(
    db: Session, google: FakeGoogle, outbox: dict[str, Any]
) -> None:
    assistant = add_assistant(db)
    request = add_request(db, assistant)
    lost = AiAssistantAppointment(
        user_id=7,
        assistant_id=assistant.id,
        request_id=request.id,
        starts_at=utc(paris(24, 14)),
        ends_at=utc(paris(24, 15)),
        google_event_id="dlhlost",
        visitor_phone_e164="+33611223344",
        language="fr",
        created_at=utc(MONDAY_10H),
    )
    db.add(lost)
    db.commit()

    assert asyncio.run(ai_assistant_appointment_notices.run_pass(db, now=utc(MONDAY_10H) + timedelta(minutes=1))) == 0
    assert asyncio.run(ai_assistant_appointment_notices.run_pass(db, now=utc(MONDAY_10H) + timedelta(minutes=5))) == 1

    [sms] = outbox["sms"].texts
    assert "votre rendez-vous du jeu. 24/09 à 14:00 est confirmé" in sms


def test_the_reminder_leaves_only_the_day_before_between_9_and_20(
    db: Session, google: FakeGoogle, outbox: dict[str, Any]
) -> None:
    assistant = add_assistant(db)
    request = add_request(db, assistant)
    appointment = AiAssistantAppointment(
        user_id=7,
        assistant_id=assistant.id,
        request_id=request.id,
        starts_at=utc(paris(24, 10)),
        ends_at=utc(paris(24, 11)),
        google_event_id="dlhlate",
        visitor_email="julie@example.fr",
        language="fr",
        confirmation_sent_at=datetime(2026, 9, 21, 8, 0),
        reminder_due_at=utc(paris(23, 10)),
        created_at=datetime(2026, 9, 21, 8, 0),
    )
    db.add(appointment)
    db.commit()

    night_before = asyncio.run(ai_assistant_appointment_notices.run_pass(db, now=utc(paris(23, 21, 30))))
    same_day = asyncio.run(ai_assistant_appointment_notices.run_pass(db, now=utc(paris(24, 1, 0))))

    assert (night_before, same_day) == (0, 0)
    db.refresh(appointment)
    assert appointment.reminder_due_at is None and appointment.reminder_sent_at is None
    assert outbox["email"].calls == []


def test_the_reminder_email_says_it_is_tomorrow(db: Session, google: FakeGoogle, outbox: dict[str, Any]) -> None:
    assistant = add_assistant(db)
    request = add_request(db, assistant, contact="julie@example.fr")
    appointment = AiAssistantAppointment(
        user_id=7,
        assistant_id=assistant.id,
        request_id=request.id,
        starts_at=utc(paris(24, 10)),
        ends_at=utc(paris(24, 11)),
        google_event_id="dlhmail",
        visitor_email="julie@example.fr",
        language="fr",
        confirmation_sent_at=datetime(2026, 9, 21, 8, 0),
        reminder_due_at=utc(paris(23, 10)),
        created_at=datetime(2026, 9, 21, 8, 0),
    )
    db.add(appointment)
    db.commit()

    assert asyncio.run(ai_assistant_appointment_notices.run_pass(db, now=utc(paris(23, 10, 5)))) == 1

    [sent] = outbox["email"].calls
    assert sent["subject"].startswith("Rappel : Votre rendez-vous chez Garage Morel")
    assert "c'est demain" in sent["body_html"]


def test_the_owner_is_told_the_appointment_is_already_in_the_agenda() -> None:
    sms = AlertSms.new_request(
        request_type=AiAssistantRequestType.APPOINTMENT,
        name="Julie Roux",
        contact="06 11 22 33 44",
        summary="Vidange et plaquettes avant, elle passe avec la voiture de sa fille.",
        has_photos=False,
        link="demo.dibodev.fr/client/1234.tneuo0.K4lzdHZLLanlAxWK",
        booked="jeu. 24/09 à 14:00 (Révision)",
    )
    email = AiAssistantRequestEmail.render(
        RequestEmailContent(
            business_name="Garage Morel",
            assistant_name="Léa",
            request_type=AiAssistantRequestType.APPOINTMENT,
            visitor_name="Julie Roux",
            contact="06 11 22 33 44",
            need=None,
            need_summary="Vidange.",
            received_at=datetime(2026, 9, 21, 10, 0),
            received_outside_hours=False,
            transcript=[],
            handled_url="https://api.example.fr/handled",
            appointment_booked="jeu. 24/09 à 14:00 (Révision)",
        )
    )

    assert sms.startswith("RDV réservé le jeu. 24/09 à 14:00 (Révision) par Julie Roux, 06 11 22 33 44 : Vidange")
    assert segment_count(sms) == 1
    assert email.subject == "Rendez-vous réservé — Julie Roux"
    assert "Dans votre agenda" in email.html
