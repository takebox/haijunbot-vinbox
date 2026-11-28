// Pipeline progress state store (pure JS, no Vue / third-party dependencies).
//
// Consumes the backend pipeline_event broadcast (see pipeline_events.py / web_gateway bridge thread):
//   { type: "pipeline_event", payload: <event> }
// Events look like:
//   { pipeline_id, type: "pipeline_start", nodes: [{stage,agent,depends_on,...}], ... }
//   { pipeline_id, type: "pipeline_agents", agent_map: {stage: agent_id} }
//   { pipeline_id, type: "stage_update", stage, status, ... }
//   { pipeline_id, type: "pipeline_done", success, final_status, ... }
//
// Design notes:
// - Idempotent: repeated events for the same stage overwrite its status without appending nodes.
// - Bounded: only the most recent N "finished" pipelines are kept (pruneFinished); running ones are never trimmed.

export const STAGE_STATUS = {
  PENDING: "pending",
  RUNNING: "running",
  COMPLETED: "completed",
  FAILED: "failed",
  SKIPPED: "skipped",
  RETRY: "retry",
};

const TERMINAL_STATUSES = new Set([
  "completed",
  "failed",
  "aborted",
  "gate_blocked",
]);

function emptyStage(node) {
  return {
    stage: node.stage,
    agent: node.agent || "",
    agentId: "",
    dependsOn: Array.isArray(node.depends_on) ? [...node.depends_on] : [],
    input: Array.isArray(node.input) ? [...node.input] : [],
    output: node.output || "",
    gate: !!node.gate,
    when: node.when || null,
    retry: node.retry || 0,
    onError: node.on_error || "abort",
    status: STAGE_STATUS.PENDING,
    error: "",
    artifact: "",
    retryCount: 0,
    // Extra fields for loop composite nodes (kind === "loop")
    kind: node.kind || "",
    until: node.until || "",
    maxIterations: node.max_iterations || 0,
    iteration: 0,
    bodyStages: Array.isArray(node.body_stages)
      ? node.body_stages.map((b) =>
          typeof b === "string" ? b : b && b.stage ? b.stage : "",
        ).filter(Boolean)
      : [],
  };
}

// localStorage key prefix: persistence key = `${PIPELINE_STORE_KEY_PREFIX}${storageKey}`
const PIPELINE_STORE_KEY_PREFIX = "haijunbot_pipeline_store_";

export class PipelineStore {
  // When storageKey is non-empty, localStorage persistence is enabled: applyEvent
  // auto-saves a snapshot and the constructor auto-restores it, so running
  // orchestrations survive a page refresh (event broadcast is in-memory only).
  // Unit tests leave storageKey empty to stay in-memory and avoid localStorage.
  constructor(maxFinished = 20, storageKey = "") {
    this.maxFinished = maxFinished;
    this.pipelines = new Map();
    this.storageKey = storageKey;
    if (storageKey) {
      this._restoreFromStorage();
    }
  }

  _storageKey() {
    return PIPELINE_STORE_KEY_PREFIX + this.storageKey;
  }

  // Serializes the current state into plain JSON-able objects (Map → array).
  _serialize() {
    return [...this.pipelines.values()].map((s) => ({
      ...s,
      stages: [...s.stages.entries()].map(([stage, node]) => ({ stage, node })),
    }));
  }

  // Restores historical pipelines from localStorage (called by the constructor). Failures / missing data are handled silently.
  _restoreFromStorage() {
    try {
      const raw = localStorage.getItem(this._storageKey());
      if (!raw) return;
      const list = JSON.parse(raw);
      if (!Array.isArray(list)) return;
      for (const s of list) {
        if (!s || !s.pipelineId || !Array.isArray(s.stages)) continue;
        const stages = new Map();
        for (const { stage, node } of s.stages) {
          if (stage) stages.set(stage, node);
        }
        this.pipelines.set(s.pipelineId, { ...s, stages });
      }
    } catch (err) {
      // Ignore when in private mode / data is corrupt; keep an empty in-memory state
      console.warn("[PIPELINE] Failed to restore pipeline store:", err);
    }
  }

  // Writes the current state to localStorage (when persistence is enabled).
  _persist() {
    if (!this.storageKey) return;
    try {
      localStorage.setItem(
        this._storageKey(),
        JSON.stringify(this._serialize()),
      );
    } catch (err) {
      // Ignore when in private mode / quota is full; the in-memory state is unaffected
      console.warn("[PIPELINE] Failed to persist pipeline store:", err);
    }
  }

  // Applies one event; events with an unknown type or no pipeline_id are ignored.
  applyEvent(event) {
    if (!event || typeof event !== "object") return null;
    const pid = event.pipeline_id;
    if (!pid) return null;
    const type = event.type;

    if (type === "pipeline_start") {
      const stages = new Map();
      for (const n of event.nodes || []) {
        stages.set(n.stage, emptyStage(n));
      }
      const state = {
        pipelineId: pid,
        orchestrationFile: event.orchestration_file || "",
        workingDir: event.working_dir || "",
        maxWorkers: event.max_workers || 0,
        approve: !!event.approve,
        defaultOnError: event.default_on_error || "abort",
        stages,
        stageOrder: (event.nodes || []).map((n) => n.stage),
        startedAt: Date.now(),
        finishedAt: null,
        success: null,
        finalStatus: "running",
        gateStage: "",
        approvalPath: "",
        approvals: [],
      };
      this.pipelines.set(pid, state);
      this._persist();
      return state;
    }

    const state = this.pipelines.get(pid);
    if (!state) return null;

    if (type === "pipeline_agents") {
      const map = event.agent_map || {};
      for (const [stage, agentId] of Object.entries(map)) {
        const node = state.stages.get(stage);
        if (node) node.agentId = agentId;
      }
      this._persist();
      return state;
    }

    if (type === "stage_update") {
      const node = state.stages.get(event.stage);
      if (!node) return state;
      if (event.status === "retry") {
        node.status = STAGE_STATUS.RUNNING;
        node.retryCount = event.retry_count || node.retryCount;
      } else {
        node.status = event.status || node.status;
      }
      if (event.error !== undefined) node.error = event.error || "";
      if (event.artifact !== undefined) node.artifact = event.artifact || "";
      if (event.agent_id) node.agentId = event.agent_id;
      // Iteration progress of a loop body stage: record it onto its loop node
      if (event.loop) {
        const loopNode = state.stages.get(event.loop);
        if (loopNode && event.iteration) loopNode.iteration = event.iteration;
      }
      this._persist();
      return state;
    }

    // loop iteration event: updates the loop node's current iteration
    if (type === "loop_iteration") {
      const node = state.stages.get(event.stage);
      if (node) {
        node.iteration = event.iteration || node.iteration;
        if (event.max_iterations) node.maxIterations = event.max_iterations;
      }
      this._persist();
      return state;
    }

    if (type === "pipeline_done") {
      state.finishedAt = Date.now();
      state.success = !!event.success;
      state.finalStatus =
        event.final_status || (event.success ? "completed" : "failed");
      state.gateStage = event.gate_stage || "";
      state.approvalPath = event.approval_path || "";
      // Old data (restored from persistence) may lack approvals; fall back to an empty array
      if (!Array.isArray(state.approvals)) state.approvals = [];
      this.pruneFinished();
      this._persist();
      return state;
    }

    // Gate manual-approval events: pending (awaiting approval) / approve / reject / retry
    // Appended to state.approvals as an approval log for the frontend overlay and auditing.
    if (type === "pipeline_approval") {
      if (!Array.isArray(state.approvals)) state.approvals = [];
      state.approvals.push({
        action: event.action || "",
        approver: event.approver || "",
        note: event.note || "",
        gateStage: event.gate_stage || "",
        approvalPath: event.approval_path || "",
        ts: event.ts || Date.now(),
      });
      this._persist();
      return state;
    }

    return state;
  }

  getPipeline(pid) {
    return this.pipelines.get(pid) || null;
  }

  // Returns all pipelines in descending start-time order (newest first).
  listPipelines() {
    return [...this.pipelines.values()].sort(
      (a, b) => b.startedAt - a.startedAt,
    );
  }

  isFinished(state) {
    return state && state.finishedAt != null;
  }

  // Only trims "finished" pipelines, keeping the most recent maxFinished; running ones are never trimmed.
  pruneFinished() {
    const finished = this.listPipelines().filter((s) => this.isFinished(s));
    if (finished.length <= this.maxFinished) return;
    const toRemove = finished.slice(this.maxFinished);
    for (const s of toRemove) this.pipelines.delete(s.pipelineId);
  }

  clear() {
    this.pipelines.clear();
  }

  // Removes a single pipeline (preview / finished / running records can all be deleted), and syncs persistence.
  removePipeline(pipelineId) {
    const removed = this.pipelines.delete(pipelineId);
    if (removed) this._persist();
    return removed;
  }

  // Preview: adds the orchestration file's DAG structure to the store as a
  // "static graph" (no execution, no Agent creation). Unlike pipeline_start from
  // applyEvent, this is directly marked as a finished preview state so
  // OrchestrationView does not show it as "running" with the pulse animation.
  addPreview(pipelineId, nodes, orchestrationFile = "") {
    if (!pipelineId || !Array.isArray(nodes)) return null;
    const stages = new Map();
    for (const n of nodes) {
      stages.set(n.stage, emptyStage(n));
    }
    const state = {
      pipelineId,
      orchestrationFile: orchestrationFile || "",
      workingDir: "",
      maxWorkers: 0,
      approve: false,
      defaultOnError: "abort",
      stages,
      stageOrder: nodes.map((n) => n.stage),
      startedAt: Date.now(),
      finishedAt: Date.now(),
      success: true,
      finalStatus: "preview",
      gateStage: "",
      approvalPath: "",
      approvals: [],
    };
    this.pipelines.set(pipelineId, state);
    this._persist();
    return state;
  }
}

export function isTerminalStatus(status) {
  return TERMINAL_STATUSES.has(status);
}
