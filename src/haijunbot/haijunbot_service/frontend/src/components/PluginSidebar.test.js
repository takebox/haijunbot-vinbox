// PluginSidebar component unit tests (vitest + @vue/test-utils + jsdom).
//
// How to run (from the frontend directory):
//   npx vitest run src/components/PluginSidebar.test.js   # run only this file
//   npm run test:vitest                                   # run all vitest cases
//
// Note: PluginSidebar uses fetchWithAuth to issue plugin-management API requests;
// tests inject a mock fetchWithAuth to emulate backend responses.
import { describe, test, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import PluginSidebar from "./PluginSidebar.vue";

// Build a mock fetchWithAuth: returns preset responses keyed by URL
function makeFetch(handlers) {
  return vi.fn(async (url, options = {}) => {
    const method = options.method || "GET";
    const key = `${method} ${url}`;
    const handler = handlers[key] || handlers["default"];
    if (!handler) throw new Error(`No handler for ${key}`);
    return { json: async () => handler() };
  });
}

const plugin = (overrides = {}) => ({
  name: "demo-plugin",
  version: "0.1.0",
  description: "demo plugin",
  dependencies: {
    plugins: { other: ">=1.0" },
    python: { requests: ">=2" },
    commands: ["git"],
  },
  frontend: null,
  ...overrides,
});

const baseProps = {
  fetchWithAuth: vi.fn(),
  gatewayUrl: "127.0.0.1:8000",
  showToast: vi.fn(),
  getHttpProtocol: () => "http",
  availableNodeOptions: [],
};

describe("PluginSidebar", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  test("loads the plugin list automatically on mount and renders it", async () => {
    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/node/master/plugins": () => ({
        success: true,
        data: { node_id: "master", plugins: [plugin()] },
      }),
    });
    const wrapper = mount(PluginSidebar, {
      props: { ...baseProps, fetchWithAuth },
    });
    await flushPromises();
    expect(wrapper.text()).toContain("demo-plugin");
    expect(wrapper.text()).toContain("0.1.0");
    expect(wrapper.text()).toContain("demo plugin");
  });

  test("shows a placeholder when the plugin list is empty", async () => {
    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/node/master/plugins": () => ({
        success: true,
        data: { node_id: "master", plugins: [] },
      }),
    });
    const wrapper = mount(PluginSidebar, {
      props: { ...baseProps, fetchWithAuth },
    });
    await flushPromises();
    expect(wrapper.text()).toContain("No plugins installed on this node");
  });

  test("notifies via showToast when loading fails", async () => {
    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/node/master/plugins": () => ({
        success: false,
        error: { message: "insufficient permissions" },
      }),
    });
    const showToast = vi.fn();
    const wrapper = mount(PluginSidebar, {
      props: { ...baseProps, fetchWithAuth, showToast },
    });
    await flushPromises();
    expect(showToast).toHaveBeenCalledWith("insufficient permissions", "error");
  });

  test("install: fills in the source, calls the install API, and refreshes the list", async () => {
    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/node/master/plugins": () => ({
        success: true,
        data: { node_id: "master", plugins: [] },
      }),
      "POST http://127.0.0.1:8000/api/node/master/plugins/install": () => ({
        success: true,
        data: { node_id: "master", output: [] },
      }),
    });
    const wrapper = mount(PluginSidebar, {
      props: { ...baseProps, fetchWithAuth },
    });
    await flushPromises();
    await wrapper.find(".plugin-install-input").setValue("/tmp/my-plugin");
    await wrapper.find(".plugin-btn-primary").trigger("click");
    await flushPromises();
    // a successful install should call the install API
    const installCall = fetchWithAuth.mock.calls.find(
      ([url, opt]) =>
        opt?.method === "POST" && url.includes("/api/node/master/plugins/install"),
    );
    expect(installCall).toBeTruthy();
    const body = JSON.parse(installCall[1].body);
    expect(body.source).toBe("/tmp/my-plugin");
    expect(body.force).toBe(false);
  });

  test("uninstall: calls the uninstall API after confirmation", async () => {
    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/node/master/plugins": () => ({
        success: true,
        data: { node_id: "master", plugins: [plugin()] },
      }),
      "POST http://127.0.0.1:8000/api/node/master/plugins/demo-plugin/uninstall": () => ({
        success: true,
        data: { node_id: "master", output: [] },
      }),
    });
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const wrapper = mount(PluginSidebar, {
      props: { ...baseProps, fetchWithAuth },
    });
    await flushPromises();
    await wrapper.findAll(".plugin-btn-danger")[0].trigger("click");
    await flushPromises();
    const uninstallCall = fetchWithAuth.mock.calls.find(
      ([url, opt]) => opt?.method === "POST" && url.includes("/uninstall"),
    );
    expect(uninstallCall).toBeTruthy();
    expect(uninstallCall[0]).toContain("/api/node/master/plugins/demo-plugin/uninstall");
    confirmSpy.mockRestore();
  });

  test("upgrade: calls the upgrade API after confirmation", async () => {
    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/node/master/plugins": () => ({
        success: true,
        data: { node_id: "master", plugins: [plugin()] },
      }),
      "POST http://127.0.0.1:8000/api/node/master/plugins/demo-plugin/upgrade": () => ({
        success: true,
        data: { node_id: "master", output: [] },
      }),
    });
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const wrapper = mount(PluginSidebar, {
      props: { ...baseProps, fetchWithAuth },
    });
    await flushPromises();
    await wrapper
      .find(".plugin-btn-sm:not(.plugin-btn-danger)")
      .trigger("click");
    await flushPromises();
    const upgradeCall = fetchWithAuth.mock.calls.find(
      ([url, opt]) => opt?.method === "POST" && url.includes("/upgrade"),
    );
    expect(upgradeCall).toBeTruthy();
    expect(upgradeCall[0]).toContain("/api/node/master/plugins/demo-plugin/upgrade");
    confirmSpy.mockRestore();
  });

  test("built-in plugins show no upgrade/uninstall buttons and display the built-in badge", async () => {
    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/node/master/plugins": () => ({
        success: true,
        data: {
          node_id: "master",
          plugins: [plugin({ name: "builtin-p", builtin: true })],
        },
      }),
    });
    const wrapper = mount(PluginSidebar, {
      props: { ...baseProps, fetchWithAuth },
    });
    await flushPromises();
    expect(wrapper.text()).toContain("Built-in");
    expect(wrapper.find(".plugin-item-actions").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Upgrade");
    expect(wrapper.text()).not.toContain("Uninstall");
  });

  test("capabilities are not shown in the list; the context menu opens the capability-detail modal", async () => {
    const fetchWithAuth = makeFetch({
      "GET http://127.0.0.1:8000/api/node/master/plugins": () => ({
        success: true,
        data: {
          node_id: "master",
          plugins: [
            plugin({
              capabilities: [
                { name: "event hook on_task_start", description: "triggered when a task starts" },
                { name: "@mycmd", description: "built-in command" },
              ],
            }),
          ],
        },
      }),
    });
    const wrapper = mount(PluginSidebar, {
      props: { ...baseProps, fetchWithAuth },
    });
    await flushPromises();
    // capabilities must not take up list space (capability text is not rendered in items)
    expect(wrapper.find(".plugin-item-capabilities").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("event hook on_task_start");
    expect(wrapper.text()).not.toContain("@mycmd");
    // the context menu is not rendered initially
    expect(wrapper.find(".plugin-cap-menu").exists()).toBe(false);
    // right-clicking a plugin item shows the context menu
    await wrapper.find(".plugin-item").trigger("contextmenu");
    expect(wrapper.find(".plugin-cap-menu").exists()).toBe(true);
    expect(wrapper.text()).toContain("Capability Details");
    // clicking "Capability Details" opens the modal with all capabilities
    await wrapper.find(".plugin-cap-menu-item").trigger("click");
    expect(wrapper.find(".cap-modal").exists()).toBe(true);
    expect(wrapper.text()).toContain("event hook on_task_start");
    expect(wrapper.text()).toContain("triggered when a task starts");
    expect(wrapper.text()).toContain("@mycmd");
    expect(wrapper.text()).toContain("built-in command");
  });
});
