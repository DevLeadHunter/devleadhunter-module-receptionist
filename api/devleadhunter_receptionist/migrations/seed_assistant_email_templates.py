"""Add the « Assistant IA - … » cold-email templates to the admin's library.

The email template seeder is append-only (it skips any template already present by name),
so running it again adds only the new assistant templates and leaves every existing one
untouched. On a fresh database the admin user does not exist yet, so the seeder no-ops and
the initial seed adds them later.

Idempotent: re-running adds nothing once the templates are present.
"""

from __future__ import annotations

from seeders.email_template_seeder import seed_email_templates


def run_migration() -> None:
    """Append the assistant cold-email templates to the admin's library."""
    seed_email_templates()


if __name__ == "__main__":
    run_migration()
