"""Shared test fixtures for Sigenergy Cloud tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Sample API response payloads
# ---------------------------------------------------------------------------

SAMPLE_AUTH_RESPONSE = {
    "access_token": "test-access-token-12345",
    "refresh_token": "test-refresh-token-67890",
    "token_type": "bearer",
    "expires_in": 7200,
}

SAMPLE_STATION = {
    "stationId": "STATION001",
    "stationName": "My Home",
    "pvCapacity": 10.0,
    "batteryCapacity": 9.6,
    "hasAcCharger": False,
    "hasDcCharger": False,
    "inverterCount": 1,
}

SAMPLE_ENERGY_FLOW = {
    "pvPower": 5230.0,
    "batterySoc": 78.5,
    "batterySoh": 99.1,
    "batteryPower": -1200.0,
    "gridPower": 150.0,
    "loadPower": 4080.0,
    "online": True,
}

SAMPLE_CURRENT_MODE = {
    "currentMode": 0,
    "currentProfileId": None,
}

SAMPLE_ALL_DATA = {
    "energy_flow": SAMPLE_ENERGY_FLOW,
    "current_mode": SAMPLE_CURRENT_MODE,
}

SAMPLE_SYSTEM_DEVICES = [
    {"name": "Pool Pump", "path": "/load/pool_pump"},
    {"name": "EV Charger", "path": "/load/ev_charger"},
    {"name": "No Path Load"},  # missing path — should be skipped
]


# ---------------------------------------------------------------------------
# aiohttp mock helpers
# ---------------------------------------------------------------------------


def make_mock_response(
    status: int = 200,
    json_data: dict[str, Any] | None = None,
    text: str = "",
) -> AsyncMock:
    """Create a mock aiohttp response with context manager support."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.text = AsyncMock(return_value=text)
    # Support `async with session.post(...) as resp:`
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def make_mock_session() -> MagicMock:
    """Create a mock aiohttp.ClientSession."""
    session = MagicMock()
    # .post() and .request() return context managers
    session.post = MagicMock()
    session.request = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Provide a mock aiohttp ClientSession."""
    return make_mock_session()


@pytest.fixture
def api_response_auth():
    """Provide sample auth response data."""
    return SAMPLE_AUTH_RESPONSE.copy()


@pytest.fixture
def api_response_station():
    """Provide sample station data wrapped in API envelope."""
    return {"code": 0, "data": SAMPLE_STATION.copy(), "message": "success"}


@pytest.fixture
def api_response_energy_flow():
    """Provide sample energy flow data wrapped in API envelope."""
    return {"code": 0, "data": SAMPLE_ENERGY_FLOW.copy(), "message": "success"}


@pytest.fixture
def api_response_current_mode():
    """Provide sample current mode data wrapped in API envelope."""
    return {"code": 0, "data": SAMPLE_CURRENT_MODE.copy(), "message": "success"}
