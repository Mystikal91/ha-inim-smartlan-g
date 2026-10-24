"""Constants for the INIM SmartLAN integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "inim_smartlan"
PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONF_CODE = "code"
CONF_ZONE_INTERVAL = "zone_scan_interval"
CONF_SLOW_INTERVAL = "slow_scan_interval"
CONF_NOTIFY_SCENARIO = "notify_scenario"
CONF_NOTIFY_OUTPUT = "notify_output"
CONF_NOTIFY_TARGET = "notify_target"
NOTIFY_PERSISTENT = "persistent_notification"  # default target
EVENT_SCENARIO_CHANGED = f"{DOMAIN}_scenario_changed"
EVENT_OUTPUT_ACTIVE = f"{DOMAIN}_output_active"
DEFAULT_PORT = 80
# Seconds; the panel is slow, do not go too low.
DEFAULT_SCAN_INTERVAL = 10  # partitions, scenario, outputs
DEFAULT_ZONE_INTERVAL = 10  # zones (the slowest request)
DEFAULT_SLOW_INTERVAL = 60  # faults, GSM, timers, last event

# Partition arming codes used by mod=do_part (act) and returned in "am".
ARM_AWAY = 1
ARM_STAY = 2
ARM_INSTANT = 3
DISARM = 4
RESET = 5

# Bit mask returned by mod=fau (taken from the panel's own web UI).
FAULT_BITS: dict[int, str] = {
    1: "zone_fuse",
    2: "ibus_fuse",
    4: "low_battery",
    8: "mains_failure",
    16: "tel_line_down",
    32: "jamming",
    64: "low_battery_wls",
    128: "wls_zone_loss",
    256: "nexus_fault",
    512: "detector_dusty",
    1024: "zone_faults",
    2048: "sounder_faults",
    4096: "loss_stamp_ongoing",
}
# Fault sensors enabled by default (the others can be enabled by the user).
FAULTS_ENABLED_DEFAULT = {4, 8, 16, 32, 256}
