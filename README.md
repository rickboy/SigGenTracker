# Sigenergy Cloud for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

A Home Assistant custom integration that connects to the **Sigenergy Cloud API** to monitor your solar inverter, battery, and grid data — and control operational modes and smart loads.

## Changelog

- See [CHANGELOG.md](CHANGELOG.md) for release history and recent updates.

## Features

- **Real-time sensors**: PV power, battery SoC/SoH, battery charge/discharge, grid import/export, load consumption, system online status
- **Capacity sensors**: PV capacity and battery capacity from station metadata
- **Operational mode selector**: Switch between Maximum Self-Consumption, Fully Feed-in to Grid, VPP, and Time of Use modes
- **Smart load switches**: Toggle discovered smart loads on/off
- **Multi-region support**: AUS (Australia/New Zealand), APAC, EU, US, CN

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the **three dots** menu (top right) → **Custom repositories**
3. Add this repository URL and select **Integration** as the category
4. Click **Add**, then find **Sigenergy Cloud** in the HACS store and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/sigenergy_cloud` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Sigenergy Cloud**
3. Enter your Sigenergy Cloud credentials:
   - **Username**: Your Sigenergy account email/username
   - **Password**: Your Sigenergy account password
   - **Region**: Select your region (AUS for Australia/New Zealand, APAC for rest of Asia-Pacific, EU, US, or CN)
4. The integration will authenticate, discover your station, and create sensor entities

## Entities Created

| Entity | Type | Description |
|--------|------|-------------|
| PV Power | Sensor (kW) | Current solar/PV generation |
| PV Capacity | Sensor (kW) | Installed PV capacity |
| Battery State of Charge | Sensor (%) | Battery SoC percentage |
| Battery State of Health | Sensor (%) | Battery SoH percentage |
| Battery Power | Sensor (kW) | Battery charge (+) / discharge (-) power |
| Battery Capacity | Sensor (kWh) | Installed battery capacity |
| Grid Power | Sensor (kW) | Grid import/export power (mapped from `buySellPower`) |
| Load Power | Sensor (kW) | Home consumption power |
| System Online | Sensor | Station online status |
| Operational Mode | Select | Current inverter operational mode |
| Smart Load *name* | Switch | Per-load on/off toggle (if applicable) |

Note: The API power values are already returned in kW and are exposed directly without W->kW conversion.

## Live API Debug Harness

For development/debugging, use `test_auth_live.py` from the repository root:

```powershell
e:/Development/SigGenTracker/.venv/Scripts/python.exe test_auth_live.py
```

Optional environment variables:

- `SIGEN_DEBUG=1` - enable verbose client debug logging
- `SIGEN_REGION=aus|apac|eu|us|cn` - override region
- `SIGEN_STATION_SN_CODE=<serial>` - force station serial for weather endpoint
- `SIGEN_STATS_DATE=YYYYMMDD` - date used for daily stats endpoints

The harness calls and prints full payloads for:

- Station details (`device/owner/station/home`)
- Energy flow (`device/sigen/station/energyflow`)
- Current/available modes
- System devices and smart load details
- Current local weather (`device/sigen/device/getCurrentLocalWeather`)
- Custom energy statistics (`data-process/sigen/station/statistics/v1/energy/custom`)
- Tariff SoC day statistics (`data-process/sigen/station/statistics/tariff-soc/day`)

## Requirements

- A Sigenergy inverter/battery system registered at [app-aus.sigencloud.com](https://app-aus.sigencloud.com/) (or your regional equivalent)
- Valid Sigenergy Cloud account credentials
- Home Assistant 2024.1.0 or newer

## Polling Interval

Data is polled every **30 seconds** by default. This is set in the coordinator and can be adjusted by modifying `DEFAULT_SCAN_INTERVAL` in `const.py`.

## Troubleshooting

- **"Invalid username or password"**: Double-check your credentials. Make sure you can log in at your regional sigencloud.com web app.
- **"Unable to connect"**: Check your network and ensure `api-aus.sigencloud.com` (or your region's URL) is reachable.
- **No smart load switches**: Smart loads only appear if your system has controllable loads configured.
- Check Home Assistant logs (**Settings → System → Logs**) for `sigenergy_cloud` entries.

## License

MIT
