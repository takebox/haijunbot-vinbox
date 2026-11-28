// currentAgentResolver unit tests (zero dependencies, using node's built-in test runner).
//
// How to run (from the frontend directory):
//   node --test src/utils/currentAgentResolver.test.mjs   # run only this file
//   npm run test:node                                      # run all *.test.mjs
//
// Background: the "Current Agent" group actions in the command palette / context
// menu all rely on resolveCurrentAgentId to locate their target. There was once a
// bug where "context menu visible" was also treated as a lock condition, so after
// clicking a menu item (the menu collapses first) the lock dropped and fell back
// to the active Agent, applying delete/rename to the wrong object. The regression
// cases below pin down that behavior.
import { test } from "node:test";
import assert from "node:assert/strict";
import { resolveCurrentAgentId } from "./currentAgentResolver.js";

test("returns null when there is no state at all", () => {
  assert.equal(resolveCurrentAgentId({}), null);
  assert.equal(resolveCurrentAgentId(), null);
});

test("the context-menu-locked Agent has the highest priority (overrides all other state)", () => {
  const id = resolveCurrentAgentId({
    contextMenuAgentId: "right-clicked",
    lobbyActiveAgentId: "lobby",
    hasNoPanel: true,
    activePanelAgentId: "active-panel",
    currentAgentId: "current",
  });
  assert.equal(id, "right-clicked");
});

test("regression: the context-menu lock does not depend on menu visibility — contextMenuAgentId alone takes effect", () => {
  // When a menu item is clicked, the menu collapses first (visible=false); the
  // resolution must not fall back to the active Agent because of that.
  // Without any "menu visible" field passed here, the lock must still hold.
  const id = resolveCurrentAgentId({
    contextMenuAgentId: "right-clicked",
    activePanelAgentId: "active-panel",
    currentAgentId: "current",
  });
  assert.equal(id, "right-clicked");
});

test("regression: the context-menu lock outranks the active Panel (delete targets the right-clicked Agent)", () => {
  // Scenario: the active Panel is agent-B, but the user right-clicked agent-A in the sidebar and clicked delete.
  const id = resolveCurrentAgentId({
    contextMenuAgentId: "agent-A",
    activePanelAgentId: "agent-B",
    currentAgentId: "agent-B",
  });
  assert.equal(id, "agent-A");
});

test("pure lobby state (no panels): the lobby-selected pet wins", () => {
  const id = resolveCurrentAgentId({
    hasNoPanel: true,
    lobbyActiveAgentId: "lobby-pet",
    activePanelAgentId: "active-panel",
    currentAgentId: "current",
  });
  assert.equal(id, "lobby-pet");
});

test("with panels: hasNoPanel=false disables lobby priority and uses the active Panel instead", () => {
  const id = resolveCurrentAgentId({
    hasNoPanel: false,
    lobbyActiveAgentId: "lobby-pet",
    activePanelAgentId: "active-panel",
    currentAgentId: "current",
  });
  assert.equal(id, "active-panel");
});

test("falls back to the lobby-selected pet when no Panel is active", () => {
  const id = resolveCurrentAgentId({
    hasNoPanel: false,
    lobbyActiveAgentId: "lobby-pet",
    activePanelAgentId: null,
    currentAgentId: "current",
  });
  assert.equal(id, "lobby-pet");
});

test("uses currentAgentId as a fallback when it is all that exists", () => {
  const id = resolveCurrentAgentId({
    currentAgentId: "current",
  });
  assert.equal(id, "current");
});

test("contextMenuAgentId of null/empty string is treated as unlocked", () => {
  assert.equal(
    resolveCurrentAgentId({
      contextMenuAgentId: null,
      currentAgentId: "current",
    }),
    "current",
  );
  assert.equal(
    resolveCurrentAgentId({
      contextMenuAgentId: "",
      currentAgentId: "current",
    }),
    "current",
  );
});

test("an empty lobbyActiveAgentId does not take part in resolution", () => {
  const id = resolveCurrentAgentId({
    hasNoPanel: true,
    lobbyActiveAgentId: "",
    currentAgentId: "current",
  });
  assert.equal(id, "current");
});
