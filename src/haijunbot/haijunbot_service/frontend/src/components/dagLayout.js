// Pipeline DAG layered layout (pure JS, no Vue / third-party dependencies).
//
// Input: stages (an array or the values of a Map), each item is { stage, dependsOn: [...] }.
// Output: layered coordinates and edges, used by OrchestrationView's self-drawn SVG.
//
// Layout strategy:
// - level: no dependencies = 0; otherwise 1 + max(level of dependencies). Cycle-proof (falls back to declaration order).
// - Nodes on the same level stack vertically in declaration order (y increases), levels spread horizontally (x increases).

export const LAYOUT = {
  NODE_W: 180,
  NODE_H: 64,
  GAP_X: 90,
  GAP_Y: 28,
  PAD_X: 24,
  PAD_Y: 24,
};

// Compute the level of each stage (cycle-proof).
export function computeLevels(stages) {
  const list = normalizeStages(stages);
  const byStage = new Map(list.map((s) => [s.stage, s]));
  const levelCache = new Map();

  function levelOf(stage, visiting) {
    if (levelCache.has(stage)) return levelCache.get(stage);
    if (visiting.has(stage)) return 0; // cycle: fall back to avoid infinite recursion
    const node = byStage.get(stage);
    if (!node) return 0;
    visiting.add(stage);
    let maxDep = -1;
    for (const d of node.dependsOn) {
      if (!byStage.has(d)) continue;
      maxDep = Math.max(maxDep, levelOf(d, visiting));
    }
    visiting.delete(stage);
    const level = maxDep < 0 ? 0 : maxDep + 1;
    levelCache.set(stage, level);
    return level;
  }

  const levels = new Map();
  for (const s of list) levels.set(s.stage, levelOf(s.stage, new Set()));
  return levels;
}

function normalizeStages(stages) {
  let arr = [];
  if (stages instanceof Map) arr = [...stages.values()];
  else if (Array.isArray(stages)) arr = stages;
  else if (stages && typeof stages === "object") arr = Object.values(stages);
  return arr
    .filter((s) => s && s.stage)
    .map((s) => ({
      stage: s.stage,
      dependsOn: Array.isArray(s.dependsOn)
        ? s.dependsOn
        : Array.isArray(s.depends_on)
          ? s.depends_on
          : [],
    }));
}

// Compute layout: returns { width, height, positions: {stage:{x,y}}, edges:[{from,to}], levels }.
export function layoutDag(stages) {
  const list = normalizeStages(stages);
  const levels = computeLevels(list);

  // Group by level, keeping declaration order within each group
  const columns = new Map();
  for (const s of list) {
    const lv = levels.get(s.stage) || 0;
    if (!columns.has(lv)) columns.set(lv, []);
    columns.get(lv).push(s.stage);
  }
  const maxLevel = columns.size ? Math.max(...columns.keys()) : 0;
  const maxRows = columns.size
    ? Math.max(...[...columns.values()].map((c) => c.length))
    : 0;

  const positions = {};
  for (const [lv, stagesInCol] of columns.entries()) {
    const colH = stagesInCol.length * LAYOUT.NODE_H + (stagesInCol.length - 1) * LAYOUT.GAP_Y;
    const totalH = maxRows * LAYOUT.NODE_H + (maxRows - 1) * LAYOUT.GAP_Y;
    const startY = LAYOUT.PAD_Y + (totalH - colH) / 2;
    stagesInCol.forEach((stage, i) => {
      positions[stage] = {
        x: LAYOUT.PAD_X + lv * (LAYOUT.NODE_W + LAYOUT.GAP_X),
        y: startY + i * (LAYOUT.NODE_H + LAYOUT.GAP_Y),
        level: lv,
      };
    });
  }

  const edges = [];
  for (const s of list) {
    for (const d of s.dependsOn) {
      if (positions[d] && positions[s.stage]) {
        edges.push({ from: d, to: s.stage });
      }
    }
  }

  const width = LAYOUT.PAD_X * 2 + (maxLevel + 1) * LAYOUT.NODE_W + maxLevel * LAYOUT.GAP_X;
  const height =
    LAYOUT.PAD_Y * 2 + Math.max(maxRows, 1) * LAYOUT.NODE_H + Math.max(maxRows - 1, 0) * LAYOUT.GAP_Y;

  return { width, height, positions, edges, levels };
}

// Generate the cubic bezier path connecting from→to (horizontal flow).
export function edgePath(fromPos, toPos) {
  const x1 = fromPos.x + LAYOUT.NODE_W;
  const y1 = fromPos.y + LAYOUT.NODE_H / 2;
  const x2 = toPos.x;
  const y2 = toPos.y + LAYOUT.NODE_H / 2;
  const dx = Math.max((x2 - x1) / 2, 20);
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}
