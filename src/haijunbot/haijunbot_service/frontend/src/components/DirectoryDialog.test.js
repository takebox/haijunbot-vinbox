// DirectoryDialog component unit tests (vitest + @vue/test-utils + jsdom).
//
// How to run (from the frontend directory):
//   npx vitest run src/components/DirectoryDialog.test.js   # run only this file
//   npm run test:vitest                                     # run all vitest cases
//
// Note: DirectoryDialog is a pure presentational component — it renders from
// props and notifies interactions through emits, making no requests of its own,
// so it can be tested by mounting it directly without mocking the network.
import { describe, test, expect } from "vitest";
import { mount } from "@vue/test-utils";
import DirectoryDialog from "./DirectoryDialog.vue";

// Build a directory item
const dir = (name, path) => ({ name, path });

// Default mount props: visible + one directory
function mountDialog(props = {}) {
  return mount(DirectoryDialog, {
    props: {
      visible: true,
      currentPath: "/home/user",
      filteredDirs: [dir("proj", "/home/user/proj")],
      ...props,
    },
  });
}

describe("DirectoryDialog rendering", () => {
  test("renders nothing when visible=false", () => {
    const wrapper = mountDialog({ visible: false });
    expect(wrapper.find(".palette-overlay").exists()).toBe(false);
    expect(wrapper.find(".dir-modal").exists()).toBe(false);
  });

  test("renders the overlay, title and current path when visible=true", () => {
    const wrapper = mountDialog({ title: "Select Working Directory" });
    expect(wrapper.find(".palette-overlay").exists()).toBe(true);
    expect(wrapper.find(".dir-modal-header h2").text()).toBe("Select Working Directory");
    expect(wrapper.find(".current-path").text()).toBe("/home/user");
  });

  test("title defaults to \"Select Working Directory\"", () => {
    const wrapper = mountDialog();
    expect(wrapper.find(".dir-modal-header h2").text()).toBe("Select Working Directory");
  });

  test("renders directory items (icon/name/path)", () => {
    const wrapper = mountDialog({
      filteredDirs: [dir("a", "/p/a"), dir("b", "/p/b")],
    });
    const items = wrapper.findAll(".dir-item");
    expect(items).toHaveLength(2);
    expect(items[0].find(".dir-name").text()).toBe("a");
    expect(items[0].find(".dir-path").text()).toBe("/p/a");
    expect(items[0].find(".dir-icon svg").exists()).toBe(true);
  });

  test("the directory item matching selectedDir gets the selected class", () => {
    const wrapper = mountDialog({
      filteredDirs: [dir("a", "/p/a"), dir("b", "/p/b")],
      selectedDir: "/p/b",
    });
    const items = wrapper.findAll(".dir-item");
    expect(items[0].classes()).not.toContain("selected");
    expect(items[1].classes()).toContain("selected");
  });

  test("searchText is echoed into the search box", () => {
    const wrapper = mountDialog({ searchText: "proj" });
    expect(wrapper.find(".dir-search-input").element.value).toBe("proj");
  });
});

describe("DirectoryDialog empty state", () => {
  test("non-file mode: shows \"No subdirectories in this directory\" when there are no directories", () => {
    const wrapper = mountDialog({ filteredDirs: [] });
    expect(wrapper.find(".dir-list").exists()).toBe(false);
    expect(wrapper.find(".empty-state p").text()).toBe("No subdirectories in this directory");
  });

  test("file mode: shows \"No subdirectories or files in this directory\" when both are empty", () => {
    const wrapper = mountDialog({
      filteredDirs: [],
      fileSelectable: true,
      fileList: [],
    });
    expect(wrapper.find(".empty-state p").text()).toBe(
      "No subdirectories or files in this directory",
    );
  });
});

describe("DirectoryDialog file-selection mode", () => {
  test("renders no file items when fileSelectable=false (even with a fileList)", () => {
    const wrapper = mountDialog({
      fileSelectable: false,
      fileList: [{ name: "a.yaml", path: "/p/a.yaml" }],
    });
    expect(wrapper.findAll(".file-item")).toHaveLength(0);
  });

  test("renders file items when fileSelectable=true, using the default file icon", () => {
    const wrapper = mountDialog({
      fileSelectable: true,
      fileList: [
        { name: "a.yaml", path: "/p/a.yaml" },
        { name: "b.yml", path: "/p/b.yml" },
      ],
    });
    const files = wrapper.findAll(".file-item");
    expect(files).toHaveLength(2);
    expect(files[0].find(".dir-name").text()).toBe("a.yaml");
    expect(files[0].find(".dir-icon svg").exists()).toBe(true);
  });

  test("fileIcon customizes the file-item icon", () => {
    const wrapper = mountDialog({
      fileSelectable: true,
      fileIcon: "📃",
      fileList: [{ name: "a.yaml", path: "/p/a.yaml" }],
    });
    expect(wrapper.find(".file-item .dir-icon").text()).toBe("📃");
  });

  test("the file item matching selectedFile gets the selected class", () => {
    const wrapper = mountDialog({
      fileSelectable: true,
      selectedFile: "/p/b.yml",
      fileList: [
        { name: "a.yaml", path: "/p/a.yaml" },
        { name: "b.yml", path: "/p/b.yml" },
      ],
    });
    const files = wrapper.findAll(".file-item");
    expect(files[0].classes()).not.toContain("selected");
    expect(files[1].classes()).toContain("selected");
  });

  test("still renders the list when only files exist (no empty state)", () => {
    const wrapper = mountDialog({
      filteredDirs: [],
      fileSelectable: true,
      fileList: [{ name: "a.yaml", path: "/p/a.yaml" }],
    });
    expect(wrapper.find(".dir-list").exists()).toBe(true);
    expect(wrapper.find(".empty-state").exists()).toBe(false);
  });
});

describe("DirectoryDialog interaction emits", () => {
  test("clicking a directory item emits select and enter", async () => {
    const wrapper = mountDialog({
      filteredDirs: [dir("proj", "/home/user/proj")],
    });
    await wrapper.find(".dir-item").trigger("click");
    expect(wrapper.emitted("select")).toBeTruthy();
    expect(wrapper.emitted("select")[0]).toEqual(["/home/user/proj"]);
    expect(wrapper.emitted("enter")).toBeTruthy();
    expect(wrapper.emitted("enter")[0]).toEqual(["/home/user/proj", false]);
  });

  test("clicking a file item emits select-file", async () => {
    const wrapper = mountDialog({
      fileSelectable: true,
      fileList: [{ name: "a.yaml", path: "/p/a.yaml" }],
    });
    await wrapper.find(".file-item").trigger("click");
    expect(wrapper.emitted("select-file")).toBeTruthy();
    expect(wrapper.emitted("select-file")[0]).toEqual(["/p/a.yaml"]);
  });

  test("typing in the search box emits update:searchText", async () => {
    const wrapper = mountDialog();
    const input = wrapper.find(".dir-search-input");
    await input.setValue("abc");
    expect(wrapper.emitted("update:searchText")).toBeTruthy();
    expect(wrapper.emitted("update:searchText")[0]).toEqual(["abc"]);
  });

  test("pressing a key in the search box emits search-keydown", async () => {
    const wrapper = mountDialog();
    await wrapper
      .find(".dir-search-input")
      .trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("search-keydown")).toBeTruthy();
  });

  test("the refresh and up buttons emit refresh / go-parent", async () => {
    const wrapper = mountDialog();
    const btns = wrapper.findAll(".path-btn");
    await btns[0].trigger("click");
    await btns[1].trigger("click");
    expect(wrapper.emitted("refresh")[0]).toEqual(["/home/user"]);
    expect(wrapper.emitted("go-parent")).toBeTruthy();
  });

  test("non-embedded: cancel/confirm/close buttons emit cancel / confirm", async () => {
    const wrapper = mountDialog();
    await wrapper.find(".dir-close-btn").trigger("click");
    const actionBtns = wrapper.findAll(".dir-modal-actions .btn");
    await actionBtns[0].trigger("click"); // cancel
    await actionBtns[1].trigger("click"); // confirm
    expect(wrapper.emitted("cancel")).toHaveLength(2);
    expect(wrapper.emitted("confirm")).toHaveLength(1);
  });
});

describe("DirectoryDialog embedded mode", () => {
  test("embedded=true renders no overlay, title bar or bottom buttons", () => {
    const wrapper = mountDialog({ embedded: true });
    expect(wrapper.find(".palette-overlay").exists()).toBe(false);
    expect(wrapper.find(".dir-modal-embedded").exists()).toBe(true);
    expect(wrapper.find(".dir-modal-header").exists()).toBe(false);
    expect(wrapper.find(".dir-modal-actions").exists()).toBe(false);
  });

  test("embedded=true still renders path/search/list", () => {
    const wrapper = mountDialog({ embedded: true });
    expect(wrapper.find(".current-path").text()).toBe("/home/user");
    expect(wrapper.find(".dir-search-input").exists()).toBe(true);
    expect(wrapper.find(".dir-item").exists()).toBe(true);
  });
});
