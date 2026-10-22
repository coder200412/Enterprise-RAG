import pytest


@pytest.fixture
def anyio_backend():
    """Run async API tests on asyncio without requiring the optional Trio package."""
    return "asyncio"
