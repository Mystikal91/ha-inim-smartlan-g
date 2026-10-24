// Offline test of the dashboard strategy: node tests/dashboard_strategy.test.js
const assert = require("node:assert/strict");

global.HTMLElement = class {};
const defined = {};
global.customElements = {
  get: (name) => defined[name],
  define: (name, cls) => {
    defined[name] = cls;
  },
};
global.window = {};

const { InimSmartlanDashboardStrategy } = require(
  "../custom_components/inim_smartlan/frontend/inim-smartlan-dashboard.js",
);

assert.ok(defined["ll-strategy-dashboard-inim-smartlan"], "element registered");
assert.equal(window.customStrategies[0].type, "inim-smartlan");
assert.equal(window.customStrategies[0].strategyType, "dashboard");

const reg = (entity_id, extra = {}) => [
  entity_id,
  { entity_id, platform: "inim_smartlan", ...extra },
];
const other = { entity_id: "light.kitchen", platform: "hue" };
const hass = {
  language: "en",
  entities: Object.fromEntries([
    reg("alarm_control_panel.part_b"),
    reg("alarm_control_panel.part_a"),
    reg("select.scenario"),
    reg("button.reset_a"),
    reg("switch.siren"),
    reg("switch.exclude_z1", { entity_category: "config" }),
    reg("binary_sensor.zone_1"),
    reg("binary_sensor.timer_1", { entity_category: "diagnostic" }),
    reg("binary_sensor.panel_fault", { translation_key: "panel_fault" }),
    reg("sensor.voltage"),
    reg("binary_sensor.hidden_zone", { hidden: true }),
    ["light.kitchen", other],
  ]),
  states: {
    "alarm_control_panel.part_a": { attributes: { friendly_name: "A" } },
    "alarm_control_panel.part_b": { attributes: { friendly_name: "B" } },
  },
};

(async () => {
  const cfg = await InimSmartlanDashboardStrategy.generate({}, hass);
  assert.equal(cfg.views.length, 2);
  const [control, status] = cfg.views;
  const grid = control.cards[0];
  assert.deepEqual(grid.cards.map((c) => c.entity), ["alarm_control_panel.part_a", "alarm_control_panel.part_b"]);
  assert.equal(grid.cards[0].features[0].type, "alarm-modes");
  const all = JSON.stringify(cfg);
  assert.ok(!all.includes("light.kitchen"), "foreign entities are ignored");
  assert.ok(!all.includes("hidden_zone"), "hidden entities are ignored");
  const entitiesOf = (view, title) =>
    view.cards.find((c) => c.title === title).entities.map((e) => e.entity);
  assert.deepEqual(entitiesOf(control, "Outputs and actions"), ["switch.siren", "button.reset_a"]);
  assert.deepEqual(entitiesOf(control, "Zones"), ["binary_sensor.zone_1"]);
  assert.deepEqual(entitiesOf(status, "Faults"), ["binary_sensor.panel_fault"]);
  assert.deepEqual(entitiesOf(status, "Timers"), ["binary_sensor.timer_1"]);
  assert.deepEqual(entitiesOf(status, "Zone exclusion"), ["switch.exclude_z1"]);

  const it = await InimSmartlanDashboardStrategy.generate({ title: "Casa" }, { ...hass, language: "it-IT" });
  assert.equal(it.title, "Casa");
  assert.equal(it.views[0].title, "Controllo");

  const empty = await InimSmartlanDashboardStrategy.generate({}, { language: "en", entities: {}, states: {} });
  assert.equal(empty.views.length, 1);
  assert.equal(empty.views[0].cards[0].type, "markdown");
  console.log("DASHBOARD OK");
})();
