// Unit tests for pipelineStore (zero dependencies, using node's built-in test runner).
//
// How to run (from the frontend directory):
//   node --test src/stores/pipelineStore.test.mjs   # run only this file
//   node --test                                      # auto-discover all *.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { PipelineStore, STAGE_STATUS } from "./pipelineStore.js";

function startEvent(pid, stages) {
  return {
    pipeline_id: pid,
    type: "pipeline_start",
    orchestration_file: "/x/pipeline.yaml",
    nodes: stages.map((s) => ({
      stage: s.stage,
      agent: s.agent || "a",
      depends_on: s.depends_on || [],
      input: [],
      output: s.output || "",
      gate: !!s.gate,
      when: null,
      retry: 0,
      on_error: "abort",
    })),
  };
}

test("pipeline_start: builds the pipeline and initializes every stage as pending", () => {
  const store = new PipelineStore();
  store.applyEvent(
    startEvent("p1", [{ stage: "s1" }, { stage: "s2", depends_on: ["s1"] }]),
  );
  const st = store.getPipeline("p1");
  assert.ok(st);
  assert.equal(st.stages.get("s1").status, STAGE_STATUS.PENDING);
  assert.equal(st.stages.get("s2").status, STAGE_STATUS.PENDING);
  assert.deepEqual(st.stages.get("s2").dependsOn, ["s1"]);
});

test("pipeline_agents: backfills agentId", () => {
  const store = new PipelineStore();
  store.applyEvent(startEvent("p1", [{ stage: "s1" }]));
  store.applyEvent({
    pipeline_id: "p1",
    type: "pipeline_agents",
    agent_map: { s1: "agent-123" },
  });
  assert.equal(store.getPipeline("p1").stages.get("s1").agentId, "agent-123");
});

test("stage_update: updates status and error info", () => {
  const store = new PipelineStore();
  store.applyEvent(startEvent("p1", [{ stage: "s1" }]));
  store.applyEvent({
    pipeline_id: "p1",
    type: "stage_update",
    stage: "s1",
    status: "running",
  });
  assert.equal(
    store.getPipeline("p1").stages.get("s1").status,
    STAGE_STATUS.RUNNING,
  );
  store.applyEvent({
    pipeline_id: "p1",
    type: "stage_update",
    stage: "s1",
    status: "failed",
    error: "boom",
  });
  const node = store.getPipeline("p1").stages.get("s1");
  assert.equal(node.status, STAGE_STATUS.FAILED);
  assert.equal(node.error, "boom");
});

test("stage_update retry: resets status to running and records the retry count", () => {
  const store = new PipelineStore();
  store.applyEvent(startEvent("p1", [{ stage: "s1" }]));
  store.applyEvent({
    pipeline_id: "p1",
    type: "stage_update",
    stage: "s1",
    status: "retry",
    retry_count: 2,
  });
  const node = store.getPipeline("p1").stages.get("s1");
  assert.equal(node.status, STAGE_STATUS.RUNNING);
  assert.equal(node.retryCount, 2);
});

test("pipeline_done: sets the terminal state and records success/finalStatus", () => {
  const store = new PipelineStore();
  store.applyEvent(startEvent("p1", [{ stage: "s1" }]));
  store.applyEvent({
    pipeline_id: "p1",
    type: "pipeline_done",
    success: false,
    final_status: "failed",
  });
  const st = store.getPipeline("p1");
  assert.equal(st.success, false);
  assert.equal(st.finalStatus, "failed");
  assert.ok(st.finishedAt);
});

test("idempotency: repeated stage_update overwrites without appending nodes", () => {
  const store = new PipelineStore();
  store.applyEvent(startEvent("p1", [{ stage: "s1" }]));
  store.applyEvent({
    pipeline_id: "p1",
    type: "stage_update",
    stage: "s1",
    status: "running",
  });
  store.applyEvent({
    pipeline_id: "p1",
    type: "stage_update",
    stage: "s1",
    status: "running",
  });
  assert.equal(store.getPipeline("p1").stages.size, 1);
});

test("pipeline_approval: appends approval log entries to approvals", () => {
  const store = new PipelineStore();
  store.applyEvent(startEvent("p1", [{ stage: "gate1", gate: true }]));
  // Broadcast pending first (awaiting approval)
  store.applyEvent({
    pipeline_id: "p1",
    type: "pipeline_approval",
    action: "pending",
    gate_stage: "gate1",
    approval_path: "/x/report.md",
    ts: 1000,
  });
  // Then broadcast an approval decision (approve)
  store.applyEvent({
    pipeline_id: "p1",
    type: "pipeline_approval",
    action: "approve",
    approver: "admin",
    note: "Looks good",
    gate_stage: "gate1",
    approval_path: "/x/report.md",
    ts: 2000,
  });
  const st = store.getPipeline("p1");
  assert.ok(Array.isArray(st.approvals), "approvals should be an array");
  assert.equal(st.approvals.length, 2);
  assert.equal(st.approvals[0].action, "pending");
  assert.equal(st.approvals[0].gateStage, "gate1");
  assert.equal(st.approvals[1].action, "approve");
  assert.equal(st.approvals[1].approver, "admin");
  assert.equal(st.approvals[1].note, "Looks good");
  assert.equal(st.approvals[1].ts, 2000);
});

test("pipeline_start / addPreview initialize approvals as an empty array", () => {
  const store = new PipelineStore();
  store.applyEvent(startEvent("p1", [{ stage: "s1" }]));
  assert.deepEqual(store.getPipeline("p1").approvals, []);
  const st = store.addPreview(
    "preview_x",
    [
      {
        stage: "s1",
        agent: "a",
        depends_on: [],
        input: [],
        output: "",
        gate: false,
        when: null,
        retry: 0,
        on_error: "abort",
      },
    ],
    "/x/p.yaml",
  );
  assert.deepEqual(st.approvals, []);
});

test("pipeline_done: falls back to an empty array when old data has no approvals", () => {
  const store = new PipelineStore();
  store.applyEvent(startEvent("p1", [{ stage: "s1" }]));
  // Simulate old data restored from persistence: no approvals field
  delete store.getPipeline("p1").approvals;
  store.applyEvent({
    pipeline_id: "p1",
    type: "pipeline_done",
    success: true,
    final_status: "completed",
  });
  assert.deepEqual(
    store.getPipeline("p1").approvals,
    [],
    "pipeline_done should initialize approvals as a fallback",
  );
});

test("stage_update for an unknown pipeline_id is ignored", () => {
  const store = new PipelineStore();
  assert.equal(
    store.applyEvent({
      pipeline_id: "nope",
      type: "stage_update",
      stage: "s1",
    }),
    null,
  );
  assert.equal(store.pipelines.size, 0);
});

test("listPipelines: sorts by startedAt descending", () => {
  const store = new PipelineStore();
  store.applyEvent(startEvent("p1", [{ stage: "s1" }]));
  store.getPipeline("p1").startedAt = 1000;
  store.applyEvent(startEvent("p2", [{ stage: "s1" }]));
  store.getPipeline("p2").startedAt = 2000;
  assert.deepEqual(
    store.listPipelines().map((s) => s.pipelineId),
    ["p2", "p1"],
  );
});

test("pruneFinished: keeps only the most recent N finished pipelines; running ones are not trimmed", () => {
  const store = new PipelineStore(2);
  // 3 finished
  for (let i = 0; i < 3; i++) {
    store.applyEvent(startEvent(`done${i}`, [{ stage: "s1" }]));
    store.getPipeline(`done${i}`).startedAt = i;
    store.applyEvent({
      pipeline_id: `done${i}`,
      type: "pipeline_done",
      success: true,
    });
  }
  // 1 running (started earlier, must not be trimmed)
  store.applyEvent(startEvent("live", [{ stage: "s1" }]));
  store.getPipeline("live").startedAt = -1;

  store.pruneFinished();
  const ids = store.listPipelines().map((s) => s.pipelineId);
  // Finished: keep the latest 2 (done2, done1); done0 is trimmed
  assert.ok(ids.includes("done2"));
  assert.ok(ids.includes("done1"));
  assert.ok(!ids.includes("done0"));
  assert.ok(ids.includes("live"));
});

test("non-object / no-pipeline_id events are ignored", () => {
  const store = new PipelineStore();
  assert.equal(store.applyEvent(null), null);
  assert.equal(store.applyEvent("x"), null);
  assert.equal(store.applyEvent({ type: "pipeline_start" }), null);
});

// ---- localStorage persistence (enabled when storageKey is non-empty) ----
function installLocalStorageMock() {
  const backing = new Map();
  const storage = {
    getItem: (k) => (backing.has(k) ? backing.get(k) : null),
    setItem: (k, v) => backing.set(k, String(v)),
    removeItem: (k) => backing.delete(k),
    clear: () => backing.clear(),
    _backing: backing,
  };
  globalThis.localStorage = storage;
  return storage;
}

test("with a storageKey, applyEvent persists automatically and a new instance can restore", () => {
  const storage = installLocalStorageMock();
  const store = new PipelineStore(20, "orchestration");
  store.applyEvent(
    startEvent("p1", [{ stage: "s1" }, { stage: "s2", depends_on: ["s1"] }]),
  );
  store.applyEvent({
    pipeline_id: "p1",
    type: "stage_update",
    stage: "s1",
    status: "completed",
    artifact: "out.md",
  });
  store.applyEvent({
    pipeline_id: "p1",
    type: "pipeline_done",
    success: true,
    final_status: "completed",
  });

  // The persistence key exists and its content is non-empty
  const key = "haijunbot_pipeline_store_orchestration";
  assert.ok(storage.getItem(key), "should write to localStorage");

  // A new instance (simulating a refresh) can restore from localStorage
  const restored = new PipelineStore(20, "orchestration");
  const st = restored.getPipeline("p1");
  assert.ok(st, "should restore the pipeline after a refresh");
  assert.equal(st.stages.get("s1").status, STAGE_STATUS.COMPLETED);
  assert.equal(st.stages.get("s1").artifact, "out.md");
  assert.equal(st.finalStatus, "completed");
});

test("without a storageKey it stays purely in-memory and never touches localStorage", () => {
  const storage = installLocalStorageMock();
  const store = new PipelineStore();
  store.applyEvent(startEvent("p1", [{ stage: "s1" }]));
  assert.equal(
    storage.getItem("haijunbot_pipeline_store_"),
    null,
    "should not write to localStorage",
  );
});

test("addPreview: adds the DAG in a static preview state; every stage is pending and nothing runs", () => {
  const store = new PipelineStore();
  const nodes = [
    {
      stage: "s1",
      agent: "a",
      depends_on: [],
      input: [],
      output: "",
      gate: false,
      when: null,
      retry: 0,
      on_error: "abort",
    },
    {
      stage: "s2",
      agent: "b",
      depends_on: ["s1"],
      input: [],
      output: "",
      gate: false,
      when: null,
      retry: 0,
      on_error: "abort",
    },
  ];
  const st = store.addPreview("preview_x", nodes, "/x/pipeline.yaml");
  assert.ok(st, "should return the new state");
  assert.equal(st.finalStatus, "preview");
  assert.ok(st.finishedAt, "a preview state should be treated as finished to avoid the pulse animation");
  assert.equal(st.success, true);
  assert.equal(st.orchestrationFile, "/x/pipeline.yaml");
  assert.equal(st.stages.get("s1").status, STAGE_STATUS.PENDING);
  assert.equal(st.stages.get("s2").status, STAGE_STATUS.PENDING);
  assert.deepEqual(st.stageOrder, ["s1", "s2"]);
  assert.equal(store.getPipeline("preview_x"), st);
});

test("addPreview: returns null when pipelineId is missing or nodes are invalid", () => {
  const store = new PipelineStore();
  assert.equal(store.addPreview("", []), null);
  assert.equal(store.addPreview("p", null), null);
  assert.equal(store.addPreview("p", "not-array"), null);
});

test("removePipeline: removes a single pipeline and syncs persistence", () => {
  installLocalStorageMock();
  const store = new PipelineStore(20, "del");
  store.addPreview(
    "preview_a",
    [
      {
        stage: "s1",
        agent: "a",
        depends_on: [],
        input: [],
        output: "",
        gate: false,
        when: null,
        retry: 0,
        on_error: "abort",
      },
    ],
    "/x/a.yaml",
  );
  store.addPreview(
    "preview_b",
    [
      {
        stage: "s1",
        agent: "b",
        depends_on: [],
        input: [],
        output: "",
        gate: false,
        when: null,
        retry: 0,
        on_error: "abort",
      },
    ],
    "/x/b.yaml",
  );
  assert.equal(store.listPipelines().length, 2);

  // Removing an existing item
  assert.equal(store.removePipeline("preview_a"), true);
  assert.equal(store.listPipelines().length, 1);
  assert.equal(store.getPipeline("preview_a"), null);
  assert.ok(store.getPipeline("preview_b"), "non-removed items should be kept");

  // Removing a non-existent item returns false
  assert.equal(store.removePipeline("preview_a"), false);

  // Persistence is synced: a new instance only restores the remaining items
  const restored = new PipelineStore(20, "del");
  assert.equal(restored.listPipelines().length, 1);
  assert.equal(
    restored.getPipeline("preview_b").orchestrationFile,
    "/x/b.yaml",
  );
});
