"""Unit tests never touch the database.

Overrides the autouse `db_setup` fixture from tests/conftest.py (which connects to
MongoDB and rebuilds indexes for every test) with a no-op, so these run in milliseconds.
"""

import pytest


@pytest.fixture(autouse=True)
def db_setup():
    yield
