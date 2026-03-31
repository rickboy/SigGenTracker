"""Constants for the Sigenergy Cloud integration."""

DOMAIN = "sigenergy_cloud"
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Regional API base URLs
REGION_APAC = "apac"
REGION_AUS = "aus"
REGION_EU = "eu"
REGION_US = "us"
REGION_CN = "cn"

BASE_URLS: dict[str, str] = {
    REGION_APAC: "https://api-apac.sigencloud.com",
    REGION_AUS: "https://api-aus.sigencloud.com",
    REGION_EU: "https://api-eu.sigencloud.com",
    REGION_US: "https://api-us.sigencloud.com",
    REGION_CN: "https://api-cn.sigencloud.com",
}

DEFAULT_REGION = REGION_APAC

REGIONS: list[str] = [REGION_APAC, REGION_AUS, REGION_EU, REGION_US, REGION_CN]

# AES-CBC encryption for password
AES_KEY = b"sigensigensigenp"
AES_IV = b"sigensigensigenp"

# OAuth2
OAUTH_CLIENT_ID = "sigen"
OAUTH_CLIENT_SECRET = "sigen"

# API endpoints
ENDPOINT_AUTH = "auth/oauth/token"
ENDPOINT_STATION_HOME = "device/owner/station/home"
ENDPOINT_ENERGY_FLOW = "device/sigen/station/energyflow"
ENDPOINT_MODES_ALL = "device/energy-profile/mode/all"
ENDPOINT_MODE_CURRENT = "device/energy-profile/mode/current"
ENDPOINT_MODE_SET = "device/energy-profile/mode"
ENDPOINT_SYSTEM_DEVICES = "device/system/device/systemDevice/card"
ENDPOINT_SMART_LOADS = "device/tp-device/smart-loads"
ENDPOINT_SMART_LOAD_TOGGLE = "device/tp-device/smart-loads/control-mode/manual/switch"
ENDPOINT_REALTIME_CONSUMPTION = (
    "data-process/sigen/station/statistics/real-time-consumption"
)

# Operational modes
OPERATIONAL_MODES: dict[int, str] = {
    0: "Maximum Self-Consumption",
    5: "Fully Feed-in to Grid",
    6: "VPP",
    9: "Time of Use",
}

# Config flow keys
CONF_REGION = "region"
CONF_USER_DEVICE_ID = "user_device_id"

# Platforms
PLATFORMS: list[str] = ["sensor", "select", "switch"]
