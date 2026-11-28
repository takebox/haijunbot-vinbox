// Component unit tests for ManageSidebar (vitest + @vue/test-utils + jsdom).
//
// How to run (from the frontend directory):
//   npx vitest run src/components/ManageSidebar.test.js   # run only this file
//   npm run test:vitest                                   # run all vitest cases
//
// Note: ManageSidebar is a pure display component — it renders from props, makes no
// requests of its own, and performs no writes, so it can be tested with a direct mount,
// no network mocking needed.
import { describe, test, expect } from "vitest";
import { mount } from "@vue/test-utils";
import ManageSidebar from "./ManageSidebar.vue";

// Build a scheduled task
function timer(overrides = {}) {
  return {
    task_id: "task-12345678",
    run_at: "2026-10-02T12:00:00",
    interval_seconds: null,
    is_recurring: false,
    cancelled: false,
    metadata: {
      action: { type: "capability_call", params: { name: "system.info" } },
      schedule: { type: "run_at", run_at: "2026-10-02T12:00:00" },
    },
    ...overrides,
  };
}

// Build a daemon session
function session(overrides = {}) {
  return {
    session_id: "sess-abc",
    name: "my-pc",
    hostname: "my-pc",
    platform: "windows",
    daemon_version: "v6.0.1",
    capabilities: [
      {
        name: "system.info",
        description: "Query system info",
        parameters: { type: "object", properties: {} },
        platform: "any",
      },
    ],
    ...overrides,
  };
}

// Build a browser extension session
function extensionSession(overrides = {}) {
  return {
    session_id: "ext-xyz",
    name: "Chrome Extension",
    extension_version: "v1.2.3",
    browser_info: { name: "Chrome", version: "120", os: "Windows" },
    tabs: [{ tab_id: 1, title: "Example page", url: "https://example.com" }],
    capabilities: [
      {
        name: "script.execute",
        description: "Execute arbitrary JS in the page (main world)",
        parameters: { code: "string" },
        platform: "browser",
      },
      {
        name: "tab.create",
        description: "New tab",
        parameters: { url: "string" },
        platform: "browser",
      },
    ],
    ...overrides,
  };
}

function mountSidebar(props = {}) {
  return mount(ManageSidebar, {
    props: {
      view: "manage",
      timers: [],
      daemonSessions: [],
      extensionSessions: [],
      installedScripts: [],
      gatewayScripts: [],
      ...props,
    },
  });
}

describe("ManageSidebar scheduled-task display (view=timers)", () => {
  test("scheduled-task view shows the empty state", () => {
    const wrapper = mountSidebar({ view: "timers" });
    expect(wrapper.find(".manage-sidebar-title").text()).toBe("Scheduled Tasks");
    expect(wrapper.find(".manage-sidebar-empty").text()).toContain(
      "No scheduled tasks",
    );
  });

  test("scheduled-task view does not show the refresh button", () => {
    const wrapper = mountSidebar({ view: "timers" });
    expect(wrapper.find(".manage-sidebar-refresh").exists()).toBe(false);
  });

  test("renders the scheduled-task list (action type/status/schedule)", () => {
    const wrapper = mountSidebar({ view: "timers", timers: [timer()] });
    expect(wrapper.find(".manage-timer-item").exists()).toBe(true);
    expect(wrapper.find(".manage-timer-type").text()).toBe("Call Capability");
    expect(wrapper.find(".manage-timer-status").text()).toBe("Running");
    expect(wrapper.find(".manage-timer-schedule").text()).toContain("Scheduled");
  });

  test("cancelled tasks show the cancelled status", () => {
    const wrapper = mountSidebar({
      view: "timers",
      timers: [timer({ cancelled: true })],
    });
    expect(wrapper.find(".manage-timer-status").text()).toBe("Cancelled");
    expect(wrapper.find(".manage-timer-status").classes()).toContain(
      "cancelled",
    );
  });

  test("cron schedules render the cron expression", () => {
    const wrapper = mountSidebar({
      view: "timers",
      timers: [
        timer({
          metadata: {
            action: { type: "capability_call" },
            schedule: { type: "cron", cron: "0 9 * * 1" },
          },
        }),
      ],
    });
    expect(wrapper.find(".manage-timer-schedule").text()).toContain(
      "cron: 0 9 * * 1",
    );
  });

  test("unknown action types display the raw type", () => {
    const wrapper = mountSidebar({
      view: "timers",
      timers: [timer({ metadata: { action: { type: "custom_action" } } })],
    });
    expect(wrapper.find(".manage-timer-type").text()).toBe("custom_action");
  });
});

describe("ManageSidebar capability-list display (view=manage)", () => {
  test("capability-list view title and refresh button", () => {
    const wrapper = mountSidebar();
    expect(wrapper.find(".manage-sidebar-title").text()).toBe("Capability List");
    expect(wrapper.find(".manage-sidebar-refresh").exists()).toBe(true);
  });

  test("shows a message when no capabilities are available", () => {
    const wrapper = mountSidebar();
    expect(wrapper.find(".manage-sidebar-empty").text()).toContain(
      "No available capabilities",
    );
  });

  test("clicking the refresh button emits the refresh event", async () => {
    const wrapper = mountSidebar({ daemonSessions: [session()] });
    await wrapper.find(".manage-sidebar-refresh").trigger("click");
    expect(wrapper.emitted("refresh")).toBeTruthy();
  });

  test("shows daemon sessions and capabilities", async () => {
    const wrapper = mountSidebar({ daemonSessions: [session()] });
    expect(wrapper.find(".manage-section-title").text()).toBe("Daemon Capabilities");
    expect(wrapper.find(".manage-session-name").text()).toBe("my-pc");
    // After expanding the session, the capability list is visible
    await wrapper.find(".manage-session-head").trigger("click");
    expect(wrapper.find(".manage-capability-name").text()).toBe("system.info");
  });

  test("expanding a daemon session shows capability details (description and parameters)", async () => {
    const wrapper = mountSidebar({ daemonSessions: [session()] });
    // Expand the session
    await wrapper.find(".manage-session-head").trigger("click");
    // After expanding the capability, description and parameters are visible
    await wrapper.find(".manage-capability-head").trigger("click");
    expect(wrapper.find(".manage-capability-desc").text()).toContain(
      "Query system info",
    );
    expect(wrapper.find(".manage-capability-params-json").exists()).toBe(true);
  });

  test("shows browser extension sessions and their capability list", async () => {
    const wrapper = mountSidebar({ extensionSessions: [extensionSession()] });
    expect(wrapper.find(".manage-section-title").text()).toBe("Browser Extension");
    expect(wrapper.find(".manage-session-name").text()).toBe("Chrome Extension");
    // After expanding the extension session, the browser info and capability list are visible
    await wrapper.find(".manage-session-head").trigger("click");
    expect(wrapper.find(".manage-capability-desc").text()).toContain("Chrome");
    expect(wrapper.find(".manage-capability-name").text()).toBe(
      "script.execute",
    );
  });

  test("expanding a browser extension capability shows details (description and parameters)", async () => {
    const wrapper = mountSidebar({ extensionSessions: [extensionSession()] });
    await wrapper.find(".manage-session-head").trigger("click");
    await wrapper.find(".manage-capability-head").trigger("click");
    expect(
      wrapper.find(".manage-capability-body .manage-capability-desc").text(),
    ).toContain("Execute arbitrary JS in the page");
    expect(wrapper.find(".manage-capability-params-json").exists()).toBe(true);
  });

test("expanded browser extension sessions show installed scripts", async () => {
    const wrapper = mountSidebar({
      extensionSessions: [extensionSession()],
      installedScripts: [
        {
          session_id: "ext-xyz",
          name: "Chrome Extension",
          scripts: [
            {
              id: "s-1",
              name: "mysite",
              description: "Site document operations",
              version: "1.0.0",
              enabled: true,
              match: ["https://example.com/*"],
            },
          ],
        },
      ],
    });
    await wrapper.find(".manage-session-head").trigger("click");
    expect(wrapper.find(".manage-script-name").text()).toBe("mysite");
    expect(wrapper.find(".manage-script-desc").text()).toContain(
      "Site document operations",
    );
    expect(wrapper.find(".manage-script-status").text()).toBe("Enabled");
  });

  test("shows the gateway script library", () => {
    const wrapper = mountSidebar({
      gatewayScripts: [
        { name: "backup", size: 2048, updated_at: "2026-10-02T00:00:00" },
      ],
    });
    expect(wrapper.find(".manage-section-title").text()).toBe("Gateway Script Library");
    expect(wrapper.find(".manage-script-name").text()).toBe("backup");
    expect(wrapper.find(".manage-script-status").text()).toBe("2.0 KB");
  });
});
