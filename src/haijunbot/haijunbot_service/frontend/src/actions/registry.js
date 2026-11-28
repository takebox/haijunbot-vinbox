// Unified action registry (single source of truth)
// The pet menu, command palette, and shortcuts all derive their action lists from here.
// Pure module: no Vue dependency, no direct reference to App.vue; every side effect goes through the
// ctx callbacks supplied by the caller.
//
// Action object structure:
// {
//   id: string,
//   label: string,
//   en: string,
//   group: string,
//   icon: string,
//   keywords: string[],
//   shortcut?: string,
//   enabled?: (ctx) => boolean,
//   run: (ctx) => void | Promise<void>
// }

export const ACTIONS = [
  // ===== Current Agent group (formerly the panel-header icon actions) =====
  {
    id: "current-view-diff",
    label: "View Changes",
    shortcut: "Space a d",
    condition: "Requires the current Agent to be selected",
    en: "View Diff",
    group: "Current Agent",
    icon: "🔀",
    keywords: ["changes", "diff", "modifications", "changes"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) => ctx.viewCurrentDiff && ctx.viewCurrentDiff(),
  },
  {
    id: "current-view-rules",
    label: "View Rules",
    shortcut: "Space a r",
    condition: "Requires the current Agent to be selected",
    en: "View Rules",
    group: "Current Agent",
    icon: "📜",
    keywords: ["rules", "guidelines"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) => ctx.viewCurrentRules && ctx.viewCurrentRules(),
  },
  {
    id: "current-view-tools",
    label: "View Tools",
    shortcut: "Space a t",
    condition: "Requires the current Agent to be selected",
    en: "View Tools",
    group: "Current Agent",
    icon: "🔧",
    keywords: ["tools"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) => ctx.viewCurrentTools && ctx.viewCurrentTools(),
  },
  {
    id: "current-create-terminal",
    label: "Create Terminal",
    shortcut: "Space n t",
    condition: "Requires the current Agent to be selected",
    en: "Create Terminal",
    group: "Current Agent",
    icon: "💻",
    keywords: ["terminal", "create"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) =>
      ctx.createTerminalForCurrent && ctx.createTerminalForCurrent(),
  },
  {
    // Global action: open/hide the editor panel, independent of the current Agent (matches the Ctrl+E branch in App.vue)
    id: "open-editor",
    label: "Open Workspace",
    // Actually executed by App.vue's Ctrl+E branch; listed here for display only, not part of ctrl+alt unified dispatch
    shortcut: "Space v e",
    condition: "Logged in",
    en: "Open Workspace",
    group: "Interface",
    icon: "📝",
    keywords: ["editor", "open", "workspace"],
    run: (ctx) => ctx.toggleWorkspacePanel && ctx.toggleWorkspacePanel(),
  },
  {
    // Global action: quickly reach the editor sidebar's "search in files" (does nothing when the editor is closed)
    id: "open-editor-global-search",
    label: "Search File Contents",
    // Actually executed by App.vue's Ctrl+Shift+F branch; listed here for display only, not part of ctrl+alt unified dispatch
    shortcut: "Space v b / Ctrl+Shift+F",
    condition: "Requires the editor panel to be open",
    en: "Search File Contents",
    group: "Interface",
    icon: "🔎",
    keywords: [
      "global",
      "content search",
      "search",
      "find",
      "content",
    ],
    run: (ctx) =>
      ctx.openWorkspaceGlobalSearch && ctx.openWorkspaceGlobalSearch(),
  },
  {
    // Global action: quickly reach the editor sidebar's "search file names" (does nothing when the editor is closed)
    id: "open-editor-file-search",
    label: "Search File Names",
    // Actually executed by App.vue's Ctrl+Shift+P branch; listed here for display only, not part of ctrl+alt unified dispatch
    shortcut: "Space v n / Ctrl+Shift+P",
    condition: "Requires the editor panel to be open",
    en: "Search File Names",
    group: "Interface",
    icon: "🗂️",
    keywords: [
      "file name search",
      "search by name",
      "search",
      "find",
      "filename",
      "file",
    ],
    run: (ctx) => ctx.openWorkspaceFileSearch && ctx.openWorkspaceFileSearch(),
  },
  {
    // Global action: quickly reach the editor sidebar's file tree (does nothing when the editor is closed)
    id: "open-editor-file-tree",
    label: "File Tree",
    // Actually executed by App.vue's Ctrl+Shift+E branch; listed here for display only, not part of ctrl+alt unified dispatch
    shortcut: "Space v r / Ctrl+Shift+E",
    condition: "Requires the editor panel to be open",
    en: "File Tree",
    group: "Interface",
    icon: "📁",
    keywords: ["file tree", "file explorer", "tree", "explorer"],
    run: (ctx) => ctx.openWorkspaceFileTree && ctx.openWorkspaceFileTree(),
  },
  {
    // Global action: open the command palette
    id: "open-command-palette",
    label: "Open Command Palette",
    // Actually executed by App.vue's Ctrl+P branch; listed here for display only, not part of ctrl+alt unified dispatch
    shortcut: "Space v p / Ctrl+P",
    condition: "Logged in",
    en: "Open Command Palette",
    group: "Interface",
    icon: "⌘",
    keywords: ["command palette", "commands", "palette", "search"],
    run: (ctx) => ctx.openCommandPalette && ctx.openCommandPalette(),
  },
  {
    // Global action: save the editor's active tab
    id: "save-active-editor-tab",
    label: "Save Current File",
    // Actually executed by App.vue's Ctrl+S branch; listed here for display only, not part of ctrl+alt unified dispatch
    shortcut: "Space v w / Ctrl+S",
    condition: "Requires the editor panel to be open with an active tab",
    en: "Save Active File",
    group: "Interface",
    icon: "💾",
    keywords: ["save", "file", "editor"],
    run: (ctx) => ctx.saveActiveWorkspaceTab && ctx.saveActiveWorkspaceTab(),
  },
  {
    // Global action: split the editor workspace left/right
    id: "split-workspace-pane-row",
    label: "Split Editor Vertically",
    // Actually executed by App.vue's Ctrl+\ branch; listed here for display only, not part of ctrl+alt unified dispatch
    shortcut: "Space p s / Ctrl+\\",
    condition: "Requires the editor panel to be in file view and not on mobile",
    en: "Split Editor Right",
    group: "Interface",
    icon: "▥",
    keywords: ["split", "left", "right", "vertical", "pane"],
    run: (ctx) =>
      ctx.splitWorkspacePane && ctx.splitWorkspacePane(ctx.activePaneId, "row"),
  },
  {
    // Global action: split the editor workspace up/down
    id: "split-workspace-pane-column",
    label: "Split Editor Horizontally",
    // Actually executed by App.vue's Ctrl+Shift+\ branch; listed here for display only, not part of ctrl+alt unified dispatch
    shortcut: "Space p h / Ctrl+-",
    condition: "Requires the editor panel to be in file view and not on mobile",
    en: "Split Editor Down",
    group: "Interface",
    icon: "▤",
    keywords: ["split", "top", "bottom", "horizontal", "pane"],
    run: (ctx) =>
      ctx.splitWorkspacePane &&
      ctx.splitWorkspacePane(ctx.activePaneId, "column"),
  },
  {
    // Global action: close the currently focused panel / editor active region
    id: "close-focused-panel",
    label: "Close Focused Panel",
    // Actually executed by App.vue's Ctrl+W branch; listed here for display only, not part of ctrl+alt unified dispatch
    shortcut: "Space p x / Ctrl+W",
    condition: "Requires a currently focused panel",
    en: "Close Focused Panel",
    group: "Interface",
    icon: "✕",
    keywords: ["close", "panel", "focused"],
    run: (ctx) => ctx.closeFocusedPanel && ctx.closeFocusedPanel(),
  },
  {
    // Global action: send buffered input (when awaiting multi-line input)
    id: "send-buffered-input",
    label: "Send Buffered Input",
    // Actually executed by App.vue's Ctrl+Alt+Enter branch; listed here for display only, not part of ctrl+alt unified dispatch
    shortcut: "Ctrl+Alt+Enter",
    condition: "Requires buffered input",
    en: "Send Buffered Input",
    group: "Actions",
    icon: "⏎",
    keywords: ["send", "buffer", "input"],
    run: (ctx) => ctx.sendBufferedInput && ctx.sendBufferedInput(),
  },
  {
    // Global action: delete the Agent selected in the pet lobby
    id: "delete-lobby-agent",
    label: "Delete Selected Agent",
    // Actually executed by App.vue's Delete branch; listed here for display only, not part of ctrl+alt unified dispatch
    shortcut: "Delete",
    condition: "An Agent is selected in the lobby and focus is not inside an input field",
    en: "Delete Selected Agent",
    group: "Lobby",
    icon: "🗑",
    keywords: ["delete", "lobby", "agent"],
    enabled: (ctx) => !!ctx?.lobbyActiveAgentId,
    run: (ctx) =>
      ctx.deleteLobbyAgent && ctx.deleteLobbyAgent(ctx.lobbyActiveAgentId),
  },
  {
    id: "current-toggle-auto-scroll",
    label: "Toggle Auto-scroll",
    shortcut: "Space a s",
    condition: "Requires the current Agent to be selected",
    en: "Toggle Auto Scroll",
    group: "Current Agent",
    icon: "⤓",
    keywords: ["auto-scroll", "scroll", "auto", "toggle"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) => ctx.toggleCurrentAutoScroll && ctx.toggleCurrentAutoScroll(),
  },
  {
    id: "current-toggle-auto-read",
    label: "Toggle Auto-read",
    shortcut: "Space a v",
    condition: "Requires the current Agent to be selected",
    en: "Toggle Auto Read",
    group: "Current Agent",
    icon: "🔊",
    keywords: ["auto-read", "read", "speech", "voice", "toggle"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) => ctx.toggleCurrentAutoRead && ctx.toggleCurrentAutoRead(),
  },
  {
    id: "current-exit-non-interactive",
    label: "Exit Non-interactive Mode",
    shortcut: "Space a x",
    condition: "Requires the current Agent to be selected",
    en: "Exit Non-Interactive Mode",
    group: "Current Agent",
    icon: "🔓",
    keywords: ["non-interactive", "exit", "unlock"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) =>
      ctx.exitCurrentNonInteractive && ctx.exitCurrentNonInteractive(),
  },
  {
    id: "current-manual-interrupt",
    label: "Manual Intervention",
    shortcut: "Space a i",
    condition: "Requires the current Agent to be selected",
    en: "Manual Interrupt",
    group: "Current Agent",
    icon: "🛑",
    keywords: ["manual", "interrupt", "intervention", "stop"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) => ctx.interruptCurrentAgent && ctx.interruptCurrentAgent(),
  },
  {
    id: "current-rename",
    label: "Rename",
    shortcut: "Space a n",
    // F2 renames the current Agent first; only falls back to node-rename when there is no current Agent (see App.vue's F2 branch)
    shortcutScope: "global",
    condition: "Requires the current Agent to be selected; when F2 is shared with node rename, the Agent takes priority",
    en: "Rename",
    group: "Current Agent",
    icon: "✏",
    keywords: ["rename"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) => ctx.renameCurrentAgent && ctx.renameCurrentAgent(),
  },
  {
    id: "current-copy",
    label: "Duplicate",
    shortcut: "Space a c",
    condition: "Requires the current Agent to be selected",
    en: "Copy",
    group: "Current Agent",
    icon: "📋",
    keywords: ["copy", "clone", "duplicate"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) => ctx.copyCurrentAgent && ctx.copyCurrentAgent(),
  },
  {
    id: "current-edit-access",
    label: "Manage Permissions",
    shortcut: "Space a e",
    condition: "Requires the current Agent to be selected and you to be its owner",
    en: "Access Control",
    group: "Current Agent",
    icon: "🔒",
    keywords: ["permissions", "access", "acl"],
    enabled: (ctx) => ctx?.isCurrentAgentOwner === true,
    run: (ctx) => ctx.editCurrentAgentAccess && ctx.editCurrentAgentAccess(),
  },
  {
    id: "current-regenerate",
    label: "Regenerate",
    shortcut: "Space a g",
    condition: "Requires the current Agent to be selected and you to be its owner",
    en: "Regenerate",
    group: "Current Agent",
    icon: "🔄",
    keywords: ["regenerate", "rebuild", "recreate"],
    enabled: (ctx) => ctx?.isCurrentAgentOwner === true,
    run: (ctx) => ctx.regenerateCurrentAgent && ctx.regenerateCurrentAgent(),
  },
  {
    id: "current-delete",
    label: "Delete",
    shortcut: "Space a z",
    condition: "Requires the current Agent to be selected",
    en: "Delete",
    group: "Current Agent",
    icon: "🗑",
    keywords: ["delete", "remove"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) => ctx.deleteCurrentAgent && ctx.deleteCurrentAgent(),
  },
  {
    id: "current-toggle-output",
    label: "Toggle Output",
    shortcut: "Space a o",
    condition: "Requires the current Agent to be selected",
    en: "Toggle Output",
    group: "Current Agent",
    icon: "🙈",
    keywords: [
      "hide output",
      "show output",
      "output",
      "hide",
      "show",
      "toggle",
    ],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) =>
      ctx.toggleCurrentAgentOutput && ctx.toggleCurrentAgentOutput(),
  },
  {
    id: "editor-send-selection-to-agent",
    label: "Have Agent Analyze Selected Code",
    shortcut: "Space v d",
    condition: "Requires code selected in the editor",
    en: "Send Selection to Agent",
    group: "Current Agent",
    icon: "🤖",
    keywords: ["analyze", "selection", "agent", "explain", "code"],
    enabled: (ctx) => !!ctx?.currentAgentId && !!ctx?.getEditorSelection,
    run: (ctx) => ctx.sendSelectionToAgent && ctx.sendSelectionToAgent(),
  },
  {
    id: "interrupt-current",
    label: "Interrupt Current Agent",
    shortcut: "Space a k",
    condition: "Requires the current Agent to be selected",
    en: "Interrupt Current Agent",
    group: "Actions",
    icon: "⏹",
    keywords: ["interrupt", "stop", "cancel"],
    enabled: (ctx) => !!ctx?.currentAgentId,
    run: (ctx) => ctx.petInterruptCurrent && ctx.petInterruptCurrent(),
  },
  {
    id: "goto-waiting",
    label: "Go to Agent Awaiting Input",
    shortcut: "Space a w",
    condition: "Requires an Agent awaiting input",
    en: "Go to Waiting Agent",
    group: "Actions",
    icon: "🚨",
    keywords: ["waiting", "input", "switch", "goto"],
    enabled: (ctx) => {
      const list = ctx?.waitingAgents ?? ctx?.agentList ?? [];
      return Array.isArray(list) ? list.length > 0 : false;
    },
    run: (ctx) => ctx.petGotoWaitingAgent && ctx.petGotoWaitingAgent(),
  },
  {
    id: "sync-status",
    label: "Sync Agent Status",
    shortcut: "Space a y",
    condition: "No special conditions (always available)",
    en: "Sync Agent Status",
    group: "Actions",
    icon: "🔄",
    keywords: ["sync", "refresh", "status"],
    run: (ctx) => ctx.syncAllStatus && ctx.syncAllStatus(),
  },
  {
    id: "create-agent",
    label: "New Agent",
    shortcut: "Space n a / Ctrl+N",
    condition: "Logged in and not inside an input field",
    en: "New Agent",
    group: "Agent",
    icon: "➕",
    keywords: ["new", "create", "agent", "add"],
    run: (ctx) => ctx.openCreateAgentModal && ctx.openCreateAgentModal(),
  },
  {
    id: "quick-create-agent",
    label: "Quick Create Agent",
    shortcut: "Space n q",
    condition: "Logged in",
    en: "Quick Create Agent",
    group: "Agent",
    icon: "⚡",
    keywords: [
      "one-shot",
      "quick",
      "create",
      "task",
    ],
    run: (ctx) => ctx.openQuickCreateAgent && ctx.openQuickCreateAgent(),
  },
  {
    id: "refresh-agents",
    label: "Refresh Agent List",
    shortcut: "Space a f",
    condition: "Logged in",
    en: "Refresh Agent List",
    group: "Agent",
    icon: "🔃",
    keywords: ["refresh", "list", "agents"],
    run: (ctx) => ctx.refreshAgentList && ctx.refreshAgentList(),
  },
  {
    id: "restart-gateway",
    label: "Restart Gateway",
    shortcut: "Space m q",
    condition: "Requires admin:config permission",
    en: "Restart Gateway",
    group: "Gateway",
    icon: "♻",
    keywords: ["restart", "gateway"],
    enabled: (ctx) => !!ctx?.hasPermission && ctx.hasPermission("admin:config"),
    run: (ctx) => ctx.restartGateway && ctx.restartGateway(),
  },
  {
    id: "restart-all-nodes",
    label: "Restart All Nodes",
    shortcut: "Space m r",
    condition: "Requires admin:config permission",
    en: "Restart All Nodes",
    group: "Gateway",
    icon: "🔁",
    keywords: ["restart", "nodes", "all"],
    enabled: (ctx) => !!ctx?.hasPermission && ctx.hasPermission("admin:config"),
    run: (ctx) => ctx.confirmRestartAllNodes && ctx.confirmRestartAllNodes(),
  },
  {
    id: "manage-groups",
    label: "Manage Groups",
    shortcut: "Space m g",
    condition: "Logged in",
    en: "Manage Groups",
    group: "Interface",
    icon: "📁",
    keywords: ["groups", "manage", "rename", "delete"],
    run: (ctx) => ctx.manageGroups && ctx.manageGroups(),
  },
  {
    id: "toggle-terminal",
    label: "Toggle Terminal Panel",
    shortcut: "Space v t / Ctrl+`",
    condition: "Not inside an input field",
    en: "Toggle Terminal Panel",
    group: "Interface",
    icon: "🖥",
    keywords: ["terminal", "toggle"],
    run: (ctx) => ctx.toggleTerminalPanel && ctx.toggleTerminalPanel(),
  },
  {
    id: "toggle-chat",
    label: "Toggle Chat Panel",
    shortcut: "Space v c",
    condition: "Logged in",
    en: "Toggle Chat Panel",
    group: "Interface",
    icon: "💬",
    keywords: ["chat", "group chat", "toggle"],
    run: (ctx) => ctx.toggleChatPanel && ctx.toggleChatPanel(),
  },
  {
    id: "open-topology",
    label: "View Network Topology",
    shortcut: "Space v u",
    condition: "Logged in",
    en: "View Network Topology",
    group: "Interface",
    icon: "🗺",
    keywords: ["topology", "network", "nodes"],
    run: (ctx) => ctx.openTopology && ctx.openTopology(),
  },
  {
    id: "open-settings",
    label: "Open Settings",
    shortcut: "Space v s",
    condition: "Logged in",
    en: "Open Settings",
    group: "Interface",
    icon: "⚙",
    keywords: ["settings", "config", "preferences"],
    run: (ctx) => ctx.openSettings && ctx.openSettings(),
  },
  {
    id: "toggle-pet",
    label: "Hide/Show Pet",
    shortcut: "Space v o",
    condition: "Logged in",
    en: "Toggle Pet",
    group: "Interface",
    icon: "🐾",
    keywords: ["pet", "widget", "hide", "show", "toggle"],
    run: (ctx) => ctx.togglePetVisibility && ctx.togglePetVisibility(),
  },
  {
    id: "open-agent-list",
    label: "Agent List",
    shortcut: "Space v l / Ctrl+A",
    condition: "Logged in",
    en: "Agent List",
    group: "Interface",
    icon: "📋",
    keywords: ["agent", "list", "switch", "select"],
    run: (ctx) => ctx.openAgentList && ctx.openAgentList(),
  },
  {
    // Sidebar activity bar "Agent List" view: open the workspace and switch to the agents sidebar view
    id: "open-workspace-agent-list",
    label: "Workspace Agent List",
    shortcut: "Space v a",
    condition: "Logged in",
    en: "Workspace Agent List",
    group: "Interface",
    icon: "📋",
    keywords: [
      "agent",
      "list",
      "workspace",
      "sidebar",
      "list",
    ],
    run: (ctx) => ctx.openWorkspaceAgentList && ctx.openWorkspaceAgentList(),
  },
  {
    // Command palette file search: open the palette and pre-fill f>, going straight to file search (matches Ctrl+F)
    id: "open-command-palette-file-search",
    label: "File Search",
    shortcut: "Space v f / Ctrl+F",
    condition: "Logged in",
    en: "File Search",
    group: "Interface",
    icon: "🔎",
    keywords: ["file", "search", "find", "command palette"],
    run: (ctx) =>
      ctx.openCommandPaletteFileSearch && ctx.openCommandPaletteFileSearch(),
  },
  {
    // Sidebar activity bar "Git" view: open the workspace and switch to the Git sidebar view
    id: "open-workspace-git",
    label: "Git View",
    shortcut: "Space v g",
    condition: "Logged in",
    en: "Git View",
    group: "Interface",
    icon: "🔀",
    keywords: ["git", "commit", "branch", "version", "commit", "branch"],
    run: (ctx) => ctx.openWorkspaceGit && ctx.openWorkspaceGit(),
  },
  {
    id: "open-onboarding",
    label: "About HaijunBot",
    condition: "Logged in",
    en: "About HaijunBot",
    group: "Interface",
    icon: "🎓",
    keywords: [
      "beginner",
      "guide",
      "tutorial",
      "get started",
      "introduction",
      "help",
      "about",
    ],
    run: (ctx) => ctx.startOnboarding && ctx.startOnboarding("welcome"),
  },
  {
    id: "open-docs",
    label: "Open Documentation",
    shortcut: "Space m h",
    condition: "Logged in",
    en: "Open Documentation",
    group: "Interface",
    icon: "📖",
    keywords: [
      "docs",
      "manual",
      "help",
      "usage",
      "tutorial",
      "documentation",
    ],
    run: (ctx) => ctx.openDocs && ctx.openDocs(),
  },
  {
    id: "open-sidebar-onboarding",
    label: "View Sidebar Guide",
    condition: "Logged in",
    en: "Sidebar Guide",
    group: "Interface",
    icon: "📋",
    keywords: [
      "sidebar",
      "guide",
      "tutorial",
      "beginner",
      "agent list",
      "tour",
    ],
    run: (ctx) => ctx.startOnboarding && ctx.startOnboarding("sidebar"),
  },
  {
    id: "reset-onboarding",
    label: "Reset Onboarding",
    condition: "Logged in",
    en: "Reset Onboarding",
    group: "Interface",
    icon: "♻️",
    keywords: [
      "beginner",
      "guide",
      "reset",
      "clear",
      "restart",
      "tutorial",
    ],
    run: (ctx) => ctx.resetOnboarding && ctx.resetOnboarding(),
  },
  {
    id: "install-browser-extension",
    label: "Install Browser Extension",
    condition: "Logged in",
    en: "Install Browser Extension",
    group: "Interface",
    icon: "🧩",
    keywords: [
      "plugin",
      "extension",
      "browser",
      "install",
    ],
    run: (ctx) => ctx.openInstallExtension && ctx.openInstallExtension(),
  },
  {
    id: "install-daemon",
    label: "Install Local Background Service",
    condition: "Logged in",
    en: "Install Local Daemon",
    group: "Interface",
    icon: "🖥",
    keywords: [
      "background",
      "service",
      "local",
      "daemon",
      "process",
      "install",
    ],
    run: (ctx) => ctx.openDaemonInstall && ctx.openDaemonInstall(),
  },
  // ===== Account =====
  {
    id: "logout",
    label: "Log Out",
    condition: "Logged in",
    en: "Log Out",
    group: "Account",
    icon: "🚪",
    keywords: [
      "exit",
      "sign out",
      "log out",
      "disconnect",
      "logout",
      "signout",
    ],
    run: (ctx) => ctx.logout && ctx.logout(),
  },
  // ===== Admin (requires admin permission) =====
  {
    id: "admin-update-code-to-main",
    label: "Update Code to the main Branch",
    condition: "Requires admin:config permission",
    en: "Update Code to main",
    group: "Admin",
    icon: "⬆",
    keywords: ["update", "code", "main", "pull", "update", "code"],
    enabled: (ctx) => !!ctx?.hasPermission && ctx.hasPermission("admin:config"),
    run: (ctx) => ctx.confirmUpdateCodeToMain && ctx.confirmUpdateCodeToMain(),
  },
  {
    id: "admin-restart-node-service",
    label: "Restart Node Service",
    condition: "Requires admin:config permission",
    en: "Restart Node Service",
    group: "Admin",
    icon: "♻",
    keywords: ["restart", "node", "service"],
    enabled: (ctx) => !!ctx?.hasPermission && ctx.hasPermission("admin:config"),
    run: (ctx) => ctx.openAdminRestartService && ctx.openAdminRestartService(),
  },
  {
    id: "admin-sync-config",
    label: "Sync Config to Other Nodes",
    condition: "Requires admin:config permission",
    en: "Sync Config to Nodes",
    group: "Admin",
    icon: "🔃",
    keywords: ["sync", "config", "nodes"],
    enabled: (ctx) => !!ctx?.hasPermission && ctx.hasPermission("admin:config"),
    run: (ctx) => ctx.openAdminSyncConfig && ctx.openAdminSyncConfig(),
  },
  {
    id: "admin-node-secret",
    label: "View Node Connection Secret",
    condition: "Requires admin:config permission",
    en: "View Node Secret",
    group: "Admin",
    icon: "🔑",
    keywords: ["secret", "key", "node"],
    enabled: (ctx) => !!ctx?.hasPermission && ctx.hasPermission("admin:config"),
    run: (ctx) => ctx.openAdminNodeSecret && ctx.openAdminNodeSecret(),
  },
  {
    id: "admin-edit-config",
    label: "Edit Config File",
    condition: "Requires admin:config permission",
    en: "Edit Config File",
    group: "Admin",
    icon: "⚙",
    keywords: ["config", "file", "models", "model groups", "edit", "llm"],
    enabled: (ctx) => !!ctx?.hasPermission && ctx.hasPermission("admin:config"),
    run: (ctx) => ctx.openAdminConfigFile && ctx.openAdminConfigFile(),
  },
  {
    id: "admin-open-panel",
    label: "Open Admin Panel",
    shortcut: "Space m a",
    condition: "Requires admin permission (any of config/users/permissions)",
    en: "Open Admin Panel",
    group: "Admin",
    icon: "🛠",
    keywords: ["admin", "panel", "users", "permissions"],
    enabled: (ctx) =>
      !!ctx?.hasPermission &&
      (ctx.hasPermission("admin:config") ||
        ctx.hasPermission("admin:users") ||
        ctx.hasPermission("admin:permissions")),
    run: (ctx) => ctx.openAdminPanel && ctx.openAdminPanel(),
  },
  {
    // Open the workspace and switch to the "plugin management" sidebar view (the side activity bar "plugins" button)
    id: "open-workspace-plugins",
    label: "Plugin Management",
    shortcut: "Space m p",
    condition: "Requires admin:plugins permission",
    en: "Plugin Management",
    group: "Admin",
    icon: "🧩",
    keywords: ["plugin", "plugins", "extensions"],
    enabled: (ctx) =>
      !!ctx?.hasPermission && ctx.hasPermission("admin:plugins"),
    run: (ctx) => ctx.openWorkspacePlugins && ctx.openWorkspacePlugins(),
  },
  // ===== Nodes (apply to the node selected in the lobby) =====
  {
    id: "node-create-agent",
    label: "Create Agent on Selected Node",
    condition: "A node is selected in the lobby",
    en: "Create Agent on Node",
    group: "Nodes",
    icon: "➕",
    keywords: ["node", "create", "agent"],
    enabled: (ctx) => !!ctx?.currentNodeId,
    run: (ctx) =>
      ctx.createAgentOnNode && ctx.createAgentOnNode(ctx.currentNodeId),
  },
  {
    id: "node-open-terminal",
    label: "Open Terminal on Selected Node",
    condition: "A node is selected in the lobby",
    en: "Open Node Terminal",
    group: "Nodes",
    icon: "⌨️",
    keywords: ["node", "terminal", "shell"],
    enabled: (ctx) => !!ctx?.currentNodeId,
    run: (ctx) =>
      ctx.openTerminalOnNode && ctx.openTerminalOnNode(ctx.currentNodeId),
  },
  {
    id: "node-update-code",
    label: "Update Code on Selected Node",
    condition: "A node is selected in the lobby",
    en: "Update Node Code",
    group: "Nodes",
    icon: "🔄",
    keywords: ["node", "update", "code", "pull"],
    enabled: (ctx) => !!ctx?.currentNodeId,
    run: (ctx) => ctx.updateNodeCode && ctx.updateNodeCode(ctx.currentNodeId),
  },
  {
    id: "node-restart-service",
    label: "Restart Service on Selected Node",
    condition: "A node is selected in the lobby",
    en: "Restart Node Service",
    group: "Nodes",
    icon: "♻️",
    keywords: ["node", "restart", "service"],
    enabled: (ctx) => !!ctx?.currentNodeId,
    run: (ctx) =>
      ctx.restartNodeService && ctx.restartNodeService(ctx.currentNodeId),
  },
  {
    // Shares F2 with "current-rename" in the "Current Agent" group: the two are distinguished by shortcutScope;
    // the Agent rename wins when a current Agent exists, otherwise this action runs (see App.vue's F2 branch)
    id: "node-rename",
    label: "Rename Selected Node",
    shortcut: "F2",
    shortcutScope: "node",
    condition: "A node is selected in the lobby; when F2 is shared with Agent rename, the Agent takes priority",
    en: "Rename Node",
    group: "Nodes",
    icon: "✏️",
    keywords: ["node", "rename"],
    enabled: (ctx) => !!ctx?.currentNodeId,
    run: (ctx) => ctx.renameNode && ctx.renameNode(ctx.currentNodeId),
    // Renaming pops an input box in the lobby, so the command palette must close first to release focus
    closePaletteOnRun: true,
  },
  // ===== Lobby directional selection (Ctrl+Alt+arrow keys) =====
  // Shares the same physical keys as the existing "region focus navigation" in App.vue: when the lobby has pets,
  // the pet is selected first; without pets it falls back to region navigation (see App.vue's Ctrl+Alt+arrow branch).
  // These four actions are only for the command palette / shortcut overview display and execution; they do not take
  // part in handleGlobalKeydown's registry dispatch (that dispatch requires ctrl+alt and not already consumed by an
  // earlier branch; the arrow-key branch returns early).
  {
    id: "lobby-select-left",
    label: "Select Agent to the Left",
    shortcut: "Ctrl+Alt+ArrowLeft",
    condition: "The pet lobby has Agents",
    en: "Select Agent to the Left",
    group: "Lobby",
    icon: "⬅️",
    keywords: ["lobby", "select", "direction", "left"],
    enabled: (ctx) => !!ctx?.hasLobbyAgents,
    run: (ctx) =>
      ctx.selectLobbyAgentInDirection &&
      ctx.selectLobbyAgentInDirection("left"),
  },
  {
    id: "lobby-select-right",
    label: "Select Agent to the Right",
    shortcut: "Ctrl+Alt+ArrowRight",
    condition: "The pet lobby has Agents",
    en: "Select Agent to the Right",
    group: "Lobby",
    icon: "➡️",
    keywords: ["lobby", "select", "direction", "right"],
    enabled: (ctx) => !!ctx?.hasLobbyAgents,
    run: (ctx) =>
      ctx.selectLobbyAgentInDirection &&
      ctx.selectLobbyAgentInDirection("right"),
  },
  {
    id: "lobby-select-up",
    label: "Select Agent Above",
    shortcut: "Ctrl+Alt+ArrowUp",
    condition: "The pet lobby has Agents",
    en: "Select Agent Above",
    group: "Lobby",
    icon: "⬆️",
    keywords: ["lobby", "select", "direction", "up"],
    enabled: (ctx) => !!ctx?.hasLobbyAgents,
    run: (ctx) =>
      ctx.selectLobbyAgentInDirection && ctx.selectLobbyAgentInDirection("up"),
  },
  {
    id: "lobby-select-down",
    label: "Select Agent Below",
    shortcut: "Ctrl+Alt+ArrowDown",
    condition: "The pet lobby has Agents",
    en: "Select Agent Below",
    group: "Lobby",
    icon: "⬇️",
    keywords: ["lobby", "select", "direction", "down"],
    enabled: (ctx) => !!ctx?.hasLobbyAgents,
    run: (ctx) =>
      ctx.selectLobbyAgentInDirection &&
      ctx.selectLobbyAgentInDirection("down"),
  },

  // ===== Lobby node directional selection (Ctrl+Shift+arrow keys) =====
  // Distinguished from Agent directional selection (Ctrl+Alt+arrow keys): Shift operates on nodes, Alt on Agents.
  // Also only for the command palette / shortcut overview display and execution; not part of handleGlobalKeydown's unified dispatch.
  {
    id: "lobby-node-select-left",
    label: "Select Node to the Left",
    shortcut: "Ctrl+Alt+Shift+ArrowLeft",
    condition: "The pet lobby has nodes",
    en: "Select Node to the Left",
    group: "Lobby",
    icon: "⬅️",
    keywords: [
      "lobby",
      "node",
      "select",
      "direction",
      "left",
    ],
    enabled: (ctx) => !!ctx?.hasLobbyNodes,
    run: (ctx) =>
      ctx.selectLobbyNodeInDirection && ctx.selectLobbyNodeInDirection("left"),
  },
  {
    id: "lobby-node-select-right",
    label: "Select Node to the Right",
    shortcut: "Ctrl+Alt+Shift+ArrowRight",
    condition: "The pet lobby has nodes",
    en: "Select Node to the Right",
    group: "Lobby",
    icon: "➡️",
    keywords: [
      "lobby",
      "node",
      "select",
      "direction",
      "right",
    ],
    enabled: (ctx) => !!ctx?.hasLobbyNodes,
    run: (ctx) =>
      ctx.selectLobbyNodeInDirection && ctx.selectLobbyNodeInDirection("right"),
  },
  {
    id: "lobby-node-select-up",
    label: "Select Node Above",
    shortcut: "Ctrl+Alt+Shift+ArrowUp",
    condition: "The pet lobby has nodes",
    en: "Select Node Above",
    group: "Lobby",
    icon: "⬆️",
    keywords: [
      "lobby",
      "node",
      "select",
      "direction",
      "up",
    ],
    enabled: (ctx) => !!ctx?.hasLobbyNodes,
    run: (ctx) =>
      ctx.selectLobbyNodeInDirection && ctx.selectLobbyNodeInDirection("up"),
  },
  {
    id: "lobby-node-select-down",
    label: "Select Node Below",
    shortcut: "Ctrl+Alt+Shift+ArrowDown",
    condition: "The pet lobby has nodes",
    en: "Select Node Below",
    group: "Lobby",
    icon: "⬇️",
    keywords: [
      "lobby",
      "node",
      "select",
      "direction",
      "down",
    ],
    enabled: (ctx) => !!ctx?.hasLobbyNodes,
    run: (ctx) =>
      ctx.selectLobbyNodeInDirection && ctx.selectLobbyNodeInDirection("down"),
  },

  // ===== Lobby: show/hide all outputs (Ctrl+Alt+A) =====
  // One-key toggle: hide all ↔ show all. Only for the command palette / shortcut overview display and execution,
  // not part of handleGlobalKeydown's unified dispatch (handled by App.vue's Ctrl+Alt+A branch).
  {
    id: "lobby-toggle-all-outputs",
    label: "Hide/Show All Outputs",
    shortcut: "Ctrl+Alt+A",
    condition: "The pet lobby has Agents",
    en: "Toggle All Outputs",
    group: "Lobby",
    icon: "💬",
    keywords: [
      "lobby",
      "output",
      "all",
      "hide",
      "show",
      "bubbles",
      "toggle",
    ],
    enabled: (ctx) => !!ctx?.hasLobbyAgentsForOutput,
    run: (ctx) => ctx.toggleAllLobbyOutputs && ctx.toggleAllLobbyOutputs(),
  },
];

// Case-insensitive substring / keyword fuzzy match; returns everything when query is empty
export function filterActions(actions, query) {
  const list = Array.isArray(actions) ? actions : [];
  const q = String(query ?? "")
    .trim()
    .toLowerCase();
  if (!q) return list.slice();
  return list.filter((action) => {
    const haystack = [
      action?.label,
      action?.en,
      action?.id,
      action?.group,
      ...(action?.keywords || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
}

// Aggregate by group, preserving in-group original order and group first-appearance order
export function groupActions(actions) {
  const list = Array.isArray(actions) ? actions : [];
  const order = [];
  const buckets = new Map();
  for (const action of list) {
    const key = action?.group || "Other";
    if (!buckets.has(key)) {
      buckets.set(key, []);
      order.push(key);
    }
    buckets.get(key).push(action);
  }
  return order.map((group) => ({ group, actions: buckets.get(group) }));
}

// ===== Keyboard shortcut conflict self-check =====
// Reusing the same physical key in different scenarios is allowed, but it must be clearly
// distinguishable, otherwise handleGlobalKeydown ambiguity arises when actionDefs.find(...)
// returns the first match (later-registered actions never fire).
// Convention: same-key actions must declare shortcutScope and scopes must differ;
// an undeclared scope counts as "global".
// Example: F2 current-rename is "global", node-rename is "node" (takes priority while a node is selected).
export function findShortcutConflicts(actions = ACTIONS) {
  const byShortcut = new Map();
  for (const action of Array.isArray(actions) ? actions : []) {
    if (!action?.shortcut) continue;
    const key = String(action.shortcut).trim().toLowerCase();
    if (!byShortcut.has(key)) byShortcut.set(key, []);
    byShortcut.get(key).push(action);
  }
  const conflicts = [];
  for (const [shortcut, list] of byShortcut) {
    if (list.length < 2) continue;
    const scopes = list.map((a) => a.shortcutScope || "global");
    const duplicated = scopes.filter((s, i) => scopes.indexOf(s) !== i);
    if (duplicated.length > 0) {
      conflicts.push({
        shortcut,
        reason: `duplicate shortcutScope: ${[...new Set(duplicated)].join(", ")}`,
        actions: list.map((a) => a.id),
      });
    }
  }
  return conflicts;
}

// Dev-time self-check: warn in the console when the registry contains indistinguishable same-key actions (does not block execution)
if (import.meta.env?.DEV) {
  const conflicts = findShortcutConflicts();
  if (conflicts.length > 0) {
    console.warn(
      "[shortcut] Keyboard shortcut conflicts detected (same-key actions must declare mutually distinct shortcutScope):",
      conflicts,
    );
  }
}

// ===== Space-leader key sequence command tree =====
// Full redesign: a two-level "space + domain key + action key" key sequence replaces most
// Ctrl+Alt(+Shift)+letter combos. Semantic keys are always unmodified single letters, so they
// are never intercepted by the system/browser (Ctrl+Alt+Shift is captured by system software
// in user environments).
// Structure: { [domainKey]: { label, children: { [actionKey]: { label, actionId } } } }
// Leaf nodes reference the actions in ACTIONS above via actionId; App.vue runs
// onCommandRun(the matching action) when a leaf is hit.
export const SPACE_COMMANDS = {
  p: {
    label: "Panel",
    children: {
      x: { label: "Close current panel", actionId: "close-focused-panel" },
      s: { label: "Split left-right", actionId: "split-workspace-pane-row" },
      h: { label: "Split top-bottom", actionId: "split-workspace-pane-column" },
    },
  },
  a: {
    label: "Agent",
    children: {
      d: { label: "View changes", actionId: "current-view-diff" },
      r: { label: "View rules", actionId: "current-view-rules" },
      t: { label: "View tools", actionId: "current-view-tools" },
      i: { label: "Manual intervention", actionId: "current-manual-interrupt" },
      k: { label: "Interrupt", actionId: "interrupt-current" },
      o: { label: "Hide/show output", actionId: "current-toggle-output" },
      v: { label: "Auto read aloud", actionId: "current-toggle-auto-read" },
      s: { label: "Auto scroll", actionId: "current-toggle-auto-scroll" },
      c: { label: "Copy", actionId: "current-copy" },
      e: { label: "Access management", actionId: "current-edit-access" },
      g: { label: "Lossless regenerate", actionId: "current-regenerate" },
      x: { label: "Exit non-interactive", actionId: "current-exit-non-interactive" },
      n: { label: "Rename", actionId: "current-rename" },
      y: { label: "Sync status", actionId: "sync-status" },
      f: { label: "Refresh Agent list", actionId: "refresh-agents" },
      w: { label: "Go to awaiting input", actionId: "goto-waiting" },
      z: { label: "Delete current Agent", actionId: "current-delete" },
    },
  },
  v: {
    label: "View",
    children: {
      a: { label: "Agent list", actionId: "open-workspace-agent-list" },
      g: { label: "Git view", actionId: "open-workspace-git" },
      e: { label: "Workspace", actionId: "open-editor" },
      t: { label: "Terminal", actionId: "toggle-terminal" },
      c: { label: "Chat", actionId: "toggle-chat" },
      s: { label: "Settings", actionId: "open-settings" },
      u: { label: "Network topology", actionId: "open-topology" },
      p: { label: "Command palette", actionId: "open-command-palette" },
      l: { label: "Agent list (command palette)", actionId: "open-agent-list" },
      f: { label: "File search", actionId: "open-command-palette-file-search" },
      r: { label: "Directory tree", actionId: "open-editor-file-tree" },
      b: { label: "Content search", actionId: "open-editor-global-search" },
      n: { label: "File name search", actionId: "open-editor-file-search" },
      w: { label: "Save current file", actionId: "save-active-editor-tab" },
      d: {
        label: "Let the Agent analyze the selected code",
        actionId: "editor-send-selection-to-agent",
      },
      o: { label: "Hide/show pet", actionId: "toggle-pet" },
    },
  },
  n: {
    label: "New",
    children: {
      a: { label: "Create Agent", actionId: "create-agent" },
      q: { label: "One-liner create", actionId: "quick-create-agent" },
      t: { label: "Create terminal", actionId: "current-create-terminal" },
    },
  },
  m: {
    label: "Manage",
    children: {
      g: { label: "Manage groups", actionId: "manage-groups" },
      a: { label: "Manage panel", actionId: "admin-open-panel" },
      h: { label: "Usage docs", actionId: "open-docs" },
      r: { label: "Restart all nodes", actionId: "restart-all-nodes" },
      q: { label: "Restart gateway", actionId: "restart-gateway" },
      p: { label: "Plugin management", actionId: "open-workspace-plugins" },
    },
  },
};

// Flat "space sequence → actionId" mapping derived from SPACE_COMMANDS (used by App.vue fast matching and command palette display)
export const SPACE_COMMAND_ACTIONS = (() => {
  const map = {};
  for (const [gKey, group] of Object.entries(SPACE_COMMANDS)) {
    for (const [aKey, leaf] of Object.entries(group.children || {})) {
      map[`${gKey}${aKey}`] = leaf.actionId;
    }
  }
  return map;
})();

export default ACTIONS;
