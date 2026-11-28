// pluginExtensions.js unit tests (vitest).
//
// How to run (from the frontend directory):
//   npx vitest run src/pluginExtensions.test.js   # run only this file
//   npm run test:vitest                           # run all vitest tests
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import {
  fetchPluginExtensions,
  buildExtensionUrl,
  loadExtensionComponent,
  clearExtensionCache,
} from "./pluginExtensions.js";

// Build a mock fetchWithAuth that returns preset responses by URL
function makeFetch(handlers) {
  return vi.fn(async (url, options = {}) => {
    const method = options.method || "GET";
    const key = `${method} ${url}`;
    const handler = handlers[key] || handlers["default"];
    if (!handler) throw new Error(`No handler for ${key}`);
    return { ok: true, json: async () => handler() };
  });
}

const baseOpts = {
  fetchWithAuth: vi.fn(),
  baseUrl: "127.0.0.1:8000",
  getHttpProtocol: () => "http",
};

describe("fetchPluginExtensions", () => {
  test("parses each plugin frontend extension point and builds extension items", async () => {
    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/plugins?node_id=master": () => ({
        success: true,
        data: {
          node_id: "master",
          plugins: [
            {
              name: "demo",
              version: "0.1.0",
              frontend: {
                admin_tabs: [
                  { id: "dashboard", title: "Dashboard", entry: "admin.js" },
                ],
                sidebar_views: [
                  { id: "stats", title: "Stats", entry: "side.js" },
                ],
                tool_panels: [{ id: "tool1", title: "Tool", entry: "tool.js" }],
              },
            },
          ],
        },
      }),
    });

    const exts = await fetchPluginExtensions({ ...baseOpts, fetchWithAuth });
    expect(exts).toHaveLength(3);
    const admin = exts.find((e) => e.extType === "admin_tabs");
    expect(admin).toMatchObject({
      nodeId: "master",
      plugin: "demo",
      pluginVersion: "0.1.0",
      extType: "admin_tabs",
      id: "dashboard",
      title: "Dashboard",
      entry: "admin.js",
    });
    expect(admin.url).toBe(
      "http://127.0.0.1:8000/api/plugins/master/demo/frontend/admin.js",
    );
    expect(exts.find((e) => e.extType === "sidebar_views").id).toBe("stats");
    expect(exts.find((e) => e.extType === "tool_panels").id).toBe("tool1");
  });

  test("skips items without a frontend declaration or with invalid entries", async () => {
    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/plugins?node_id=master": () => ({
        success: true,
        data: {
          node_id: "master",
          plugins: [
            { name: "a", version: "1", frontend: null },
            {
              name: "b",
              version: "1",
              frontend: { admin_tabs: [{ title: "no id" }] },
            },
            {
              name: "c",
              version: "1",
              frontend: { admin_tabs: [{ id: "x", entry: "" }] },
            },
          ],
        },
      }),
    });

    const exts = await fetchPluginExtensions({ ...baseOpts, fetchWithAuth });
    expect(exts).toHaveLength(0);
  });

  test("returns an empty array when the request fails or the response is unsuccessful", async () => {
    const fetchWithAuth = vi.fn(async () => ({ ok: false }));
    const exts = await fetchPluginExtensions({ ...baseOpts, fetchWithAuth });
    expect(exts).toEqual([]);
  });

  test("silently returns an empty array on errors", async () => {
    const fetchWithAuth = vi.fn(async () => {
      throw new Error("network down");
    });
    const exts = await fetchPluginExtensions({ ...baseOpts, fetchWithAuth });
    expect(exts).toEqual([]);
  });
});

describe("buildExtensionUrl", () => {
  test("builds the serve endpoint URL (strips leading slash, encodes node and plugin name)", () => {
    const url = buildExtensionUrl({
      nodeId: "node/1",
      plugin: "my plugin",
      entry: "/admin.js",
      baseUrl: "127.0.0.1:8000",
      getHttpProtocol: () => "http",
    });
    expect(url).toBe(
      "http://127.0.0.1:8000/api/plugins/node%2F1/my%20plugin/frontend/admin.js",
    );
  });
});

describe("loadExtensionComponent", () => {
  beforeEach(() => {
    clearExtensionCache();
  });
  afterEach(() => {
    clearExtensionCache();
  });

  test("fetches JS source from the backend and imports the component default export via Blob", async () => {
    // Use a data URL as the createObjectURL return value so the dynamic import actually executes in Node
    globalThis.Blob = vi.fn(function (parts) {
      return { parts };
    });
    globalThis.URL.createObjectURL = vi.fn(
      () =>
        "data:text/javascript,export default { name: 'FakeExt', render() {} }",
    );
    globalThis.URL.revokeObjectURL = vi.fn();

    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/plugins/master/demo/frontend/admin.js":
        () => ({
          success: true,
          data: {
            node_id: "master",
            name: "demo",
            content: "export default {}",
          },
        }),
    });

    const ext = {
      nodeId: "master",
      plugin: "demo",
      extType: "admin_tabs",
      id: "dashboard",
      entry: "admin.js",
      url: "http://127.0.0.1:8000/api/plugins/master/demo/frontend/admin.js",
    };

    const comp = await loadExtensionComponent(ext, {
      fetchWithAuth,
      getHttpProtocol: () => "http",
    });
    expect(comp).toBeTruthy();
    expect(comp.name).toBe("FakeExt");
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalled();
  });

  test("returns null when the response has no content or fails", async () => {
    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/plugins/master/demo/frontend/admin.js":
        () => ({
          success: true,
          data: { content: "" },
        }),
    });
    const ext = {
      nodeId: "master",
      plugin: "demo",
      extType: "admin_tabs",
      id: "dashboard",
      entry: "admin.js",
      url: "http://127.0.0.1:8000/api/plugins/master/demo/frontend/admin.js",
    };
    const comp = await loadExtensionComponent(ext, {
      fetchWithAuth,
      getHttpProtocol: () => "http",
    });
    expect(comp).toBeNull();
  });

  test("components are cached and reused for the same key", async () => {
    let calls = 0;
    const fetchWithAuth = vi.fn(async () => {
      calls += 1;
      return {
        ok: true,
        json: async () => ({
          success: true,
          data: { content: "export default 1" },
        }),
      };
    });
    const ext = {
      nodeId: "master",
      plugin: "demo",
      extType: "admin_tabs",
      id: "dashboard",
      entry: "admin.js",
      url: "http://127.0.0.1:8000/api/plugins/master/demo/frontend/admin.js",
    };
    // First time: mock Blob/URL, createObjectURL returns a data URL that can really be imported
    globalThis.Blob = vi.fn(function () {
      return {};
    });
    globalThis.URL.createObjectURL = vi.fn(
      () => "data:text/javascript,export default { name: 'C' }",
    );
    globalThis.URL.revokeObjectURL = vi.fn();

    const c1 = await loadExtensionComponent(ext, {
      fetchWithAuth,
      getHttpProtocol: () => "http",
    });
    const c2 = await loadExtensionComponent(ext, {
      fetchWithAuth,
      getHttpProtocol: () => "http",
    });
    expect(c1).toBe(c2);
    // Cache hit: no repeated fetch
    expect(calls).toBe(1);
  });
});
