// Onboarding tour composable.
//
// Extracted from App.vue's <script setup> (Issue #118 Step 8), preserving behavior exactly:
// - Constants: ONBOARDING_KEY_PREFIX / LEGACY_ONBOARDING_KEY / ONBOARDING_AUTO_DELAY
// - State: activeTourId / activeTourSteps / showOnboarding / onboardingTimer
// - Flag read/write: onboardingKey / hasSeenTour / markTourSeen / resetOnboardingMarks
// - Step constants: WELCOME_TOUR_STEPS / LOBBY_TOUR_STEPS / AGENT_TOUR_STEPS /
// - Trigger/close: maybeStartTour / finishTour / startOnboarding / clearOnboardingTimer

//
// Dependency injection (passed in by the caller within setup; must be called after they are defined):
// - showToast: toasts when finishTour completes the welcome tour (getter form, evaluated only when called internally)
// - openWorkspaceAgentList: the sidebar scenario of startOnboarding needs to open the editor and switch to
//   the Agent list view first (getter form, defined after this composable's call site to avoid a TDZ)
import { computed, ref } from 'vue'
export function useTour({ showToast, openWorkspaceAgentList }) {
  // Multiple tours triggered per scenario: shown once each on first entering the lobby / first creating an Agent / first opening a Panel;
  // each tour writes a separate flag once seen, which can be cleared via the command palette "Reset onboarding tour" to trigger again.
  const ONBOARDING_KEY_PREFIX = 'haijunbot_onboarding_'
  // Legacy single tour flag: existing users have already seen it, treated as welcome seen, to avoid disturbing them again
  const LEGACY_ONBOARDING_KEY = 'haijunbot_onboarding_done_v1'
  const ONBOARDING_AUTO_DELAY = 800
  // The tour scenario currently in progress (null means not active)
  const activeTourId = ref(null)
  const activeTourSteps = computed(() => (activeTourId.value ? getTourSteps(activeTourId.value) : []))
  const showOnboarding = computed({
    get: () => activeTourId.value !== null,
    set: (visible) => {
      if (!visible && activeTourId.value) finishTour()
    },
  })
  let onboardingTimer = null

  function clearOnboardingTimer() {
    if (onboardingTimer) {
      clearTimeout(onboardingTimer)
      onboardingTimer = null
    }
  }

  function onboardingKey(tourId) {
    return `${ONBOARDING_KEY_PREFIX}${tourId}_v1`
  }

  function hasSeenTour(tourId) {
    try {
      if (localStorage.getItem(onboardingKey(tourId)) === '1') return true
      if (tourId === 'welcome' && localStorage.getItem(LEGACY_ONBOARDING_KEY) === '1') return true
      return false
    } catch (err) {
      return true
    }
  }

  function markTourSeen(tourId) {
    try {
      localStorage.setItem(onboardingKey(tourId), '1')
    } catch (err) {
      /* A write failure in private mode can be ignored */
    }
  }

  // Tour steps per scenario. When target cannot find an element the component automatically degrades to a centered card
  function getTourSteps(tourId) {
    if (tourId === 'welcome') return WELCOME_TOUR_STEPS
    if (tourId === 'lobby') return LOBBY_TOUR_STEPS()
    if (tourId === 'agent') return AGENT_TOUR_STEPS()
    if (tourId === 'panel') return PANEL_TOUR_STEPS()
    if (tourId === 'sidebar') return SIDEBAR_TOUR_STEPS()
    return []
  }

  // Intro page: single step, no target (centered card), introducing HaijunBot's positioning and core concepts
  const WELCOME_TOUR_STEPS = [
    {
      id: 'welcome',
      icon: '👋',
      title: 'Welcome to HaijunBot',
      desc: 'HaijunBot moves AI from "working alone" to "working together": you no longer drive just one assistant, but orchestrate multiple Agents at once, each handling its own task and collaborating.',
      hint: 'Four collaboration modes to combine as you like: one person one Agent (focus on one thing), one person many Agents (parallel progress), many people one Agent (share a single assistant), many people many Agents (each team with its own crew).',
    },
    {
      id: 'welcome-concepts',
      icon: '🧭',
      title: 'Five core concepts',
      desc: 'Agent: an AI assistant that can be assigned tasks, split into general Agents (analysis, planning, execution) and code Agents (reading code, editing code, running verification). Node: the machine where an Agent runs. Gateway: the server connecting you to all nodes.',
      hint: 'Pet lobby: when no panel is open, all Agents appear here as pets. Command palette: press Ctrl+P (⌘+P on Mac) to search and run almost every action.',
    },
    {
      id: 'welcome-toolbar',
      icon: '🧰',
      title: 'Top-right toolbar',
      desc: 'The top-right has a permanent toolbar: 💬 open the chat room, 💻 open the terminal panel, ⌘ open the command palette (Ctrl+P), ⚙ open settings; administrators also see a 🛡️ admin entry. The Agent list is in the editor panel sidebar (open with Ctrl+A).',
      hint: 'The toolbar can be dragged (dropping it on the left/right edge of the screen auto-collapses it into a narrow strip you can click to expand); long-press the main pet in the bottom-left to quickly create an Agent with a single sentence (Ctrl+Alt+N).',
    },
    {
      id: 'welcome-command-palette',
      icon: '⌘',
      title: 'Command palette',
      desc: 'Press Ctrl+P (⌘+P on Mac) or click ⌘ in the toolbar to open the command palette: actions are grouped (Current Agent, Execution, Interface, Gateway, Admin, Account, Nodes, Lobby, etc.); type keywords to search and press Enter to run.',
      hint: 'Many actions have shortcuts (e.g. Ctrl+N to create an Agent, Ctrl+Alt+K to interrupt the current Agent); the command palette is the unified entry for "almost every action" and is handiest when you cannot remember shortcuts.',
    },
    {
      id: 'welcome-more',
      icon: '🧩',
      title: 'More entries',
      desc: 'The command palette also hides many useful capabilities: hide/show pets (Ctrl+Alt+B), hide/show all output, refresh and sync Agent status, log out; administrators can also restart the gateway/nodes, open the admin panel, and edit the config file in the settings modal.',
      hint: '"Install browser extension" lets HaijunBot operate web pages in your browser; "View network topology" shows the full picture of node connections. Config file editing (requires admin:config permission) is in the "Config file editing" section of the settings modal, supporting both form and plain-text modes.',
    },
    {
      id: 'welcome-start',
      icon: '🚀',
      title: 'Get started',
      desc: 'Create your first Agent with "➕" in the editor panel sidebar\'s Agent list (or press Ctrl+N); double-click a pet to open the chat panel, describe your request in the bottom input box and send (press Enter in single-line mode, or Ctrl+Enter / Ctrl+D).',
      hint: 'At any time, search "tour" in the command palette (Ctrl+P) to view it again, or search "reset onboarding tour" to re-trigger the tours for each scenario.',
    },
  ]

  // Lobby scenario: shown when no Panel is visible
  function LOBBY_TOUR_STEPS() {
    return [
      {
        id: 'lobby-dashboard',
        icon: '📊',
        title: 'Lobby dashboard',
        desc: 'This shows in real time the current time, gateway connection status and address, the number of online nodes, and Agent counts by status, giving you the whole picture at a glance.',
        hint: 'When the gateway is offline pets stop responding; first check the connection status on the dashboard in the top-left of the lobby.',
        target: '.pet-lobby-dash',
        placement: 'bottom',
      },
      {
        id: 'lobby-pet',
        icon: '🐾',
        title: 'Pets are Agents',
        desc: 'Each pet corresponds to one Agent: drag to reposition, double-click to open its chat panel, and its latest output scrolls above the pet.',
        hint: 'When it needs your confirmation or input the pet highlights to alert you; right-click a pet to open the quick actions menu.',
        target: '.lobby-pet',
        placement: 'bottom',
      },
      {
        id: 'lobby-at-completion',
        icon: '@',
        title: 'Use @ to reference in the pet input box',
        desc: 'When a pet is waiting for input you can reply directly in the input box below it, without opening the panel. Typing @ also pops up the completion list, letting you reference files, rules, built-in commands, and substitution variables.',
        hint: 'The completion list supports arrow-key selection, Enter to insert, Esc to cancel; typing a file name searches and references the file content, saving manual pasting.',
        target: '.lobby-pet',
        placement: 'bottom',
      },
      {
        id: 'lobby-topology',
        icon: '🕸',
        title: 'Nodes and topology',
        desc: 'The computer cases in the lobby represent the nodes, and the connecting lines show how they link to the master gateway; below each node its name, Agent count, and version are shown.',
        hint: 'Search "network topology" in the command palette (Ctrl+P) to open the fullscreen topology view and see node relationships more clearly.',
        target: '.lobby-node',
        placement: 'bottom',
      },
      {
        id: 'lobby-create',
        icon: '➕',
        title: 'Create an Agent',
        desc: 'Create an Agent with "➕" in the editor panel sidebar\'s Agent list (or press Ctrl+N), choosing the node, Agent type, and working directory; you can also double-click a node in the lobby to create directly on that node.',
        hint: 'Code Agents (hca) are good at reading code, editing code, and running verification; general Agents (hjb) suit analysis, planning, and execution. Long-press the main pet in the bottom-left to quickly create an Agent with a single sentence (Ctrl+Alt+N).',
        target: '.workspace-activity-bar',
        placement: 'bottom',
      },
      {
        id: 'lobby-quick-create',
        icon: '🐾',
        title: 'Create an Agent with one sentence',
        desc: 'Long-press the main pet in the bottom-left (or press Ctrl+Alt+N), type a one-sentence task description, and press Enter to create an Agent that starts executing immediately; everything except the task uses defaults, ideal for quickly kicking off a task.',
        hint: 'Long-pressing the main pet for about 0.6 seconds triggers it; when you need to customize the node, type, working directory, etc., use the full create window via "➕".',
        target: '.pet-float',
        placement: 'top',
      },
      {
        id: 'lobby-pet-menu',
        icon: '🖱',
        title: 'Pet context menu',
        desc: 'Right-click a pet to quickly view changes, view rules, view tools, create a terminal, open the editor, rename, duplicate, manage permissions, losslessly respawn, delete, and more, without opening a panel first.',
        hint: 'The menu matches the command palette\'s "Current Agent" group, plus "Add to group / Remove from group"; whichever pet is selected is the Agent it acts on.',
        target: '.lobby-pet',
        placement: 'bottom',
      },
      {
        id: 'lobby-node-menu',
        icon: '🖧',
        title: 'Node context menu',
        desc: 'Right-click a node in the lobby to create an Agent, open a terminal, update code, restart the service, or rename the node.',
        hint: 'Updating code and restarting the service affect the Agents running on that node; confirm before proceeding.',
        target: '.lobby-node',
        placement: 'bottom',
      },
    ]
  }

  // Agent scenario: shown after the first Agent is created
  function AGENT_TOUR_STEPS() {
    return [
      {
        id: 'agent-status',
        icon: '🚦',
        title: 'Agent status',
        desc: 'The colors on pets and panels indicate Agent status: running, waiting for input, waiting for confirmation, idle, stopped. When waiting for input it highlights to prompt you to handle it.',
        hint: 'The command palette\'s "Jump to Agent waiting for input" takes you straight to the pet that needs you most.',
        target: '.workspace-activity-bar',
        placement: 'bottom',
      },
      {
        id: 'agent-sidebar',
        icon: '📋',
        title: 'Agent list',
        desc: 'In the editor panel sidebar\'s Agent list you can view all Agents, multi-select, and browse by node or custom group.',
        hint: 'In the sidebar you can batch duplicate, batch delete, and add to groups; individual Agent rename/duplicate/manage permissions/lossless respawn/delete are in the command palette\'s (Ctrl+P) "Current Agent" group.',
        target: '.workspace-activity-bar',
        placement: 'bottom',
      },
      {
        id: 'agent-manage',
        icon: '🛠',
        title: 'Manage a single Agent',
        desc: 'In the command palette\'s (Ctrl+P) "Current Agent" group: rename changes the display name; duplicate builds another with the same config; manage permissions controls who can read and who can interact; lossless respawn rebuilds the process while keeping the session; delete removes it entirely.',
        hint: '"Lossless respawn" and "Manage permissions" are visible only to the Agent owner; "Human intervention" can interrupt the current Agent and take over at any time.',
        target: '.workspace-activity-bar',
        placement: 'bottom',
      },
      {
        id: 'agent-groups',
        icon: '🗂',
        title: 'Custom groups',
        desc: 'Once you have many Agents, use "Manage groups" in the editor sidebar to sort Agents into custom groups; groups can be collapsed, making it easy to organize by project or purpose.',
        hint: 'Stopped Agents are automatically removed from groups, avoiding a buildup of invalid entries.',
        target: '.workspace-activity-bar',
        placement: 'bottom',
      },
    ]
  }

  // Panel scenario: shown after the chat panel is first opened
  function PANEL_TOUR_STEPS() {
    return [
      {
        id: 'panel-input',
        icon: '💬',
        title: 'Chat in the panel',
        desc: 'The bottom of the panel is the input box: in single-line mode press Enter to send, in multi-line mode press Ctrl+Enter or Ctrl+D to send (Enter inserts a newline). The Agent\'s output streams in real time above.',
        hint: 'Hold the right Ctrl key for voice input.',
        target: '.session-panel',
        placement: 'top',
      },
      {
        id: 'panel-at-completion',
        icon: '@',
        title: 'Quick reference with @',
        desc: 'Typing @ in the input box pops up the completion list, letting you quickly reference four kinds of content: 📄 files (keep typing a file name to search), 📚 rules (built-in/file/YAML rules), ⚙️ built-in commands (e.g. Summary, Commit, Review), 📝 prompt templates (e.g. sdd/1.spec). Arrow keys to select, Enter to insert, Esc to cancel.',
        hint: 'Referencing a file brings its content to the Agent, saving manual pasting; referencing a rule temporarily loads the specified rule for this conversation. The pet lobby input box also supports @.',
        target: '.session-panel',
        placement: 'top',
      },
      {
        id: 'panel-confirm',
        icon: '✅',
        title: 'Confirmation card',
        desc: 'When an Agent needs your decision a confirmation bar pops up: press y to confirm, n to cancel, Enter to trigger the default option; while waiting for multi-line input you can press Ctrl+C to send the completion signal.',
        hint: 'The confirmation card stays within the panel and does not pop out to interrupt other Agents.',
        target: '.session-panel',
        placement: 'top',
      },
      {
        id: 'panel-context-menu',
        icon: '🖱',
        title: 'Panel context menu',
        desc: 'Right-click the empty area of a panel to view changes (diff), rules, and tools, and to open a terminal and code editor, inspecting the Agent\'s workspace at any time.',
        hint: 'These entries are also available in the command palette\'s (Ctrl+P) "Current Agent" group.',
        target: '.session-panel',
        placement: 'top',
      },
      {
        id: 'panel-layout',
        icon: '🪟',
        title: 'Close the panel',
        desc: 'Press Ctrl+W to close the panel with the current focus and return to the pet lobby; inside the editor you can split horizontally/vertically into multiple areas, each independently hosting files, sessions, terminals, or chat.',
        hint: 'Inside the editor press Ctrl+\\ to split horizontally and Ctrl+- to split vertically; after splitting, Ctrl+W closes the currently active area.',
        target: '.session-panel',
        placement: 'top',
      },
      {
        id: 'panel-auto',
        icon: '🔁',
        title: 'Auto-scroll and read aloud',
        desc: 'A panel can enable auto-scroll to keep the output following the latest content; it can also enable read-aloud to speak the Agent\'s replies.',
        hint: 'Both can be toggled at any time in the command palette\'s "Current Agent" group.',
        target: '.session-panel',
        placement: 'top',
      },
    ]
  }

  // Sidebar scenario: shown after first opening the Agent list view inside the editor
  function SIDEBAR_TOUR_STEPS() {
    return [
      {
        id: 'sidebar-list',
        icon: '📋',
        title: 'Agent list',
        desc: 'The editor sidebar lists all Agents by node and custom group, each item showing its type, name, status, and working directory; click to open it in the editor.',
        hint: 'Agents waiting for input blink to remind you to handle them promptly.',
        target: '.workspace-sidebar-agents',
        placement: 'right',
      },
      {
        id: 'sidebar-context-menu',
        icon: '🖱',
        title: 'Agent context menu',
        desc: 'Right-click any Agent item to view changes, create a terminal, open the editor, rename, duplicate, manage permissions, losslessly respawn, delete, and more, without opening a panel first.',
        hint: 'The menu matches the command palette\'s (Ctrl+P) "Current Agent" group and acts on the Agent you right-clicked.',
        target: '.workspace-sidebar-agents .agent-item',
        placement: 'right',
      },
      {
        id: 'sidebar-batch',
        icon: '☑',
        title: 'Batch operations',
        desc: 'Click "☑" at the top of the sidebar to enter batch selection mode, then check multiple Agents to batch duplicate, add to groups, or delete.',
        hint: 'Batch deletion cannot be undone; confirm the selected Agents before proceeding.',
        target: '.workspace-sidebar-agents',
        placement: 'right',
      },
      {
        id: 'sidebar-groups',
        icon: '📁',
        title: 'Manage groups',
        desc: 'Click "📁" at the top of the sidebar to rename or delete custom groups; groups can be collapsed, making it easy to organize Agents by project or purpose.',
        hint: 'Stopped Agents are automatically removed from groups, avoiding a buildup of invalid entries.',
        target: '.workspace-sidebar-agents',
        placement: 'right',
      },
      {
        id: 'sidebar-orchestrate',
        icon: '🧩',
        title: 'Orchestration: batch-create Agents',
        desc: 'Click "🧩" at the top of the sidebar, choose a node and an orchestration file (YAML) and parse it; an editable form is generated for each Agent in the file, and one click batch-creates them after you confirm.',
        hint: 'Each Agent can individually set its name, type, working directory, model group, target node, etc.; if a task description is filled in, the Agent executes on start (required in non-interactive mode).',
        target: '.workspace-sidebar-agents',
        placement: 'right',
      },
    ]
  }

  // Clear all tour flags (command palette "Reset onboarding tour"); entering the corresponding scenario next time triggers it again
  function resetOnboardingMarks() {
    try {
      const keys = []
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(ONBOARDING_KEY_PREFIX)) keys.push(key)
      }
      keys.forEach(key => localStorage.removeItem(key))
      localStorage.removeItem(LEGACY_ONBOARDING_KEY)
    } catch (err) {
      /* A read failure in private mode can be ignored */
    }
  }

  // Scenario trigger: skip when a tour is already in progress or this scenario has been seen; delay until the target element is mounted before showing
  function maybeStartTour(tourId) {
    if (activeTourId.value) return
    if (hasSeenTour(tourId)) return
    clearOnboardingTimer()
    onboardingTimer = setTimeout(() => {
      onboardingTimer = null
      if (activeTourId.value) return
      if (hasSeenTour(tourId)) return
      activeTourId.value = tourId
    }, ONBOARDING_AUTO_DELAY)
  }

  // Close/finish: record the current scenario as seen and dismiss
  function finishTour() {
    const tourId = activeTourId.value
    clearOnboardingTimer()
    if (tourId) markTourSeen(tourId)
    activeTourId.value = null
    if (tourId === 'welcome') showToast()('Guide complete, start using HaijunBot', 'success')
  }

  // Manually open the specified scenario tour (command palette); does not write the flag
  function startOnboarding(tourId = 'welcome') {
    clearOnboardingTimer()
    activeTourId.value = tourId
    // The sidebar scenario needs to open the editor and switch to the Agent list view first, otherwise the tour target is not visible
    if (tourId === 'sidebar') openWorkspaceAgentList()()
  }

  return {
    activeTourId,
    activeTourSteps,
    showOnboarding,
    maybeStartTour,
    finishTour,
    startOnboarding,
    resetOnboardingMarks,
    clearOnboardingTimer,
  }
}
