"""Two prospects never share a demo slug across the site and the receptionist; one prospect's site and receptionist
may."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from devleadhunter_receptionist.services.assistant_service import ai_assistant_service
from models.demo_site import DemoSite
from services.demo_site_service import demo_site_service


def _site(db: Session, *, slug: str, prospect_id: int | None) -> DemoSite:
    site = DemoSite(
        user_id=7,
        prospect_id=prospect_id,
        slug=slug,
        business_name="Garage Martin",
        status="active",
        expires_at=datetime.now(UTC) + timedelta(days=21),
    )
    db.add(site)
    db.commit()
    return site


def test_a_receptionist_shares_its_own_prospects_site_slug_never_another_prospects(db: Session) -> None:
    _site(db, slug="garage-martin", prospect_id=1)

    own = ai_assistant_service.create(
        db, user_id=7, business_name="Garage Martin", prospect_id=1, country="FR", use_brand_color=False
    )
    another = ai_assistant_service.create(
        db, user_id=7, business_name="Garage Martin", prospect_id=2, country="FR", use_brand_color=False
    )

    assert own.slug == "garage-martin"
    assert another.slug == "garage-martin-2"


def test_a_site_never_takes_another_prospects_receptionist_slug(db: Session) -> None:
    ai_assistant_service.create(
        db, user_id=7, business_name="Toitures Morel", prospect_id=1, country="FR", use_brand_color=False
    )

    assert demo_site_service.unique_slug(db, "Toitures Morel", 1) == "toitures-morel"
    assert demo_site_service.unique_slug(db, "Toitures Morel", 2) == "toitures-morel-2"
