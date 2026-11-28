// AboutModal component unit tests (vitest + @vue/test-utils + jsdom).
//
// How to run (in frontend directory):
//   npx vitest run src/components/AboutModal.test.js   # Run only this file
//   npm run test:vitest                                 # Run all vitest tests
//
// Note: AboutModal is a pure display component—rendered by props, notifies
// close via emit, and does not make requests itself, so it can be mounted
// directly for testing without mocking the network.
import { describe, test, expect } from "vitest";
import { mount } from "@vue/test-utils";
import AboutModal from "./AboutModal.vue";

const baseProps = {
  visible: true,
  frontendVersion: "6.0.7",
  backendVersion: "6.0.7",
  nodes: [{ node_id: "master", status: "online", version: "6.0.7" }],
  daemonSessions: [
    {
      session_id: "s1",
      name: "skyfire-pc",
      platform: "windows",
      daemon_version: "6.0.7",
    },
  ],
  browserExtSessions: [
    {
      session_id: "e1",
      name: "Edge",
      extension_version: "6.0.7",
      browser_info: { name: "Edge" },
    },
  ],
};

function mountAbout(props = {}) {
  return mount(AboutModal, {
    props: { ...baseProps, ...props },
  });
}

describe("AboutModal rendering", () => {
  test("Does not render content when visible=false", () => {
    const wrapper = mountAbout({ visible: false });
    expect(wrapper.find(".modal-overlay").exists()).toBe(false);
  });

  test("Renders title and software info when visible=true", () => {
    const wrapper = mountAbout();
    expect(wrapper.find(".modal-overlay").exists()).toBe(true);
    expect(wrapper.find(".modal-header h2").text()).toBe("About");
    expect(wrapper.find(".about-title").text()).toBe("HaijunBot Web Gateway");
    expect(wrapper.find(".about-subtitle").text()).toContain("6.0.7");
  });

  test("Displays MIT license and author skyfire", () => {
    const wrapper = mountAbout();
    const tags = wrapper.findAll(".about-tag").map((t) => t.text());
    expect(tags).toContain("MIT License");
    expect(tags).toContain("Author: skyfire");
  });

  test("Displays node versions", () => {
    const wrapper = mountAbout();
    const item = wrapper.find(".about-item");
    expect(item.text()).toContain("master");
    expect(item.text()).toContain("6.0.7");
  });

  test("Displays daemon versions", () => {
    const wrapper = mountAbout();
    const text = wrapper.text();
    expect(text).toContain("skyfire-pc");
    expect(text).toContain("windows");
  });

  test("Displays browser extension versions", () => {
    const wrapper = mountAbout();
    const text = wrapper.text();
    expect(text).toContain("Edge");
    expect(text).toContain("6.0.7");
  });

  test("Shows empty state when no data", () => {
    const wrapper = mountAbout({
      nodes: [],
      daemonSessions: [],
      browserExtSessions: [],
    });
    const text = wrapper.text();
    expect(text).toContain("No node information");
    expect(text).toContain("No online daemons");
    expect(text).toContain("No online browser extensions");
  });

  test("Clicking close button emits update:visible false", () => {
    const wrapper = mountAbout();
    wrapper.find(".close-btn").trigger("click");
    expect(wrapper.emitted("update:visible")).toBeTruthy();
    expect(wrapper.emitted("update:visible")[0]).toEqual([false]);
  });

  test("Clicking overlay blank area closes", () => {
    const wrapper = mountAbout();
    wrapper.find(".modal-overlay").trigger("click");
    expect(wrapper.emitted("update:visible")).toBeTruthy();
    expect(wrapper.emitted("update:visible")[0]).toEqual([false]);
  });
});
