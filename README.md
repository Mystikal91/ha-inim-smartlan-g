# INIM SmartLAN/G for Home Assistant (unofficial)

Local-polling custom integration for INIM alarm panels with a **SmartLAN/G** board,
built on the board's own web interface (no official API exists).

> **Status: early alpha (0.1.0).** Developed and used on a SmartLiving 515 with a SmartLAN/G board. The API
> client is tested against a mock panel; the Home Assistant layer has no automated tests yet and several
> write features (outputs, zone exclusion, alarm memory reset, arming checks) are not verified on a real panel.
> Not affiliated with INIM Electronics. It needs a **SmartLAN/G** board (the web interface); the SmartLAN/SI has
> no web server and is not supported.

## Entities
* **Partitions** -> `alarm_control_panel` (away / home=stay / night=instant / disarm). A partition with an
  unreset alarm memory shows `triggered` while armed.
* **Arming scenarios** -> one `select`.
* **Arming checks** -> arming a partition or scenario is refused with the list of zones that are not ready (same check as the panel web UI).
* **Alarm memory reset** -> one `button` per partition (same as the Reset action of the panel web UI).
* **Zone exclusion** -> one `switch` per zone (config category, disabled by default). On = excluded.
* **Zones** -> `binary_sensor` (on = status 2) with raw status attributes.
* **Faults** -> aggregated "Panel fault" + one diagnostic sensor per fault bit.
* **Outputs** ("commands") -> `switch` (plain on/off outputs only).
* **Timers** -> read-only diagnostic `binary_sensor` (disabled by default); **Last event** sensor from the panel log.
* **System voltage**, **GSM/Nexus** diagnostics (only if a Nexus is present).

Everything is discovered from the panel, nothing is hardcoded to a specific setup.

## Notifications
In the integration options you can enable a notification when the scenario changes and/or when an
output becomes active (e.g. the siren), and choose where it is sent (a Home Assistant notification or
any `notify.*` service, such as your phone). Events `inim_smartlan_scenario_changed` and
`inim_smartlan_output_active` are always fired for use in automations.

## Dashboard
A ready-made dashboard: *Settings -> Dashboards -> Add dashboard -> INIM SmartLAN* (restart Home Assistant
first). Also ready-to-paste cards and automation examples: [docs/dashboard.md](docs/dashboard.md).

## Install
HACS -> Custom repositories -> add `https://github.com/Mystikal91/ha-inim-smartlan-g` (type *Integration*), install, restart, then
*Settings -> Devices & services -> Add integration -> INIM SmartLAN*.
Needs Home Assistant 2025.3+.

**Use a user code, not the installer code.** With the installer code the panel returns an empty
list of outputs, so no output switches are created. Log in with the same user code you would use
on the keypad or in the official app.

## Security notes
* The panel speaks **plain HTTP** and the login token appears to be **static**. Keep the panel on a trusted
  LAN/VPN, never exposed to the internet.
* Home Assistant stores username, password and code in its config entry.
* The panel is slow and fragile: requests are serialised. In the options you can set three polling intervals:
  partitions/scenario/outputs (10 s), zones (10 s) and faults/GSM/timers/last event (60 s).

## Reporting problems
Use *Download diagnostics* on the integration: credentials, host, token and every name set on the panel
(zones, partitions, users, places) are redacted.

## Help us: send a probe
Some features (outputs, zones above 31, timers, event log) need more real-world data.
Run `python tools/probe.py --host ... --user ...` (read-only, token not saved), review the JSON and attach it to an issue.

## Not done yet
Full event log (only the last event is exposed).
Protocol notes: [docs/protocol.md](docs/protocol.md).

## Development
See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) and [docs/ROADMAP.md](docs/ROADMAP.md).