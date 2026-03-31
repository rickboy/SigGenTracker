# Plan: SigenCloud Home Assistant HACS Integration

Build a Home Assistant HACS custom component in Python that authenticates against the SigenCloud API (APAC region), polls for solar/battery/grid/load data via a DataUpdateCoordinator, and exposes it as HA entities (sensors, a mode selector, and smart load switches).

---

## Phase 1 — API Client (standalone, testable)

1. Create `const.py` — regional base URLs (defaulting APAC: `https://api-apac.sigencloud.com/`), OAuth constants, AES key/IV (`sigensigensigenp`), all endpoint paths, and operational mode constants
2. Create `api.py` — async `SigenCloudApiClient` using `aiohttp` (already in HA):
   - `authenticate(username, password)` — AES-CBC-encrypts password, POSTs OAuth2 password grant with BasicAuth `sigen:sigen`
   - `_refresh_token()` — refresh grant using stored refresh_token
   - `_request()` — attaches Bearer header, auto-refreshes on 401
   - `get_station()` — home station info (stationId, capacities)
   - `get_energy_flow(station_id)` — real-time PV, battery, grid, load power
   - `get_smart_loads(station_id)` — discover controllable loads
   - `get_operational_mode / get_available_modes / set_operational_mode` — mode management
   - `toggle_smart_load()` — on/off patch

## Phase 2 — HA Integration Core

3. Create `manifest.json` — domain `sigenergy_cloud`, requirements `[pycryptodome]`, `iot_class: cloud_polling`, `config_flow: true`
4. Create `__init__.py` — `async_setup_entry`, `async_unload_entry`, `SigenEnergyDataUpdateCoordinator` polling `get_energy_flow` + `get_station` at configurable interval (default 30s)
5. Create `config_flow.py` — `async_step_user` with username/password/region fields (APAC default), validates by authenticating + fetching station; `async_step_reauth` for token expiry

## Phase 3 — Entities

6. Create `sensor.py` — `SensorEntityDescription` entries for:
   - PV power (W), Battery SoC (%), Battery SoH (%), Battery charge/discharge power (W), Grid import/export (W), Load consumption (W), Today's energy (kWh), Station online status
7. Create `select.py` — `SigenEnergyModeSelect` entity mapping API mode IDs to readable names (Maximum Self-Consumption, Fully Feed-in, TOU, VPP, etc.)
8. Create `switch.py` — one `SigenSmartLoadSwitch` per discovered smart load

## Phase 4 — HACS Polish

9. Create `translations/en.json` — config flow labels and entity names
10. Create `hacs.json` — HACS metadata (`category: integration`)
11. Create `README.md` — HACS install steps, config, options

---

## Files to Create

All new (workspace is empty):

- `custom_components/sigenergy_cloud/const.py`
- `custom_components/sigenergy_cloud/api.py`
- `custom_components/sigenergy_cloud/__init__.py`
- `custom_components/sigenergy_cloud/manifest.json`
- `custom_components/sigenergy_cloud/config_flow.py`
- `custom_components/sigenergy_cloud/sensor.py`
- `custom_components/sigenergy_cloud/select.py`
- `custom_components/sigenergy_cloud/switch.py`
- `custom_components/sigenergy_cloud/translations/en.json`
- `hacs.json`
- `README.md`

---

## Key Technical Details

- **Auth endpoint**: `POST auth/oauth/token` with OAuth2 password grant, BasicAuth `sigen:sigen`, AES-CBC encrypted password (key+IV = `sigensigensigenp`, Base64 output)
- **API response envelope**: `{"code": 0, "data": {...}, "message": "success"}`
- **Token auto-refresh** on 401 responses
- **`pycryptodome`** as `requirements` entry in `manifest.json` for AES support
- **Regional base URLs**:
  - EU: `https://api-eu.sigencloud.com/`
  - CN: `https://api-cn.sigencloud.com/`
  - APAC: `https://api-apac.sigencloud.com/` (Australia — default)
  - US: `https://api-us.sigencloud.com/`

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `auth/oauth/token` | POST | Get/refresh tokens |
| `device/owner/station/home` | GET | Station info |
| `device/sigen/station/energyflow?id={id}` | GET | Real-time power flow |
| `device/energy-profile/mode/all/{id}` | GET | Available modes |
| `device/energy-profile/mode/current/{id}` | GET | Current mode |
| `device/energy-profile/mode` | PUT | Set mode |
| `device/system/device/systemDevice/card?stationId={id}` | GET | Smart loads list |
| `device/tp-device/smart-loads?stationId={id}&loadPath={path}` | GET | Load details |
| `device/tp-device/smart-loads/control-mode/manual/switch?...` | PATCH | Toggle load |

---

## Verification

1. Run `hacs validate` action against the repo to check structure compliance
2. Manually install in a local HA dev container — add integration via UI, confirm entities appear
3. Cross-check entity values against the app-aus.sigencloud.com web app
4. Test operational mode `select` entity changes reflect in the web app
5. Toggle a smart load `switch` and confirm state in web app

---

## Decisions

- Building a self-contained `api.py` rather than depending on Bankilo/sigen-api (too new/unstable)
- Region defaults to APAC in the config flow (user is on `app-aus.sigencloud.com`)
- Smart load switches and operational mode select included as useful controls
- Modbus explicitly excluded