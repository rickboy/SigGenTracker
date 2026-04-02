# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

### Added
- Added capacity sensors:
  - PV Capacity (kW)
  - Battery Capacity (kWh)
- Added live API debug harness script: `test_auth_live.py`.
- Added full payload dumps in the harness for:
  - Station details
  - Energy flow
  - Current/available modes
  - System devices and smart load details
  - Current local weather
  - Custom energy statistics
  - Tariff SoC day statistics
- Added API client methods for:
  - Current local weather (`device/sigen/device/getCurrentLocalWeather`)
  - Custom energy statistics (`data-process/sigen/station/statistics/v1/energy/custom`)
  - Tariff SoC day (`data-process/sigen/station/statistics/tariff-soc/day`)

### Changed
- Updated power sensor units from W to kW.
- Aligned power handling with API payloads (values already in kW; no W->kW conversion).
- Updated grid power mapping to prefer `buySellPower` (with fallback to `gridPower`).
- Improved auth/refresh token parsing to handle nested token payloads and fallback JSON parsing.

### Fixed
- Fixed auth token extraction when API returns tokens under `data`.
- Fixed local test harness imports so Home Assistant runtime is not required.
- Updated and expanded test coverage for new API endpoints and sensor behavior.
