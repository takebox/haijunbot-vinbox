// "Current Agent" resolution: the "Current Agent" group actions in the command palette / context menu uniformly use it to locate the target.
//
// Priority (top to bottom, first match wins):
//   1) contextMenuAgentId -- Agent locked by the context menu (sidebar / Panel right-click).
//      Must be first, and must NOT depend on whether the menu is visible: clicking a menu item
//      collapses the menu first, so if "menu visible" were a condition, the lock would be lost
//      and it would fall back to the current active Agent, causing delete/rename etc. to act on
//      the wrong Agent.
//   2) Agent of the pet selected in the pet lobby (no embedded panels);
//   3) Agent inside the currently active Panel;
//   4) Lobby selected pet (fallback);
//   5) currentAgentId (final fallback).
//
// Extracted as a pure function for easy unit testing: input is a snapshot of each state, output is the resolved agentId (null if none).

/**
 * Resolve the current Agent's ID.
 * @param {object} state
 * @param {string|null} [state.contextMenuAgentId] Agent ID locked by the context menu
 * @param {string|null} [state.lobbyActiveAgentId] Agent ID of the pet selected in the lobby
 * @param {boolean} [state.hasNoPanel] whether there are no embedded panels (pure lobby state)
 * @param {string|null} [state.activePanelAgentId] Agent ID inside the currently active Panel
 * @param {string|null} [state.currentAgentId] current Agent (final fallback)
 * @returns {string|null}
 */
export function resolveCurrentAgentId(state = {}) {
  const {
    contextMenuAgentId,
    lobbyActiveAgentId,
    hasNoPanel,
    activePanelAgentId,
    currentAgentId,
  } = state;

  // 1) Context-menu lock takes priority (not dependent on menu visibility)
  if (contextMenuAgentId) return contextMenuAgentId;
  // 2) Pure lobby state: use the pet selected in the lobby
  if (hasNoPanel && lobbyActiveAgentId) return lobbyActiveAgentId;
  // 3) Agent inside the currently active Panel
  if (activePanelAgentId) return activePanelAgentId;
  // 4) Lobby selected pet (fallback)
  if (lobbyActiveAgentId) return lobbyActiveAgentId;
  // 5) Final fallback
  return currentAgentId || null;
}
