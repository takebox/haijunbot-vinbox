// Network topology data model and layout (pure JS, no Vue / third-party dependencies)
// nodes: [{ node_id, status, ... }]  agents: [{ agent_id, name, node_id, status, ... }]

export const NODE_STATE = {
  ONLINE: "online",
  OFFLINE: "offline",
  UNKNOWN: "unknown",
};

export const AGENT_STATE = {
  RUNNING: "running",
  WAITING: "waiting",
  IDLE: "idle",
  STOPPED: "stopped",
};

const ONLINE_ALIASES = new Set([
  "online",
  "running",
  "ready",
  "connected",
  "up",
]);

export function normalizeNodeStatus(raw) {
  const value = String(raw || "")
    .trim()
    .toLowerCase();
  if (!value) return NODE_STATE.UNKNOWN;
  if (ONLINE_ALIASES.has(value)) return NODE_STATE.ONLINE;
  if (
    value === "offline" ||
    value === "stopped" ||
    value === "down" ||
    value === "disconnected"
  ) {
    return NODE_STATE.OFFLINE;
  }
  return NODE_STATE.UNKNOWN;
}

export function normalizeAgentStatus(rawStatusClass) {
  const value = String(rawStatusClass || "")
    .trim()
    .toLowerCase();
  if (!value) return AGENT_STATE.IDLE;
  if (value === "stopped") return AGENT_STATE.STOPPED;
  if (value.startsWith("waiting")) return AGENT_STATE.WAITING;
  if (value === "running") return AGENT_STATE.RUNNING;
  return AGENT_STATE.IDLE;
}

// Assemble nodes and agents into a topology model centered on master
export function buildTopology(nodes, agents, getStatusClass) {
  const nodeList = Array.isArray(nodes) ? nodes : [];
  const agentList = Array.isArray(agents) ? agents : [];
  const resolveStatusClass =
    typeof getStatusClass === "function" ? getStatusClass : () => "running";

  const nodeMap = new Map();
  const registerNode = (id, raw) => {
    const key = String(id || "").trim() || "master";
    if (!nodeMap.has(key)) {
      nodeMap.set(key, {
        id: key,
        label: key,
        state: normalizeNodeStatus(raw && raw.status),
        isCenter: key === "master",
        agents: [],
      });
    }
    return nodeMap.get(key);
  };

  // Register all explicit nodes first, making sure master exists
  nodeList.forEach((node) => registerNode(node && node.node_id, node));
  if (!nodeMap.has("master")) {
    nodeMap.set("master", {
      id: "master",
      label: "master",
      state: NODE_STATE.ONLINE,
      isCenter: true,
      agents: [],
    });
  }

  // Place each agent under its node_id
  agentList.forEach((agent) => {
    const nodeId = String((agent && agent.node_id) || "").trim() || "master";
    const node = registerNode(
      nodeId,
      nodeMap.get(nodeId) || { status: "unknown" },
    );
    const state = normalizeAgentStatus(resolveStatusClass(agent));
    node.agents.push({
      id: String((agent && agent.agent_id) || "").trim(),
      name: String(
        (agent && agent.name) || (agent && agent.agent_id) || "",
      ).trim(),
      type:
        (agent && agent.agent_type) === "code_agent" ? "code_agent" : "agent",
      state,
      // Stopped agents are not drawn on the topology, only shown as data
      stopped: state === AGENT_STATE.STOPPED,
    });
  });

  const center = nodeMap.get("master");
  const rest = [];
  nodeMap.forEach((node) => {
    if (!node.isCenter) rest.push(node);
  });
  const orderedNodes = [...rest];

  // Agents "involved in drawing" per node (stopped ones filtered out); center handled the same way
  const pickDrawAgents = (node) => node.agents.filter((a) => !a.stopped);
  orderedNodes.forEach((node) => {
    node.drawAgents = pickDrawAgents(node);
  });
  center.drawAgents = pickDrawAgents(center);

  const links = orderedNodes.map((node) => ({
    source: "master",
    target: node.id,
  }));

  let waiting = 0;
  let running = 0;
  let stopped = 0;
  let idle = 0;
  let online = 0;
  orderedNodes.forEach((node) => {
    if (node.state === NODE_STATE.ONLINE) online++;
  });
  if (center.state === NODE_STATE.ONLINE) online++;
  let agentTotal = 0;
  let agentActive = 0;
  nodeMap.forEach((node) => {
    agentTotal += node.agents.length;
    node.agents.forEach((a) => {
      if (!a.stopped) agentActive++;
      if (a.state === AGENT_STATE.WAITING) waiting++;
      else if (a.state === AGENT_STATE.RUNNING) running++;
      else if (a.state === AGENT_STATE.STOPPED) stopped++;
      else idle++;
    });
  });

  return {
    center,
    nodes: orderedNodes,
    links,
    counts: {
      nodes: nodeMap.size,
      online,
      // agents is the full count (including stopped, for data display)
      agents: agentTotal,
      // activeAgents is the number of agents drawn (excluding stopped)
      activeAgents: agentActive,
      waiting,
      // per-status agent counts (waiting already accumulated above)
      running,
      stopped,
      idle,
    },
  };
}

// Ring layout: master at center, remaining nodes evenly distributed around the circle (first at top).
// Radius guarantee: ring node boxes must not touch/overlap the center box -- otherwise the "straight
// up" master→node link would be fully hidden and look absent (other directions stay visible via diagonal
// gaps). Lower bound = center half-height + node half-height + gap, then take the larger with canvas radius.
export function layoutTopology(model, width, height, options = {}) {
  const w = Number(width) || 240;
  const h = Number(height) || 240;
  const cx = w / 2;
  const cy = h / 2;
  const centerHalfH = Number(options.centerHalfH) || 0;
  const nodeHalfH = Number(options.nodeHalfH) || 0;
  const minGap = Number(options.minGap) || 0;
  const minRadius = centerHalfH + nodeHalfH + minGap;
  // Allow the caller to override the ring radius (e.g. large graphs want child nodes closer to the
  // center to leave more room for access nodes); when omitted, adapt to canvas size but not below minRadius
  const radius = Math.max(
    Number(options.radius) || Math.min(w, h) * 0.34,
    minRadius,
  );
  const nodes = (model && model.nodes) || [];
  const count = nodes.length;
  const positioned = nodes.map((node, index) => {
    if (count === 0) return { id: node.id, x: cx, y: cy, angle: -Math.PI / 2 };
    // Distribute evenly clockwise starting from the top (-90°)
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
    return {
      id: node.id,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      // Record the azimuth angle: the agent layout uses it to place agents on the side facing away from the center
      angle,
    };
  });
  return {
    center: { x: cx, y: cy },
    nodes: positioned,
    radius,
  };
}

// Layout the "involved in drawing" agents around their respective nodes:
// - center node: agents arranged in a full circle around it
// - other nodes: agents only placed in the outer sector facing away from the center, so that
//   inward-facing agents do not overlap neighboring nodes (and their agents)
// Each agent carries label coordinates: labels point radially outward to avoid covering node text
// options.ring: orbit radius for child-node agents; options.centerRing: orbit radius for center agents;
// options.labelGap: extra outward offset of labels beyond the agent icon's outer edge;
// options.agentRadius: agent icon radius (labels move out another labelGap beyond it, avoiding icon/antenna overlap);
// options.minGap: minimum distance between adjacent agent centers (the ring radius auto-grows if needed);
// options.canvas: { width, height } to keep the ring radius within the canvas;
// options.edgePad: minimum reserved margin from ring outer edge to canvas edge (agent radius + label)
export function layoutAgents(model, nodeLayout, options = {}) {
  const ring = Number(options.ring) || 34;
  const centerRing = Number(options.centerRing) || ring;
  const labelGap = Number(options.labelGap) || 12;
  const agentRadius = Number(options.agentRadius) || 0;
  const minGap = Number(options.minGap) || 26;
  const canvas = options.canvas || null;
  const edgePad = Number(options.edgePad) || 0;
  const placed = [];

  // Ring radius upper limit at a node: must not exceed the canvas (smallest margin in all directions)
  const ringLimitAt = (pos) => {
    if (!canvas) return Infinity;
    const w = Number(canvas.width) || 0;
    const h = Number(canvas.height) || 0;
    return Math.max(0, Math.min(pos.x, w - pos.x, pos.y, h - pos.y) - edgePad);
  };

  if (!model || !nodeLayout) return { agents: placed };

  const push = (agent, nodeId, pos, r, angle) => {
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    // Label offset another labelGap beyond the agent icon's outer edge, avoiding the icon and antenna
    const labelDist = r + agentRadius + labelGap;
    placed.push({
      id: agent.id,
      name: agent.name,
      type: agent.type || "agent",
      state: agent.state,
      nodeId,
      x: pos.x + r * cos,
      y: pos.y + r * sin,
      labelX: pos.x + labelDist * cos,
      labelY: pos.y + labelDist * sin,
      labelAnchor: cos > 0.35 ? "start" : cos < -0.35 ? "end" : "middle",
      labelBaseline: sin > 0.4 ? "hanging" : sin < -0.4 ? "auto" : "middle",
    });
  };

  // Center node: agents arranged around a full circle
  const centerPos = nodeLayout.center;
  if (model.center && centerPos) {
    const list = model.center.drawAgents || [];
    const total = list.length;
    list.forEach((agent, i) => {
      const angle = -Math.PI / 2 + (i * 2 * Math.PI) / total;
      push(agent, model.center.id, centerPos, centerRing, angle);
    });
  }

  // Other nodes: agents placed in the sector facing away from the center
  const nodeCount = (model.nodes || []).length || 1;
  // Sector half-angle: the more nodes, the narrower the sector, so neighboring sectors do not intrude on each other
  const spreadDeg = Math.min(80, Math.max(38, 180 / nodeCount - 10));
  const spread = (spreadDeg * Math.PI) / 180;
  const posMap = new Map((nodeLayout.nodes || []).map((p) => [p.id, p]));
  (model.nodes || []).forEach((node) => {
    const pos = posMap.get(node.id);
    const list = node.drawAgents || [];
    if (!pos || list.length === 0) return;
    // Outward direction: the node's azimuth angle relative to the center
    const baseAngle = Number.isFinite(pos.angle) ? pos.angle : -Math.PI / 2;
    const total = list.length;
    const step = total > 1 ? (spread * 2) / (total - 1) : 0;
    // With many agents the arc spacing is insufficient; automatically enlarge the ring radius
    // (keeping adjacent agent center distance >= minGap) but not beyond the node's available
    // canvas margin, to avoid overflowing the canvas
    const limit = ringLimitAt(pos);
    const r =
      total > 1 && step > 0
        ? Math.min(limit, Math.max(ring, minGap / (2 * Math.sin(step / 2))))
        : Math.min(ring, limit);
    list.forEach((agent, i) => {
      const angle = total > 1 ? baseAngle - spread + i * step : baseAngle;
      push(agent, node.id, pos, r, angle);
    });
  });

  return { agents: placed };
}

// Browser UA parsing: extract "browser name + major version" from browser_info.user_agent for access-node display.
// Zero dependencies, pure regex; returns an empty string when unrecognized (the caller decides the fallback text).
// Ordering matters: Edge/Opera UAs also contain Chrome/Safari markers, so more specific patterns must match first.
const BROWSER_UA_PATTERNS = [
  { name: "Edge", re: /Edg(?:e|A|iOS)?\/([\d.]+)/ },
  { name: "Opera", re: /(?:OPR|Opera)\/([\d.]+)/ },
  { name: "Vivaldi", re: /Vivaldi\/([\d.]+)/ },
  { name: "Yandex", re: /YaBrowser\/([\d.]+)/ },
  { name: "Firefox", re: /(?:Firefox|FxiOS)\/([\d.]+)/ },
  { name: "Chrome", re: /(?:Chrome|CriOS)\/([\d.]+)/ },
  { name: "Safari", re: /Version\/([\d.]+).*Safari/ },
];

export function parseBrowserFromUserAgent(userAgent) {
  const ua = String(userAgent || "");
  if (!ua) return { name: "", version: "" };
  for (const { name, re } of BROWSER_UA_PATTERNS) {
    const m = ua.match(re);
    if (m) return { name, version: m[1] || "" };
  }
  return { name: "", version: "" };
}

// Build the display label for a browser-extension node, e.g. "Edge 153 · v5.0.5".
// browserInfo is the gateway session's browser_info (includes user_agent); extensionVersion is the extension version.
export function formatBrowserLabel(browserInfo, extensionVersion) {
  const info =
    browserInfo && typeof browserInfo === "object" ? browserInfo : {};
  const { name, version } = parseBrowserFromUserAgent(info.user_agent);
  const major = version ? String(version).split(".")[0] : "";
  const browser = name ? (major ? `${name} ${major}` : name) : "";
  const ext = String(extensionVersion || "").trim();
  const extLabel = ext ? `v${ext}` : "";
  return [browser, extLabel].filter(Boolean).join(" · ");
}
