from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "warmlink"
MANUFACTURER = "WarmLink"

CONF_DEVICE_CODE = "device_code"
CONF_DEVICE_NAME = "device_name"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30

CLOUD_URL = "https://cloud.linked-go.com:449/crmservice/api"
APP_ID = "16"
LANGUAGE = "en"

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

REQUEST_CODES: tuple[str, ...] = (
    "Power",
    "Mode",
    "ModeState",
    "R01",
    "R02",
    "T01",
    "T02",
    "T03",
    "T04",
    "T05",
    "T08",
    "TimerMuteOnHour",
    "TimerMuteOnMinute",
    "Timer_Mute_Off_En",
    "TimerMuteOffHour",
    "TimerMuteOffMinute",
    "compensate_slope",
    "compensate_offset",
    "InputCurrent1",
    "Zone 2 Water Target",
    "Zone 2 Cure Slope",
    "Zone 2 Curve Offset",
    "Zone 1 Room Temp",
    "Zone 2 Room Temp",
    "Zone 2 Mixing Temp",
    "SG01",
    "SG Status",
    "Fault1",
    "Fault5",
    "Fault6",
    "Timer_Mute_On_En",
    "Manual-mute",
    "MainBoard Version",
    "code_version",
)
