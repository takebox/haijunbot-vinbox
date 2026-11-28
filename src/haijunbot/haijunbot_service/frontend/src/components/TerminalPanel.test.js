// TerminalPanel component unit tests (vitest + @vue/test-utils + jsdom).
//
// How to run (in frontend directory):
//   npx vitest run src/components/TerminalPanel.test.js   # Run only this file
//   npm run test:vitest                                   # Run all vitest tests
//
// Note: TerminalPanel is a pure display component—rendered by props, notifies
// interactions via emit. This test focuses on the "restore session" scenario:
// as long as sessions has entries, the tab bar and content area hostEl should
// render and trigger setHostRef event, which is the prerequisite for
// setTerminalHostRef → initIndependentTerminal to initialize xterm in App.vue
// (regression protection for the "after re-login, tabs visible but xterm missing" bug).
import { describe, test, expect } from "vitest";
import { mount } from "@vue/test-utils";
import TerminalPanel from "./TerminalPanel.vue";

// Construct a session
const session = (terminalId, overrides = {}) => ({
  terminal_id: terminalId,
  interpreter: "bash",
  access: "owner",
  ...overrides,
});

function mountPanel(props = {}) {
  return mount(TerminalPanel, {
    props: {
      visible: true,
      active: false,
      embedded: true,
      interaction: {},
      panelStyle: {},
      nodeOptions: [],
      selectedNodeId: "",
      socket: null,
      sessions: [],
      activeId: "",
      resizeDirections: [],
      formatNodeLabel: (n) => n.label || n.node_id,
      ...props,
    },
  });
}

describe("TerminalPanel restore session rendering", () => {
  test("When sessions is empty, shows empty state and does not trigger setHostRef", () => {
    const wrapper = mountPanel();
    expect(wrapper.find(".terminal-empty").exists()).toBe(true);
    expect(wrapper.emitted("setHostRef")).toBeUndefined();
  });

  test("Renders tabs when sessions has data", () => {
    const wrapper = mountPanel({
      sessions: [session("t1"), session("t2")],
      activeId: "t1",
    });
    const tabs = wrapper.findAll(".terminal-tab");
    expect(tabs.length).toBe(2);
    expect(tabs[0].text()).toContain("bash");
  });

  test("Content area hostEl renders and triggers setHostRef when sessions has data (el is non-null)", () => {
    const wrapper = mountPanel({
      sessions: [session("t1")],
      activeId: "t1",
    });
    // Content area host container renders
    expect(wrapper.findAll(".terminal-host").length).toBe(1);
    // Triggers setHostRef, and el is a real DOM element (non-null)
    const emitted = wrapper.emitted("setHostRef");
    expect(emitted).toBeTruthy();
    const [terminalId, el] = emitted[0];
    expect(terminalId).toBe("t1");
    expect(el).toBeTruthy();
    expect(el.nodeType).toBe(1); // ELEMENT_NODE
  });

  test("Multiple sessions each trigger setHostRef once, and non-active session hostEl also renders (v-show hidden still renders)", () => {
    const wrapper = mountPanel({
      sessions: [session("t1"), session("t2")],
      activeId: "t1",
    });
    const emitted = wrapper.emitted("setHostRef");
    expect(emitted).toBeTruthy();
    const ids = emitted.map((e) => e[0]);
    expect(ids).toContain("t1");
    expect(ids).toContain("t2");
    // Content area host container count = session count (v-show only hides, does not destroy)
    expect(wrapper.findAll(".terminal-host").length).toBe(2);
  });

  test("Owner session shows share and close buttons, read session shows read-only badge", () => {
    const wrapper = mountPanel({
      sessions: [session("t1"), session("t2", { access: "read" })],
      activeId: "t1",
    });
    expect(wrapper.find(".terminal-tab-share").exists()).toBe(true);
    expect(wrapper.find(".terminal-tab-close").exists()).toBe(true);
    const readTab = wrapper.findAll(".terminal-tab")[1];
    expect(readTab.classes()).toContain("terminal-tab-readonly");
    expect(readTab.find(".terminal-tab-badge").exists()).toBe(true);
  });

  test("Sync button exists, clicking triggers syncTerminals event (restore all accessible terminals)", () => {
    const wrapper = mountPanel({ socket: {} });
    // Sync button is in the terminal panel action area
    const syncBtn = wrapper
      .findAll(".terminal-create-btn")
      .find((b) => b.text() === "🔄");
    expect(syncBtn).toBeTruthy();
    syncBtn.trigger("click");
    const emitted = wrapper.emitted("syncTerminals");
    expect(emitted).toBeTruthy();
    expect(emitted.length).toBe(1);
  });
});
