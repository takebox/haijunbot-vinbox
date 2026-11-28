// Unit tests for the LSP language server registry (src/lsp/registry.js) using node:test + node:assert/strict.
//
// How to run (from the frontend directory):
//   node --test src/lsp/registry.test.mjs
//
// Note: registry.js has module-level mutable state (serverByLanguage /
// serverByExtension / loaded / loadPromise) and loadLspServers is cached.
// node:test runs each file in its own process, but state in one module instance
// persists across cases within the same file. For a clean slate, this test uses
// "dynamic import + URL query strings" so Node treats `registry.js?case=N` as
// distinct module instances (ESM allows query strings to distinguish modules),
// giving each case an isolated instance with no cross-talk. Dependencies such as
// fetchWithAuth are injected as mocks via arguments.
import { test } from "node:test";
import assert from "node:assert/strict";

// Dynamically import an isolated module instance (distinguished by the case query string)
async function loadRegistry(caseNo) {
  return await import(`./registry.js?case=${caseNo}`);
}

// Build default deps: fetchWithAuth returns ok + empty servers
function makeDeps(overrides = {}) {
  const fetchWithAuth =
    overrides.fetchWithAuth ||
    (async () => ({
      ok: true,
      status: 200,
      json: async () => ({ servers: [] }),
    }));
  return {
    fetchWithAuth,
    getGatewayAddress:
      overrides.getGatewayAddress ||
      (() => ({ host: "localhost", port: "8080" })),
    getHttpProtocol: overrides.getHttpProtocol || (() => "http"),
  };
}

test("initial state: not loaded, lookups return null", async () => {
  const reg = await loadRegistry(1);
  assert.equal(reg.isLspRegistryLoaded(), false);
  assert.equal(reg.getServerByLanguage("python"), null);
  assert.equal(reg.getServerByPath("a.py"), null);
});

test("loadLspServers success: indexes by monacoLanguage and extensions", async () => {
  const reg = await loadRegistry(2);
  const servers = [
    { id: "python", monacoLanguage: "python", extensions: [".py", ".PYI"] },
    { id: "js", monacoLanguage: "javascript", extensions: [".js"] },
  ];
  const deps = makeDeps({
    fetchWithAuth: async () => ({
      ok: true,
      status: 200,
      json: async () => ({ servers }),
    }),
  });
  const result = await reg.loadLspServers(deps);
  assert.ok(result instanceof Map);
  // indexed by language
  assert.equal(reg.getServerByLanguage("python").id, "python");
  assert.equal(reg.getServerByLanguage("javascript").id, "js");
  // indexed by extension (dot included, lowercased)
  assert.equal(reg.getServerByPath("main.PY").id, "python");
  assert.equal(reg.getServerByPath("app.js").id, "js");
  assert.equal(reg.isLspRegistryLoaded(), true);
});

test("only the first entry per monacoLanguage is kept", async () => {
  const reg = await loadRegistry(3);
  const servers = [
    { id: "py1", monacoLanguage: "python", extensions: [".py"] },
    { id: "py2", monacoLanguage: "python", extensions: [".py"] },
  ];
  const deps = makeDeps({
    fetchWithAuth: async () => ({
      ok: true,
      status: 200,
      json: async () => ({ servers }),
    }),
  });
  await reg.loadLspServers(deps);
  assert.equal(reg.getServerByLanguage("python").id, "py1");
});

test("cache: a second call (force=false) does not re-fetch", async () => {
  const reg = await loadRegistry(4);
  let callCount = 0;
  const deps = makeDeps({
    fetchWithAuth: async () => {
      callCount++;
      return {
        ok: true,
        status: 200,
        json: async () => ({
          servers: [
            { id: "py", monacoLanguage: "python", extensions: [".py"] },
          ],
        }),
      };
    },
  });
  await reg.loadLspServers(deps);
  await reg.loadLspServers(deps);
  assert.equal(callCount, 1);
});

test("force=true re-fetches", async () => {
  const reg = await loadRegistry(5);
  let callCount = 0;
  const deps = makeDeps({
    fetchWithAuth: async () => {
      callCount++;
      return { ok: true, status: 200, json: async () => ({ servers: [] }) };
    },
  });
  await reg.loadLspServers(deps);
  await reg.loadLspServers(deps, true);
  assert.equal(callCount, 2);
});

test("response.ok=false returns an empty Map without throwing", async () => {
  const reg = await loadRegistry(6);
  const deps = makeDeps({
    fetchWithAuth: async () => ({ ok: false, status: 500 }),
  });
  const result = await reg.loadLspServers(deps);
  assert.ok(result instanceof Map);
  assert.equal(result.size, 0);
  assert.equal(reg.isLspRegistryLoaded(), false);
});

test("an exception from fetchWithAuth is caught, not rethrown, and returns a Map", async () => {
  const reg = await loadRegistry(7);
  const deps = makeDeps({
    fetchWithAuth: async () => {
      throw new Error("network down");
    },
  });
  const result = await reg.loadLspServers(deps);
  assert.ok(result instanceof Map);
  assert.equal(reg.isLspRegistryLoaded(), false);
});

test("a non-array servers value is treated as empty without throwing", async () => {
  const reg = await loadRegistry(8);
  const deps = makeDeps({
    fetchWithAuth: async () => ({
      ok: true,
      status: 200,
      json: async () => ({ servers: "oops" }),
    }),
  });
  const result = await reg.loadLspServers(deps);
  assert.ok(result instanceof Map);
  assert.equal(result.size, 0);
});

test("entries missing id or monacoLanguage are skipped; missing extensions does not error", async () => {
  const reg = await loadRegistry(9);
  const servers = [
    { id: "ok", monacoLanguage: "python", extensions: [".py"] },
    { id: "no-lang", extensions: [".x"] }, // missing monacoLanguage → skipped
    { monacoLanguage: "no-id", extensions: [".y"] }, // missing id → skipped
    { id: "no-ext", monacoLanguage: "plaintext" }, // missing extensions → no error
  ];
  const deps = makeDeps({
    fetchWithAuth: async () => ({
      ok: true,
      status: 200,
      json: async () => ({ servers }),
    }),
  });
  await reg.loadLspServers(deps);
  assert.equal(reg.getServerByLanguage("python").id, "ok");
  assert.equal(reg.getServerByLanguage("no-lang"), null);
  assert.equal(reg.getServerByLanguage("no-id"), null);
  // a language without extensions can still be found by language id
  assert.equal(reg.getServerByLanguage("plaintext").id, "no-ext");
});

test("getServerByLanguage: empty/miss returns null, hit returns the spec", async () => {
  const reg = await loadRegistry(10);
  const deps = makeDeps({
    fetchWithAuth: async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        servers: [{ id: "py", monacoLanguage: "python", extensions: [".py"] }],
      }),
    }),
  });
  await reg.loadLspServers(deps);
  assert.equal(reg.getServerByLanguage(""), null);
  assert.equal(reg.getServerByLanguage(undefined), null);
  assert.equal(reg.getServerByLanguage("golang"), null);
  assert.equal(reg.getServerByLanguage("python").id, "py");
});

test("getServerByPath: empty/no-extension/unregistered returns null, case-insensitive hits work", async () => {
  const reg = await loadRegistry(11);
  const deps = makeDeps({
    fetchWithAuth: async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        servers: [{ id: "py", monacoLanguage: "python", extensions: [".py"] }],
      }),
    }),
  });
  await reg.loadLspServers(deps);
  assert.equal(reg.getServerByPath(""), null);
  assert.equal(reg.getServerByPath(undefined), null);
  assert.equal(reg.getServerByPath("noext"), null); // no extension
  assert.equal(reg.getServerByPath("a.PY").id, "py"); // case-insensitive hit
  assert.equal(reg.getServerByPath("/deep/dir/main.py").id, "py"); // deep paths use the last extension
  assert.equal(reg.getServerByPath("main.go"), null); // unregistered extension
});
