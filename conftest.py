"""Root conftest - stub out ``homeassistant`` so tests can import the
custom component without needing a full HA installation.

This file is loaded by pytest *before* any test module is collected, so
the stubs are ready before ``custom_components.sigenergy_cloud`` is imported.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

# ── tiny stub classes that need real behaviour ────────────────────────────

class _ConfigEntry:
    """Minimal ConfigEntry stub."""
    def __init__(self, **kwargs: Any) -> None:
        self.data: dict[str, Any] = kwargs.get("data", {})
        self.entry_id: str = kwargs.get("entry_id", "test-entry-id")
        self.unique_id: str | None = kwargs.get("unique_id")


class _ConfigEntryAuthFailed(Exception):
    """Stub for homeassistant.exceptions.ConfigEntryAuthFailed."""


class _UpdateFailed(Exception):
    """Stub for homeassistant.helpers.update_coordinator.UpdateFailed."""


class _DataUpdateCoordinator:
    """Minimal coordinator stub."""
    def __init__(self, hass: Any, logger: Any, *, name: str, update_interval: Any) -> None:
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data: dict[str, Any] = {}

    async def async_config_entry_first_refresh(self) -> None: ...

    def __class_getitem__(cls, item: Any) -> type:
        return cls


class _CoordinatorEntity:
    """Stub base for CoordinatorEntity."""
    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator

    def __class_getitem__(cls, item: Any) -> type:
        return cls


@dataclass(frozen=True, kw_only=True)
class _SensorEntityDescription:
    """Stub dataclass for SensorEntityDescription."""
    key: str = ""
    translation_key: str | None = None
    native_unit_of_measurement: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    icon: str | None = None
    name: str | None = None
    entity_category: str | None = None
    suggested_display_precision: int | None = None


class _SensorEntity:
    """Stub SensorEntity."""


class _SelectEntity:
    """Stub SelectEntity."""


class _SwitchEntity:
    """Stub SwitchEntity."""


class _ConfigFlow:
    """Stub ConfigFlow."""
    DOMAIN: str = ""
    VERSION: int = 1

    def __init_subclass__(cls, *, domain: str = "", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.DOMAIN = domain

    async def async_set_unique_id(self, uid: str) -> None: ...
    def _abort_if_unique_id_configured(self) -> None: ...
    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "form", **kwargs}
    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "create_entry", **kwargs}
    def async_abort(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "abort", **kwargs}
    def async_show_progress(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "progress", **kwargs}


# ── build stub modules ───────────────────────────────────────────────────

def _make_module(**attrs: Any) -> MagicMock:
    mod = MagicMock()
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


_stubs: dict[str, Any] = {
    # homeassistant (top-level)
    "homeassistant": _make_module(),
    # homeassistant.const
    "homeassistant.const": _make_module(
        CONF_PASSWORD="password",
        CONF_USERNAME="username",
        PERCENTAGE="%",
        UnitOfPower=type("UnitOfPower", (), {"WATT": "W"}),
    ),
    # homeassistant.core
    "homeassistant.core": _make_module(
        HomeAssistant=MagicMock,
    ),
    # homeassistant.config_entries
    "homeassistant.config_entries": _make_module(
        ConfigEntry=_ConfigEntry,
        ConfigFlow=_ConfigFlow,
        ConfigFlowResult=dict,  # type alias → plain dict
    ),
    # homeassistant.exceptions
    "homeassistant.exceptions": _make_module(
        ConfigEntryAuthFailed=_ConfigEntryAuthFailed,
    ),
    # homeassistant.helpers
    "homeassistant.helpers": _make_module(),
    # homeassistant.helpers.aiohttp_client
    "homeassistant.helpers.aiohttp_client": _make_module(
        async_get_clientsession=MagicMock(),
    ),
    # homeassistant.helpers.update_coordinator
    "homeassistant.helpers.update_coordinator": _make_module(
        DataUpdateCoordinator=_DataUpdateCoordinator,
        CoordinatorEntity=_CoordinatorEntity,
        UpdateFailed=_UpdateFailed,
    ),
    # homeassistant.helpers.entity_platform
    "homeassistant.helpers.entity_platform": _make_module(
        AddEntitiesCallback=MagicMock,
    ),
    # homeassistant.helpers.device_registry
    "homeassistant.helpers.device_registry": _make_module(
        DeviceEntryType=MagicMock(),
        DeviceInfo=dict,
    ),
    # homeassistant.components
    "homeassistant.components": _make_module(),
    # homeassistant.components.sensor
    "homeassistant.components.sensor": _make_module(
        SensorDeviceClass=type("SensorDeviceClass", (), {"POWER": "power", "BATTERY": "battery", "ENUM": "enum"}),
        SensorStateClass=type("SensorStateClass", (), {"MEASUREMENT": "measurement"}),
        SensorEntity=_SensorEntity,
        SensorEntityDescription=_SensorEntityDescription,
    ),
    # homeassistant.components.select
    "homeassistant.components.select": _make_module(
        SelectEntity=_SelectEntity,
    ),
    # homeassistant.components.switch
    "homeassistant.components.switch": _make_module(
        SwitchEntity=_SwitchEntity,
    ),
    # homeassistant.data_entry_flow (used by config_flow tests)
    "homeassistant.data_entry_flow": _make_module(
        FlowResult=dict,
    ),
}

# Inject all stubs before any test module can import them
sys.modules.update(_stubs)
