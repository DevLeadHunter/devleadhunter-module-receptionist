"""The receptionist's tests run on the core's fixtures, with the module installed and switched on.

Run them from the core's ``api/`` folder (its packages must be importable by their usual names)::

    python -m pytest ../../devleadhunter-module-receptionist/api/tests
"""

from collections.abc import Iterator

import pytest

from core.product_modules.registry import product_module_registry
from devleadhunter_receptionist.module import ReceptionistModule
from tests.conftest import *  # noqa: F403 — the core's fixtures (database, offline registries, Resend…)

# The module's tables join the metadata before the core's ``engine`` fixture creates them.
ReceptionistModule().load()


@pytest.fixture(autouse=True)
def receptionist_installed(no_product_module_installed: None) -> Iterator[None]:
    """The core sees the receptionist installed (switched on by default: no switch stored in a test database)."""
    product_module_registry.use([ReceptionistModule()])
    yield
