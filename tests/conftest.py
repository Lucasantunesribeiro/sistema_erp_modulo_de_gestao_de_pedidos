import pytest


@pytest.fixture(autouse=True)
def _use_db(db):
    """Automatically use the test database for all tests."""
    pass
