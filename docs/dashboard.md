# Dashboard examples

Entities are created from what your panel reports, so their ids depend on the names you gave
to partitions, zones and outputs. None of the examples below hardcodes a name.

> These snippets have **not been tested on a live dashboard yet**. If one does not work with your
> Home Assistant version, open an issue with the error shown by the card editor.

## 1. No configuration: use areas

1. *Settings -> Devices & services -> INIM SmartLAN -> the device* and set an **area** (e.g. "Alarm").
2. If your dashboard is the auto-generated *Overview*, the entities appear by themselves, grouped by
   area. On a hand-edited dashboard add an **Area** card for that area.

Some entities are disabled by default (zone exclusion switches, timers, most fault bits). Enable
the ones you want from the device page.

## 2. Cards that follow your panel (needs `auto-entities` from HACS)

[`auto-entities`](https://github.com/thomasloven/lovelace-auto-entities) builds the card from a filter, so
new zones or outputs show up without editing anything.

Partitions, with arm / disarm buttons:

```yaml
type: custom:auto-entities
card:
  type: grid
  columns: 2
  square: false
card_param: cards
filter:
  include:
    - integration: inim_smartlan
      domain: alarm_control_panel
      options:
        type: tile
        features:
          - type: alarm-modes
            modes: [armed_home, armed_away, armed_night, disarmed]
```

Scenario, alarm memory reset and outputs in one list:

```yaml
type: custom:auto-entities
card:
  type: entities
  title: Panel controls
filter:
  include:
    - integration: inim_smartlan
      domain: select
    - integration: inim_smartlan
      domain: button
    - integration: inim_smartlan
      domain: switch
      entity_category: "!config"   # hides the zone exclusion switches
sort:
  method: name
```

Zones (every zone has a `status_code` attribute, faults and timers do not):

```yaml
type: custom:auto-entities
card:
  type: entities
  title: Zones
filter:
  include:
    - integration: inim_smartlan
      domain: binary_sensor
      attributes:
        status_code: "*"
sort:
  method: name
```

If a filter option is not accepted by your version of `auto-entities`, drop that line and filter
by hand with *exclude* rules.

## 3. Manual cards

Find the ids in *Settings -> Devices & services -> INIM SmartLAN -> entities*, then replace the
placeholders:

```yaml
type: vertical-stack
cards:
  - type: alarm-panel
    entity: alarm_control_panel.YOUR_PARTITION
    states: [arm_home, arm_away, arm_night]
  - type: entities
    entities:
      - select.YOUR_SCENARIO_SELECT
      - switch.YOUR_OUTPUT
      - button.YOUR_RESET_BUTTON
```

## Notifications through automations

Besides the notification options of the integration, two events are always fired and can drive any
automation:

| Event | Data |
|---|---|
| `inim_smartlan_scenario_changed` | `entry_id`, `id`, `name` |
| `inim_smartlan_output_active` | `entry_id`, `id`, `name` |

```yaml
alias: Siren active
triggers:
  - trigger: event
    event_type: inim_smartlan_output_active
actions:
  - action: notify.mobile_app_YOUR_PHONE
    data:
      title: Alarm output active
      message: "{{ trigger.event.data.name }}"
```
