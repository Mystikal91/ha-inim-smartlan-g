/*
 * Dashboard strategy for the INIM SmartLAN/G integration.
 *
 * Builds a ready-to-use dashboard from the entities the integration created, so nothing
 * is tied to one panel: partitions, zones, outputs, ... are discovered from the entity registry.
 * Pick "INIM SmartLAN" in Settings -> Dashboards -> Add dashboard, or use in raw config:
 *
 *   strategy:
 *     type: custom:inim-smartlan
 */

const DOMAIN = "inim_smartlan";
const STRATEGY = "inim-smartlan";
const DOCS = "https://github.com/Mystikal91/ha-inim-smartlan-g/blob/main/docs/dashboard.md";

const TEXTS = {
  en: {
    title: "INIM",
    control: "Control",
    status: "Status",
    partitions: "Partitions",
    scenario: "Scenario",
    outputs: "Outputs and actions",
    zones: "Zones",
    faults: "Faults",
    sensors: "Diagnostics",
    timers: "Timers",
    exclusion: "Zone exclusion",
    empty:
      "No INIM SmartLAN entities found. Add the integration first (Settings -> Devices & services).",
  },
  it: {
    title: "INIM",
    control: "Controllo",
    status: "Stato",
    partitions: "Partizioni",
    scenario: "Scenario",
    outputs: "Uscite e azioni",
    zones: "Zone",
    faults: "Guasti",
    sensors: "Diagnostica",
    timers: "Timer",
    exclusion: "Esclusione zone",
    empty:
      "Nessuna entità INIM SmartLAN trovata. Aggiungi prima l'integrazione (Impostazioni -> Dispositivi e servizi).",
  },
};

function texts(hass) {
  const lang = String((hass && hass.language) || "en").toLowerCase();
  return lang.startsWith("it") ? TEXTS.it : TEXTS.en;
}

function friendlyName(hass, entityId) {
  const state = hass.states && hass.states[entityId];
  return (state && state.attributes && state.attributes.friendly_name) || entityId;
}

/** Entities of this integration grouped by role, using only registry data. */
function collect(hass) {
  const groups = {
    alarm: [],
    scenario: [],
    buttons: [],
    outputs: [],
    exclusion: [],
    zones: [],
    faults: [],
    timers: [],
    sensors: [],
  };
  const entries = Object.values(hass.entities || {}).filter(
    (e) => e && e.platform === DOMAIN && !e.hidden,
  );
  for (const entry of entries) {
    const id = entry.entity_id;
    const domain = id.split(".")[0];
    if (domain === "alarm_control_panel") groups.alarm.push(id);
    else if (domain === "select") groups.scenario.push(id);
    else if (domain === "button") groups.buttons.push(id);
    else if (domain === "switch") {
      (entry.entity_category === "config" ? groups.exclusion : groups.outputs).push(id);
    } else if (domain === "binary_sensor") {
      if (entry.translation_key) groups.faults.push(id);
      else if (entry.entity_category === "diagnostic") groups.timers.push(id);
      else groups.zones.push(id);
    } else if (domain === "sensor") groups.sensors.push(id);
  }
  for (const key of Object.keys(groups)) {
    groups[key].sort((a, b) =>
      friendlyName(hass, a).localeCompare(friendlyName(hass, b), hass.language || "en"),
    );
  }
  return groups;
}

function entitiesCard(title, ids) {
  return { type: "entities", title, entities: ids.map((entity) => ({ entity })) };
}

function buildControlView(t, g) {
  const cards = [];
  if (g.alarm.length) {
    cards.push({
      type: "grid",
      columns: 2,
      square: false,
      cards: g.alarm.map((entity) => ({
        type: "tile",
        entity,
        features: [
          {
            type: "alarm-modes",
            modes: ["armed_home", "armed_away", "armed_night", "disarmed"],
          },
        ],
      })),
    });
  }
  if (g.scenario.length) {
    cards.push({
      type: "grid",
      columns: 1,
      square: false,
      cards: g.scenario.map((entity) => ({
        type: "tile",
        entity,
        features: [{ type: "select-options" }],
      })),
    });
  }
  const actions = [...g.outputs, ...g.buttons];
  if (actions.length) cards.push(entitiesCard(t.outputs, actions));
  if (g.zones.length) cards.push(entitiesCard(t.zones, g.zones));
  return { title: t.control, path: "control", icon: "mdi:shield-home", cards };
}

function buildStatusView(t, g) {
  const cards = [];
  if (g.faults.length) cards.push(entitiesCard(t.faults, g.faults));
  if (g.sensors.length) cards.push(entitiesCard(t.sensors, g.sensors));
  if (g.timers.length) cards.push(entitiesCard(t.timers, g.timers));
  if (g.exclusion.length) cards.push(entitiesCard(t.exclusion, g.exclusion));
  return { title: t.status, path: "status", icon: "mdi:heart-pulse", cards };
}

class InimSmartlanDashboardStrategy extends HTMLElement {
  static async generate(config, hass) {
    const t = texts(hass);
    const groups = collect(hass);
    const total = Object.values(groups).reduce((n, list) => n + list.length, 0);
    const title = (config && config.title) || t.title;
    if (!total) {
      return {
        title,
        views: [{ title, path: "empty", cards: [{ type: "markdown", content: t.empty }] }],
      };
    }
    const views = [buildControlView(t, groups)];
    const status = buildStatusView(t, groups);
    if (status.cards.length) views.push(status);
    return { title, views };
  }
}

if (typeof customElements !== "undefined" && !customElements.get(`ll-strategy-dashboard-${STRATEGY}`)) {
  customElements.define(`ll-strategy-dashboard-${STRATEGY}`, InimSmartlanDashboardStrategy);
}

if (typeof window !== "undefined") {
  window.customStrategies = window.customStrategies || [];
  if (!window.customStrategies.some((s) => s.type === STRATEGY)) {
    window.customStrategies.push({
      type: STRATEGY,
      strategyType: "dashboard",
      name: "INIM SmartLAN",
      description: "Partitions, scenario, zones, outputs and diagnostics of your INIM panel.",
      documentationURL: DOCS,
    });
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { InimSmartlanDashboardStrategy, collect };
}
