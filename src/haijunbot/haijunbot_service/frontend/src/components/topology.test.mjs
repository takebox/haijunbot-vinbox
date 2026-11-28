// Unit tests for topology (zero dependencies, using node's built-in test runner).
//
// How to run (from the frontend directory):
//   node --test src/components/topology.test.mjs   # run only this file
//   node --test                                     # auto-discover all *.test.mjs
// Note: do not use `node --test src/` (the directory argument is not supported in this node version).
//
// Note: topology.js is the data model and layout pure functions for the
// topology graph (no Vue / third-party dependencies), so it can be unit tested
// directly without DOM.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  NODE_STATE,
  AGENT_STATE,
  normalizeNodeStatus,
  normalizeAgentStatus,
  buildTopology,
  layoutTopology,
  layoutAgents,
  parseBrowserFromUserAgent,
  formatBrowserLabel,
} from "./topology.js";

// ===== normalizeNodeStatus =====
test("normalizeNodeStatus: online aliases normalize to online", () => {
  for (const v of [
    "online",
    "RUNNING",
    "ready",
    "connected",
    "up",
    " online ",
  ]) {
    assert.equal(normalizeNodeStatus(v), NODE_STATE.ONLINE, `input ${v}`);
  }
});

test("normalizeNodeStatus: offline aliases normalize to offline", () => {
  for (const v of ["offline", "stopped", "down", "disconnected", "DOWN"]) {
    assert.equal(normalizeNodeStatus(v), NODE_STATE.OFFLINE, `input ${v}`);
  }
});

test("normalizeNodeStatus: empty and unknown values normalize to unknown", () => {
  assert.equal(normalizeNodeStatus(""), NODE_STATE.UNKNOWN);
  assert.equal(normalizeNodeStatus(null), NODE_STATE.UNKNOWN);
  assert.equal(normalizeNodeStatus(undefined), NODE_STATE.UNKNOWN);
  assert.equal(normalizeNodeStatus("whatever"), NODE_STATE.UNKNOWN);
});

// ===== normalizeAgentStatus =====
test("normalizeAgentStatus: normalizes each status", () => {
  assert.equal(normalizeAgentStatus("stopped"), AGENT_STATE.STOPPED);
  assert.equal(normalizeAgentStatus("running"), AGENT_STATE.RUNNING);
  // Any status class starting with "waiting" is grouped as waiting
  assert.equal(normalizeAgentStatus("waiting"), AGENT_STATE.WAITING);
  assert.equal(normalizeAgentStatus("waiting-single"), AGENT_STATE.WAITING);
  assert.equal(normalizeAgentStatus("WAITING_CONFIRM"), AGENT_STATE.WAITING);
});

test("normalizeAgentStatus: empty and unknown values normalize to idle", () => {
  assert.equal(normalizeAgentStatus(""), AGENT_STATE.IDLE);
  assert.equal(normalizeAgentStatus(null), AGENT_STATE.IDLE);
  assert.equal(normalizeAgentStatus("foo"), AGENT_STATE.IDLE);
});

// ===== buildTopology =====
test("buildTopology: auto-adds master (online) when there are no nodes", () => {
  const model = buildTopology([], [], () => "running");
  assert.equal(model.center.id, "master");
  assert.equal(model.center.isCenter, true);
  assert.equal(model.center.state, NODE_STATE.ONLINE);
  assert.deepEqual(model.nodes, []);
  assert.deepEqual(model.links, []);
  assert.equal(model.counts.nodes, 1);
  assert.equal(model.counts.online, 1);
});

test("buildTopology: agents are placed by node_id; an empty node_id goes to master", () => {
  const nodes = [{ node_id: "n1", status: "online" }];
  const agents = [
    { agent_id: "a1", name: "A1", node_id: "n1", agent_type: "code_agent" },
    { agent_id: "a2", name: "A2" }, // no node_id → master
  ];
  const model = buildTopology(nodes, agents, () => "running");
  assert.equal(model.center.agents.length, 1);
  assert.equal(model.center.agents[0].id, "a2");
  assert.equal(model.nodes.length, 1);
  assert.equal(model.nodes[0].id, "n1");
  assert.equal(model.nodes[0].agents.length, 1);
  assert.equal(model.nodes[0].agents[0].type, "code_agent");
  // Anything that is not a code_agent is grouped as agent
  assert.equal(model.center.agents[0].type, "agent");
  // links only connect master → child nodes
  assert.deepEqual(model.links, [{ source: "master", target: "n1" }]);
});

test("buildTopology: stopped agents count toward agents but not activeAgents/drawAgents", () => {
  const agents = [
    { agent_id: "a1", name: "A1", node_id: "master" },
    { agent_id: "a2", name: "A2", node_id: "master" },
  ];
  const getStatusClass = (a) => (a.agent_id === "a2" ? "stopped" : "running");
  const model = buildTopology([], agents, getStatusClass);
  assert.equal(model.counts.agents, 2);
  assert.equal(model.counts.activeAgents, 1);
  assert.equal(model.counts.stopped, 1);
  assert.equal(model.counts.running, 1);
  assert.equal(model.center.agents.length, 2);
  assert.equal(model.center.drawAgents.length, 1);
  assert.equal(model.center.drawAgents[0].id, "a1");
});

test("buildTopology: counts tally each status correctly", () => {
  const agents = [
    { agent_id: "a1", node_id: "master" },
    { agent_id: "a2", node_id: "master" },
    { agent_id: "a3", node_id: "master" },
  ];
  const statusMap = { a1: "running", a2: "waiting-single", a3: "idle" };
  const model = buildTopology([], agents, (a) => statusMap[a.agent_id]);
  assert.deepEqual(model.counts, {
    nodes: 1,
    online: 1,
    agents: 3,
    activeAgents: 3,
    waiting: 1,
    running: 1,
    stopped: 0,
    idle: 1,
  });
});

test("buildTopology: non-array inputs fall back to empty", () => {
  const model = buildTopology(null, undefined, null);
  assert.equal(model.center.id, "master");
  assert.deepEqual(model.nodes, []);
  assert.equal(model.counts.agents, 0);
});

// ===== layoutTopology =====
test("layoutTopology: default canvas 240, center in the middle", () => {
  const layout = layoutTopology({ nodes: [] }, 0, 0);
  assert.deepEqual(layout.center, { x: 120, y: 120 });
  assert.equal(layout.radius, Math.min(240, 240) * 0.34);
});

test("layoutTopology: a single node sits at the top (-90°)", () => {
  const layout = layoutTopology({ nodes: [{ id: "n1" }] }, 240, 240);
  const p = layout.nodes[0];
  assert.equal(p.id, "n1");
  assert.equal(p.angle, -Math.PI / 2);
  assert.ok(Math.abs(p.x - 120) < 1e-9);
  assert.ok(p.y < 120);
});

test("layoutTopology: multiple nodes are evenly distributed around the circle", () => {
  const layout = layoutTopology(
    { nodes: [{ id: "n1" }, { id: "n2" }, { id: "n3" }, { id: "n4" }] },
    240,
    240,
  );
  assert.equal(layout.nodes.length, 4);
  // Adjacent angle step is 2π/4
  const step = (2 * Math.PI) / 4;
  for (let i = 1; i < 4; i++) {
    assert.ok(
      Math.abs(layout.nodes[i].angle - layout.nodes[i - 1].angle - step) < 1e-9,
    );
  }
});

test("layoutTopology: radius respects the minRadius floor and can be overridden via options.radius", () => {
  const layout = layoutTopology({ nodes: [] }, 240, 240, {
    centerHalfH: 50,
    nodeHalfH: 40,
    minGap: 20,
  });
  // minRadius = 50+40+20 = 110 > 240*0.34=81.6
  assert.equal(layout.radius, 110);

  const overridden = layoutTopology({ nodes: [] }, 240, 240, { radius: 300 });
  assert.equal(overridden.radius, 300);
});

// ===== layoutAgents =====
test("layoutAgents: empty inputs produce an empty agents list", () => {
  assert.deepEqual(layoutAgents(null, null), { agents: [] });
  assert.deepEqual(layoutAgents({}, null), { agents: [] });
});

test("layoutAgents: center-node agents are arranged in a ring", () => {
  const model = {
    center: {
      id: "master",
      drawAgents: [{ id: "a1", name: "A1", state: "running" }],
    },
    nodes: [],
  };
  const nodeLayout = { center: { x: 100, y: 100 }, nodes: [] };
  const { agents } = layoutAgents(model, nodeLayout, { centerRing: 30 });
  assert.equal(agents.length, 1);
  assert.equal(agents[0].nodeId, "master");
  // A single agent sits at -90° (directly above)
  assert.ok(Math.abs(agents[0].x - 100) < 1e-9);
  assert.ok(agents[0].y < 100);
  assert.equal(agents[0].labelAnchor, "middle");
  assert.equal(agents[0].labelBaseline, "auto");
});

test("layoutAgents: child-node agents are spread within a fan facing away from the center", () => {
  const model = {
    center: { id: "master", drawAgents: [] },
    nodes: [
      {
        id: "n1",
        drawAgents: [
          { id: "a1", name: "A1", state: "running" },
          { id: "a2", name: "A2", state: "running" },
        ],
      },
    ],
  };
  // n1 sits at the top (angle=-90°), so agents should spread in the outward (upper) fan
  const nodeLayout = {
    center: { x: 100, y: 100 },
    nodes: [{ id: "n1", x: 100, y: 40, angle: -Math.PI / 2 }],
  };
  const { agents } = layoutAgents(model, nodeLayout, { ring: 20 });
  assert.equal(agents.length, 2);
  for (const a of agents) {
    assert.equal(a.nodeId, "n1");
    // The fan is centered on -90° with a spread on each side, so agent.y should be less than the node y (above)
    assert.ok(a.y < 40);
  }
});

test("layoutAgents: labelAnchor / labelBaseline follow the cos/sin boundary rules", () => {
  // Center agents are evenly spaced clockwise from the top (-90°): i=0 top, i=1 right, i=2 bottom, i=3 left
  const model = {
    center: {
      id: "master",
      drawAgents: [
        { id: "top", name: "T", state: "running" },
        { id: "right", name: "R", state: "running" },
        { id: "bottom", name: "B", state: "running" },
        { id: "left", name: "L", state: "running" },
      ],
    },
    nodes: [],
  };
  const nodeLayout = { center: { x: 0, y: 0 }, nodes: [] };
  const { agents } = layoutAgents(model, nodeLayout, { centerRing: 100 });
  const byId = Object.fromEntries(agents.map((a) => [a.id, a]));
  assert.equal(byId.top.labelAnchor, "middle");
  assert.equal(byId.top.labelBaseline, "auto");
  assert.equal(byId.right.labelAnchor, "start");
  assert.equal(byId.bottom.labelAnchor, "middle");
  assert.equal(byId.bottom.labelBaseline, "hanging");
  assert.equal(byId.left.labelAnchor, "end");
});

// ===== parseBrowserFromUserAgent =====
test("parseBrowserFromUserAgent: empty UA returns empty", () => {
  assert.deepEqual(parseBrowserFromUserAgent(""), { name: "", version: "" });
  assert.deepEqual(parseBrowserFromUserAgent(null), { name: "", version: "" });
  assert.deepEqual(parseBrowserFromUserAgent("Mozilla/5.0"), {
    name: "",
    version: "",
  });
});

test("parseBrowserFromUserAgent: recognizes each browser", () => {
  const cases = [
    ["Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36", "Chrome", "120.0.0.0"],
    ["Mozilla/5.0 Firefox/121.0", "Firefox", "121.0"],
    ["Mozilla/5.0 Version/17.0 Safari/605.1.15", "Safari", "17.0"],
    ["Mozilla/5.0 Edg/120.0.0.0", "Edge", "120.0.0.0"],
    ["Mozilla/5.0 OPR/105.0.0.0", "Opera", "105.0.0.0"],
    ["Mozilla/5.0 Vivaldi/6.5.3206.48", "Vivaldi", "6.5.3206.48"],
    ["Mozilla/5.0 YaBrowser/23.11.0.0", "Yandex", "23.11.0.0"],
  ];
  for (const [ua, name, version] of cases) {
    const r = parseBrowserFromUserAgent(ua);
    assert.equal(r.name, name, `UA=${ua}`);
    assert.equal(r.version, version, `UA=${ua}`);
  }
});

test("parseBrowserFromUserAgent: Edge/Opera take precedence over Chrome (UA contains Chrome markers)", () => {
  // An Edge UA also contains Chrome and Safari, so Edge must match first
  const edge = parseBrowserFromUserAgent(
    "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
  );
  assert.equal(edge.name, "Edge");
  const opera = parseBrowserFromUserAgent(
    "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36 OPR/105.0.0.0",
  );
  assert.equal(opera.name, "Opera");
});

// ===== formatBrowserLabel =====
test("formatBrowserLabel: browser major version + extension version", () => {
  assert.equal(
    formatBrowserLabel(
      { user_agent: "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36" },
      "5.0.5",
    ),
    "Chrome 120 · v5.0.5",
  );
});

test("formatBrowserLabel: only shows the browser when there is no extension version", () => {
  assert.equal(
    formatBrowserLabel(
      { user_agent: "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36" },
      "",
    ),
    "Chrome 120",
  );
});

test("formatBrowserLabel: only shows the extension version when there is no browser info", () => {
  assert.equal(formatBrowserLabel({}, "5.0.5"), "v5.0.5");
  assert.equal(formatBrowserLabel(null, "5.0.5"), "v5.0.5");
});

test("formatBrowserLabel: returns an empty string when everything is empty", () => {
  assert.equal(formatBrowserLabel(null, ""), "");
  assert.equal(formatBrowserLabel({ user_agent: "" }, ""), "");
});
