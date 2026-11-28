// Component unit tests for the CommandPalette command palette (vitest + @vue/test-utils + jsdom).
//
// How to run (execute from the frontend directory):
//   npx vitest run src/components/CommandPalette.test.js   # run only this file
//   npm run test:vitest                                    # run all vitest cases
//
// Notes: CommandPalette is a controlled component - props.visible controls visibility and props.ctx provides
// external capabilities (Agent list / file search results / search callbacks) and notifies the outside via emit. Tests
// just mount it and pass a ctx stub; no network mocking is needed. Recently used is persisted to localStorage,
// jsdom is available, and it is cleared before each test case.
import { describe, test, expect, beforeEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import CommandPalette from "./CommandPalette.vue";

// Build a command action object (filterActions depends on fields like id/label/group/icon/run)
function action(overrides = {}) {
  return {
    id: "cmd-1",
    label: "Test Command",
    icon: "🧪",
    group: "Test",
    run: () => {},
    ...overrides,
  };
}

// Build a ctx stub: provides an empty Agent list and empty file results by default; overridable
function makeCtx(overrides = {}) {
  return {
    agentList: [],
    openedAgentIds: new Set(),
    fileSearchResults: [],
    fileSearchLoading: false,
    fileSearchError: "",
    getAgentNodeLabel: () => "",
    getStatusClass: () => "running",
    searchWorkspaceFiles: () => {},
    clearWorkspaceFileSearch: () => {},
    ...overrides,
  };
}

// Default mount props: visible=true + a set of actions + ctx stub
function mountPalette(props = {}) {
  return mount(CommandPalette, {
    props: {
      visible: true,
      actions: [action()],
      ctx: makeCtx(),
      title: "Search commands…",
      initialQuery: "",
      ...props,
    },
  });
}

beforeEach(() => {
  localStorage.clear();
});

describe("Prefix detection and placeholders", () => {
  test("a normal query uses command mode and the placeholder uses props.title", () => {
    const wrapper = mountPalette();
    expect(wrapper.find(".cmd-input").attributes("placeholder")).toBe(
      "Search commands…",
    );
  });

  test("initialQuery='f>' enters file mode, placeholder is \"Search files…\"", () => {
    const wrapper = mountPalette({ initialQuery: "f>" });
    expect(wrapper.find(".cmd-input").attributes("placeholder")).toBe(
      "Search files…",
    );
  });

  test("initialQuery='a>' enters Agent mode, placeholder is \"Search Agents…\"", () => {
    const wrapper = mountPalette({ initialQuery: "a>" });
    expect(wrapper.find(".cmd-input").attributes("placeholder")).toBe(
      "Search Agents…",
    );
  });
});

describe("File mode rendering", () => {
  test("renders file entries when fileSearchResults is provided (label=name, meta=file_path)", () => {
    const wrapper = mountPalette({
      initialQuery: "f>",
      ctx: makeCtx({
        fileSearchResults: [
          { name: "setup.py", file_path: "/home/user/setup.py" },
        ],
      }),
    });
    const items = wrapper.findAll(".cmd-item");
    expect(items).toHaveLength(1);
    expect(items[0].find(".cmd-item-title").text()).toBe("setup.py");
    expect(items[0].find(".cmd-item-meta").text()).toBe("/home/user/setup.py");
  });

  test("empty state is \"Searching…\" when fileSearchLoading", () => {
    const wrapper = mountPalette({
      initialQuery: "f>",
      ctx: makeCtx({ fileSearchLoading: true }),
    });
    expect(wrapper.find(".cmd-empty").text()).toBe("Searching…");
  });

  test("empty state is the error text when fileSearchError", () => {
    const wrapper = mountPalette({
      initialQuery: "f>",
      ctx: makeCtx({ fileSearchError: "Search failed" }),
    });
    expect(wrapper.find(".cmd-empty").text()).toBe("Search failed");
  });

  test("empty state is \"No matching files\" when there is a query but no match", () => {
    const wrapper = mountPalette({
      initialQuery: "f>abc",
      ctx: makeCtx({ fileSearchResults: [] }),
    });
    expect(wrapper.find(".cmd-empty").text()).toBe("No matching files");
  });

  test("empty state in file mode without a query is \"Type a file name to search the current Agent workspace\"", () => {
    const wrapper = mountPalette({
      initialQuery: "f>",
      ctx: makeCtx({ fileSearchResults: [] }),
    });
    expect(wrapper.find(".cmd-empty").text()).toBe(
      "Type a file name to search the current Agent workspace",
    );
  });
});

describe("Agent mode rendering and sorting", () => {
  const agents = [
    { agent_id: "a1", name: "Running", status: "running" },
    { agent_id: "a2", name: "Stopped", status: "stopped" },
    { agent_id: "a3", name: "Opened", status: "running" },
  ];

  // Note: an Agent entry's .cmd-item-title embeds the en child element (agent_id), so text() concatenates to name+agent_id
  test("renders Agent entries, label from name and en from agent_id", () => {
    const wrapper = mountPalette({
      initialQuery: "a>",
      ctx: makeCtx({ agentList: agents }),
    });
    const items = wrapper.findAll(".cmd-item");
    expect(items).toHaveLength(3);
    expect(items[0].find(".cmd-item-title").text()).toBe("Runninga1");
  });

  test("Running comes before Stopped; opened comes before unopened with the same running state", () => {
    const wrapper = mountPalette({
      initialQuery: "a>",
      ctx: makeCtx({
        agentList: agents,
        openedAgentIds: new Set(["a3"]),
      }),
    });
    // Sorting rules: first by running state (running first), then by opened (opened first).
    // Expected order: a3 (running, opened) / a1 (running, not opened) / a2 (stopped)
    const titles = wrapper.findAll(".cmd-item-title").map((n) => n.text());
    expect(titles).toEqual(["Openeda3", "Runninga1", "Stoppeda2"]);
  });

  test("search terms filter by name/agent_id/nodeLabel", () => {
    const wrapper = mountPalette({
      initialQuery: "a>a2",
      ctx: makeCtx({
        agentList: agents,
        getAgentNodeLabel: (agent) =>
          agent.agent_id === "a1" ? "NodeX" : "NodeY",
      }),
    });
    const titles = wrapper.findAll(".cmd-item-title").map((n) => n.text());
    // Only a2 matches (name contains a2)
    expect(titles).toEqual(["Stoppeda2"]);
  });
});

describe("Recently used", () => {
  test("with no search term, recently used commands are pinned to the \"Recently used\" group", () => {
    localStorage.setItem(
      "haijunbot_cmd_palette_recent",
      JSON.stringify(["cmd-recent"]),
    );
    const wrapper = mountPalette({
      actions: [
        action({ id: "cmd-recent", label: "Recent Command" }),
        action({ id: "cmd-other", label: "Other Command" }),
      ],
    });
    const groupTitles = wrapper
      .findAll(".cmd-group-title")
      .map((n) => n.text());
    expect(groupTitles[0]).toBe("Recently used");
    // The recently used group contains this command, and it does not appear again in the regular list
    const firstGroupItems = wrapper
      .findAll(".cmd-group")[0]
      .findAll(".cmd-item-title")
      .map((n) => n.text());
    expect(firstGroupItems).toContain("Recent Command");
    const allLabels = wrapper.findAll(".cmd-item-title").map((n) => n.text());
    expect(allLabels.filter((l) => l === "Recent Command")).toHaveLength(1);
  });

  test("Recently used is not shown in Agent mode", () => {
    localStorage.setItem(
      "haijunbot_cmd_palette_recent",
      JSON.stringify(["cmd-recent"]),
    );
    const wrapper = mountPalette({
      initialQuery: "a>",
      actions: [action({ id: "cmd-recent", label: "Recent Command" })],
      ctx: makeCtx({ agentList: [] }),
    });
    expect(wrapper.find(".cmd-group-title").exists()).toBe(false);
    expect(wrapper.find(".cmd-empty").exists()).toBe(true);
  });

  test("Recently used is not shown in file mode", () => {
    localStorage.setItem(
      "haijunbot_cmd_palette_recent",
      JSON.stringify(["cmd-recent"]),
    );
    const wrapper = mountPalette({
      initialQuery: "f>",
      actions: [action({ id: "cmd-recent", label: "Recent Command" })],
      ctx: makeCtx({ fileSearchResults: [] }),
    });
    expect(wrapper.find(".cmd-group-title").exists()).toBe(false);
  });
});

describe("Interaction and emit", () => {
  test("clicking an item emits ('run', action, 'current')", async () => {
    const wrapper = mountPalette({ actions: [action({ id: "cmd-1" })] });
    await wrapper.find(".cmd-item").trigger("click");
    expect(wrapper.emitted("run")).toBeTruthy();
    expect(wrapper.emitted("run")[0][0].id).toBe("cmd-1");
    expect(wrapper.emitted("run")[0][1]).toBe("current");
  });

  test("Enter triggers run for the currently selected item", async () => {
    const wrapper = mountPalette({ actions: [action({ id: "cmd-1" })] });
    await wrapper.find(".cmd-input").trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("run")).toBeTruthy();
    expect(wrapper.emitted("run")[0][0].id).toBe("cmd-1");
  });

  test("ArrowDown moves activeIndex and skips disabled items", async () => {
    const wrapper = mountPalette({
      actions: [
        action({ id: "cmd-1", label: "One" }),
        action({ id: "cmd-2", label: "Two", disabled: true }),
        action({ id: "cmd-3", label: "Three" }),
      ],
    });
    // Initial activeIndex=0 (cmd-1)
    await wrapper.find(".cmd-input").trigger("keydown", { key: "ArrowDown" });
    // Skips the disabled cmd-2 and lands on cmd-3
    const active = wrapper.findAll(".cmd-item.is-active");
    expect(active).toHaveLength(1);
    expect(active[0].find(".cmd-item-title").text()).toBe("Three");
  });

  test("ArrowUp moves activeIndex", async () => {
    const wrapper = mountPalette({
      actions: [
        action({ id: "cmd-1", label: "One" }),
        action({ id: "cmd-2", label: "Two" }),
      ],
    });
    // First move down to the last, then move up back to the first
    await wrapper.find(".cmd-input").trigger("keydown", { key: "ArrowDown" });
    await wrapper.find(".cmd-input").trigger("keydown", { key: "ArrowUp" });
    const active = wrapper.findAll(".cmd-item.is-active");
    expect(active[0].find(".cmd-item-title").text()).toBe("One");
  });

  test("Escape emits 'update:visible', false and 'close'", async () => {
    const wrapper = mountPalette();
    await wrapper.find(".cmd-input").trigger("keydown", { key: "Escape" });
    expect(wrapper.emitted("update:visible")).toBeTruthy();
    expect(wrapper.emitted("update:visible")[0]).toEqual([false]);
    expect(wrapper.emitted("close")).toBeTruthy();
  });

  test("clicking a disabled item does not emit run", async () => {
    const wrapper = mountPalette({
      actions: [action({ id: "cmd-1", disabled: true })],
    });
    await wrapper.find(".cmd-item").trigger("click");
    expect(wrapper.emitted("run")).toBeFalsy();
  });
});

describe("File mode search callbacks", () => {
  test("input changes in file mode call ctx.searchWorkspaceFiles(query)", async () => {
    const searchWorkspaceFiles = vi.fn();
    const wrapper = mountPalette({
      initialQuery: "f>",
      ctx: makeCtx({ searchWorkspaceFiles }),
    });
    const input = wrapper.find(".cmd-input");
    await input.setValue("f>setup");
    expect(searchWorkspaceFiles).toHaveBeenCalledWith("setup");
  });

  test("leaving file mode calls ctx.clearWorkspaceFileSearch()", async () => {
    const clearWorkspaceFileSearch = vi.fn();
    const wrapper = mountPalette({
      initialQuery: "f>",
      ctx: makeCtx({ clearWorkspaceFileSearch }),
    });
    const input = wrapper.find(".cmd-input");
    await input.setValue("normal");
    expect(clearWorkspaceFileSearch).toHaveBeenCalled();
  });
});
