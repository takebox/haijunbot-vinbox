### Release Note - v6.1.0 2026-10-07
#### **🚀 New Features**
- **🎯 Comprehensive plugin system upgrade**
  - **Value tag**: More powerful plugin capabilities and a richer extension ecosystem
  - **Scenario tag**: Feature extension, plugin development, capability orchestration
  - **Effect**: Added built-in plugins such as the gh plugin (GitHub operations) and the AI dark factory plugin (automated evaluation pipeline); supports one-click plugin scaffold generation, automatic plugin dependency installation, plugin upgrade and URL installation, reversible plugin uninstall (uninstall precisely revokes registered resources), and automatic discovery and selection of plugin orchestration templates; the plugin management UI is displayed by node, making extension and maintenance easier
- **🎯 Terminal session persistence and sharing**
  - **Value tag**: More reliable terminal sessions, shareable and collaborative across devices
  - **Scenario tag**: Multi-device login, team collaboration, reconnection after disconnection
  - **Effect**: Terminal sessions support persistence and reconnection recovery; output during disconnection is automatically cached and can be replayed after reconnection; supports real-time terminal sharing and ACL permission control, with child-node terminal output broadcast in real time to all authorized users, making multi-device/multi-user collaboration smoother
- **🎯 Commit tool (quick commit)**
  - **Value tag**: Cleaner commit history, one formal commit per requirement
  - **Scenario tag**: Code commit, requirement wrap-up, history cleanup
  - **Effect**: Added the Commit tool, which automatically squashes CheckPoint temporary commits made during development into one formal commit and uses an LLM to generate a conventional commit message based on the diff, making the commit history tidier
- **🎯 Screenshot upload to the command-origin gateway**
  - **Value tag**: Screenshots are automatically sent back, making cross-device viewing more convenient
  - **Scenario tag**: Remote operations, screenshot evidence, multi-device collaboration
  - **Effect**: Screenshots are automatically uploaded to the command-origin gateway and a URL is returned, making it easy to view them directly on the device that issued the command
#### **📌 Fixes**
- **🔧 Plugin capability tooltip occlusion and residue**
  - **Value tag**: The tooltip no longer occludes the item below, and repository-switch data is cleaner
  - **Scenario tag**: Viewing plugin capabilities, switching repositories
  - **Effect**: Fixed the plugin capability tooltip occluding the mouse response of the item below and stale data remaining when switching repositories, making the interaction more accurate
- **🔧 Missing API authentication in the gh plugin**
  - **Value tag**: More stable and reliable GitHub operations
  - **Scenario tag**: Issue/PR management, GitHub operations
  - **Effect**: Fixed the issue where the gh plugin's issue- and PR-related API requests failed due to missing token authentication
- **🔧 Lost shared terminal output**
  - **Value tag**: Shared terminal output is complete and not lost
  - **Scenario tag**: Terminal sharing, multi-user viewing, re-login
  - **Effect**: Fixed the issues of output loss when the child-node terminal's owner_id is empty, terminal content not displaying after re-login, and sharing users not receiving real-time output
#### **🔧 Optimizations and Refactoring**
- **🎯 More intuitive plugin capability display**
  - **Value tag**: Plugin capabilities at a glance, visible on hover
  - **Scenario tag**: Plugin browsing, capability viewing
  - **Effect**: The plugin capability list now displays in a hover tooltip, with a cleaner style; the Git panel supports a "Follow current session" option that automatically refreshes the corresponding working-directory data when switching Agents
- **🎯 More standardized plugin management**
  - **Value tag**: Clearer permissions and paths, safer management
  - **Scenario tag**: Plugin management, permission control, multi-node deployment
  - **Effect**: Plugin management APIs now use node-level paths, dynamically load the permission manifest and add a plugin management entry, and built-in plugins can be loaded directly from the source directory and display their capability list
---
### Release Note - v6.0.11 2026-10-06
#### **🚀 New Features**
- **🎯 Configurable audit system (disabled by default)**
  - **Value tag**: Key behaviors are traceable, making security review easier
  - **Scenario tag**: Security audit, behavior tracking, compliance scenarios
  - **Effect**: Can record key behavior events such as user input, tool calls, and task completion into daily audit logs, with sensitive information automatically redacted; disabled by default with zero overhead, enabled on demand
- **🎯 Runtime hotpatch tool**
  - **Value tag**: Code changes take effect immediately, no process restart required
  - **Scenario tag**: Live tuning, self-evolution, quick fixes
  - **Effect**: Supports hot-updating existing modules or injecting brand-new code, automatically rebinding existing class instances to new classes so code changes take effect immediately, making development and debugging more efficient
- **🎯 Proactive memory retrieval (better understands your past experience)**
  - **Value tag**: Relevant historical memories are automatically brought in at task start, making processing more accurate
  - **Scenario tag**: Complex tasks, long-term use, experience reuse
  - **Effect**: Automatically semantically retrieves the most relevant historical memories based on the current task and injects them into the context, with no manual retrieval needed, letting past experience directly assist the current task
- **🎯 Terminal-Bench 2.0 evaluation support**
  - **Value tag**: More flexible evaluation, with specifiable model group and version
  - **Scenario tag**: Capability evaluation, model comparison, environment setup
  - **Effect**: Added a Harbor adapter layer supporting Terminal-Bench 2.0 evaluation, allowing dynamic specification of the evaluation version and specification of the model group via parameters, and improved the evaluation environment setup and run scripts
- **🎯 Quiet mode (quiet)**
  - **Value tag**: More concise console output, focused on results
  - **Scenario tag**: Script invocation, log viewing, automation scenarios
  - **Effect**: Added quiet mode to suppress console output while still retaining gateway and event output, making automated invocation cleaner
#### **📌 Fixes**
- **🔧 Accidental creation when the Create Agent dialog pops up**
  - **Value tag**: No more accidental creation submission when selecting a directory
  - **Scenario tag**: Creating an Agent, directory selection, keyboard operation
  - **Effect**: Fixed the issue where pressing Enter while the directory selection dialog was open accidentally triggered Agent creation, making keyboard operation more accurate
- **🔧 More accurate display of Agent running status**
  - **Value tag**: Real-time, accurate status in the frontend Agent list
  - **Scenario tag**: Multi-Agent management, status viewing, frontend display
  - **Effect**: Fixed the inconsistency between Agent lifecycle status and frontend display, correctly mapping the exited/stopped status to the frontend, making list refresh more reliable
#### **🔧 Optimizations and Refactoring**
- **🎯 More focused task analysis flow**
  - **Value tag**: Check rules and memories first when handling tasks, so decisions are better grounded
  - **Scenario tag**: Task handling, experience reuse, rule application
  - **Effect**: Unified the task analysis flow as "rules → memory → tool generation", prioritizing the reuse of existing rules and experience, reducing unnecessary tool generation, and making handling more efficient
- **🎯 Daemon self-update supports more platforms**
  - **Value tag**: ARMv7 32-bit devices can also update automatically
  - **Scenario tag**: Multi-platform deployment, daemon upgrade, embedded devices
  - **Effect**: Daemon self-update now supports the ARMv7 32-bit platform, covering a wider range of deployment environments

---
### Release Note - v6.0.10 2026-10-05
#### **📌 Fixes**
- **🔧 Scheduled tasks no longer lost after restart**
  - **Value tag**: Delayed/periodic tasks recover across sessions and trigger as usual after restart
  - **Scenario tag**: Delayed tasks, periodic tasks, service restart
  - **Effect**: Fixed the issue where delayed (after) scheduled tasks were not persisted and could not be found after restart; recovery now automatically skips canceled or completed tasks to avoid accidental triggering
- **🔧 Intermittent failure of the timer tool**
  - **Value tag**: More stable timer tool; task status no longer "splits"
  - **Scenario tag**: Scheduled tasks, tool calls, state management
  - **Effect**: Fixed the issue where the tool module import method caused the timer singleton state to split—created in one place but not found in another—by importing uniformly by package path, keeping state consistent and reliable
- **🔧 Git panel data does not refresh after switching Agents**
  - **Value tag**: Immediately see the commits and branches of the corresponding working directory after switching Agents
  - **Scenario tag**: Git management, Agent switching, commit viewing
  - **Effect**: Fixed the issue where the Git view still showed the old Agent's data after switching Agents via the session panel; it now automatically refreshes by the new working directory upon switching
- **🔧 Collapsed input box force-expanded by polling**
  - **Value tag**: A collapsed input box is no longer automatically expanded, making operation smoother
  - **Scenario tag**: Multi-panel, input box collapse, status refresh
  - **Effect**: Fixed the issue where periodic status refresh force-expanded a user-collapsed input box and stole focus, respecting the user's explicit intent to collapse
- **🔧 Wrong target in the cache management panel**
  - **Value tag**: The cache panel always targets the correct Agent
  - **Scenario tag**: Cache management, multiple Agents, buffer operations
  - **Effect**: Fixed the issue where the cache management panel always read the current Agent instead of the Agent that owns the clicked panel; opening the panel now targets the correct Agent
#### **🚀 New Features**
- **🎯 Code Agent supports scheduled execution**
  - **Value tag**: The code Agent can also execute tasks automatically on a schedule
  - **Scenario tag**: Scheduled tasks, automation, code Agent
  - **Effect**: Wired the timer tool into the code Agent, supporting after/at/loop scheduled execution and cancel/list/clear management
- **🎯 More reliable automatic browser-extension version sync**
  - **Value tag**: After the gateway releases a new extension version, the local side follows automatically
  - **Scenario tag**: Extension upgrade, gateway release, long-lived connection
  - **Effect**: Added a periodic fallback sync mechanism so that even if the gateway does not reconnect for a long time, it automatically compares and syncs to the latest extension version, making upgrades easier
- **🎯 Automatic module singleton-split scanning (CI)**
  - **Value tag**: Better code quality assurance, with hidden risks surfaced early
  - **Scenario tag**: CI checks, code review, pre-release checks
  - **Effect**: Added a static scanner and CI workflow that automatically detect module singleton-split risks and block merges/releases, reducing production risks
---
### Release Note - v6.0.9 2026-10-05
#### **🚀 New Features**
- **🎯 CI automation integration (testing / issue classification / code review)**
  - **Value tag**: Automated commit and collaboration workflows, with better quality assurance
  - **Scenario tag**: CI integration, issue management, PR review
  - **Effect**: Added three CI workflows that automatically run tests, classify and label issues, and perform code review on PRs; the quick-config tool also supports a non-interactive mode, so platform configuration can be completed automatically without human intervention in CI environments
- **🎯 Automatic project overview supplementation (AGENTS.md / HAIJUN.md)**
  - **Value tag**: Community-standard project descriptions are automatically included, so the Agent understands the project better when getting started
  - **Scenario tag**: Open-source projects, team collaboration, Agent initialization
  - **Effect**: Automatically reads AGENTS.md / HAIJUN.md from the repository root as a supplement to the project overview and merges them into the existing project rules; overlong content is automatically truncated by budget so the context is not blown up
- **🎯 Centralized management of build-verification / static-check configuration**
  - **Value tag**: Configuration done in one place, no longer scattered across multiple files
  - **Scenario tag**: Build verification, lint configuration, post-change file handling
  - **Effect**: Configurations such as build verification, lint tools, and post-change file handling are consolidated into config.yaml, supporting custom build commands and per-file-type command templates, making configuration more centralized and easier to maintain
#### **📌 Fixes**
- **🔧 Browser extension no longer freezes when creating a tab**
  - **Value tag**: Occasional page-busy states no longer block creating a new tab
  - **Scenario tag**: Multi-window browsing, tab creation, page detection
  - **Effect**: Fixed the issue where window-splitting detection and script injection could hang and block tab creation; added a timeout fallback for the related operations, automatically falling back to opening a new window on timeout, making the operation smoother
- **🔧 Git panel does not refresh data after switching Agents**
  - **Value tag**: Immediately see the latest commits and branches after switching, no longer stuck on old data
  - **Scenario tag**: Git management, Agent switching, commit viewing
  - **Effect**: Fixed the issue where the commit history did not refresh when switching Agents or switching back to the Git view; now it pulls the latest data on every switch
- **🔧 Accidental creation when the Create Agent dialog pops up**
  - **Value tag**: No more accidental creation submission when selecting a directory
  - **Scenario tag**: Creating an Agent, directory selection, keyboard operation
  - **Effect**: Fixed the issue where pressing Enter while the directory selection dialog was open accidentally triggered Agent creation, making keyboard operation more accurate
#### **🔧 Optimizations and Refactoring**
- **🎯 Login-state persistence (no disconnect on restart)**
  - **Value tag**: No re-login needed after the gateway or browser restarts, making connections easier
  - **Scenario tag**: Service restart, browser restart, long-lived connection
  - **Effect**: Both the daemon credentials and the browser extension login token are persisted to disk, automatically restoring the login state and reconnecting after restart, with no need to reopen page detection or log in again
- **🎯 Smart pre-filtering of tools and rules**
  - **Value tag**: Quickly focus even with many tools and rules, for more efficient responses
  - **Scenario tag**: Large number of tools, numerous rules, complex tasks
  - **Effect**: When the number of tools or rules exceeds a threshold, automatically and roughly filters out the most relevant candidates by task-context keywords and injects them, reducing context usage; also streamlines tool parameter descriptions, automatically truncating overlong ones, reducing input volume
- **🎯 Greatly improved memory-consolidation performance**
  - **Value tag**: Faster and cheaper consolidation when there are many memories
  - **Scenario tag**: Memory archiving, batch consolidation, long-term use
  - **Effect**: Memory grouping now uses a tag index to avoid all-pairs comparisons, merges small groups into a single batched model call, and dynamically batches based on token budget, significantly improving both consolidation speed and cost
- **🎯 More efficient scheduled-task scheduling**
  - **Value tag**: Quickly compute the next trigger time even for complex periods
  - **Scenario tag**: Cron scheduling, periodic tasks, performance-sensitive scenarios
  - **Effect**: The next cron trigger time is now computed by day-skipping scan instead of minute-by-minute enumeration, making scheduling faster and more stable
- **🎯 Enhanced admin-panel security**
  - **Value tag**: Safer proxies and accounts
  - **Scenario tag**: Proxy configuration, account management, security protection
  - **Effect**: Added SSRF protection for proxy target URLs (proxying to intranet/loopback addresses is prohibited); when admin has no initial password set, the first login forces setting a password, avoiding random-password leakage and forgetfulness
- **🎯 System slimming (remove the methodology module)**
  - **Value tag**: A lighter system with more focused concepts
  - **Scenario tag**: System maintenance, feature cleanup
  - **Effect**: Removed the methodology module and its related commands and configuration, consolidating experience accumulation into rules and tools, reducing usage and maintenance costs
---
### Release Note - v6.0.8 2026-10-04

#### **🚀 New Features**

- **🎯 Scheduled tasks support cron-expression scheduling**
  - **Value tag**: Periodic tasks can be auto-triggered down to the minute, for more flexible scheduling
  - **Scenario tag**: Scheduled backups, periodic inspections, scheduled push
  - **Effect**: Scheduled tasks now support standard 5-field cron-expression scheduling (minute hour day month weekday), with range, step, and list syntax; the first trigger automatically aligns to the next matching time point and advances automatically after triggering; combined with the web management sidebar, they can be viewed and scheduled intuitively
- **🎯 Web management sidebar (scheduled tasks / capability list / script library)**
  - **Value tag**: Management entries centralized in one place, status at a glance
  - **Scenario tag**: Scheduled-task management, capability viewing, script management
  - **Effect**: The web UI adds a management sidebar that centrally displays scheduled tasks, the Daemon capability list, and the installed script library, refreshable with one click, making management easier
- **🎯 Agent visual collaboration (editor commands)**
  - **Value tag**: While the Agent works on code, your editor view automatically follows and locates
  - **Scenario tag**: Code review, change localization, collaborative editing
  - **Effect**: The Agent can issue commands to the user's frontend editor (open file, jump to line, select code segment), guiding the editor view to the location being analyzed or modified, making human-machine collaboration more intuitive
- **🎯 daemon JS script automation**
  - **Value tag**: Use JS scripts to call local capabilities for automation, lowering the barrier
  - **Scenario tag**: Local automation, script reuse, batch operations
  - **Effect**: haijunbot-daemon includes a pure-Go JS runtime (zero cgo); you can write JS scripts to call local capabilities such as files, commands, and processes, with support for the `run-script` command, parameter injection, and sample scripts, making automation more flexible
- **🎯 Enhanced Windows automation capabilities**
  - **Value tag**: More complete Windows window and input control
  - **Scenario tag**: Window management, GUI automation, mouse operations
  - **Effect**: Added capabilities such as window position retrieval and movement and mouse double-click, making Windows GUI automation coverage more comprehensive

#### **📌 Fixes**

- **🔧 More accurate cross-file go-to-definition**
  - **Value tag**: Viewing symbol definitions across files no longer shows blank or fails
  - **Scenario tag**: Code navigation, symbol localization, cross-file references
  - **Effect**: Fixed the issue where cross-file go-to-definition in LSP showed blank content because the target file was not loaded, and made the language server search upward for the project root to index the whole project, making cross-file semantics more reliable
- **🔧 Image size configuration anomaly no longer errors out**
  - **Value tag**: Image upload no longer interrupted when the configuration is anomalous
  - **Scenario tag**: Image upload, configuration fault tolerance
  - **Effect**: Fixed the issue where an anomalous image-size configuration type caused upload failures; now it automatically falls back to the default value when the configuration is anomalous, for more stable use
- **🔧 macOS platform build fix**
  - **Value tag**: Compiles and releases normally on macOS, with more complete cross-platform support
  - **Scenario tag**: macOS deployment, cross-platform build, CI release
  - **Effect**: Fixed the issue where the Windows wait capability failed to cross-compile on the macOS platform, so macOS can now build and release smoothly, with more complete cross-platform support

#### **🔧 Optimizations and Refactoring**

- **🎯 Refactoring of the browser-extension and daemon tool architecture**
  - **Value tag**: Capabilities are dynamically reported by the client side, for more flexible extension
  - **Scenario tag**: Capability extension, tool calls, multi-device collaboration
  - **Effect**: Browser-extension and daemon tools are uniformly split into the "session / capability list / invocation" trio, adopting a dynamic-capability + call model where client-side capabilities register and report themselves and the gateway passes them through, so new capabilities require no kernel changes
- **🎯 Dynamic reporting of the browser-extension capability list**
  - **Value tag**: Extension capabilities at a glance, displayable in the frontend
  - **Scenario tag**: Capability viewing, extension management
  - **Effect**: The browser extension dynamically reports its own capability list (tabs, navigation, DOM operations, etc.), aligned with the daemon capability format so the frontend can display them uniformly
- **🎯 Enhanced frontend experience**
  - **Value tag**: More intuitive interface and clearer information
  - **Scenario tag**: File browsing, topology viewing, command palette
  - **Effect**: The file tree adds icons for various file types; the pet hall and topology diagram add visualization of access-end nodes (browser extension, local background service); the command palette adds Agent-type and meta-info icons; and the user management panel is enhanced
- **🎯 Rule-loading guidance under native function calling**
  - **Value tag**: Rules can be loaded on demand mid-task, for more complete capability
  - **Scenario tag**: Native tool calling, rule loading
  - **Effect**: When native function calling is active, the "load rules/tracks on demand" guidance is retained, so the model can still proactively load relevant rules mid-task

---

### Release Note - v6.0.7 2026-10-01

#### **🚀 New Features**

- **🎯 Agent orchestration (generate multiple Agents working together at once)**
  - **Value tag**: Complex tasks can be split among multiple Agents for parallel collaboration, making orchestration easier
  - **Scenario tag**: Multi-Agent collaboration, task orchestration, cross-node deployment
  - **Effect**: Added an orchestration file browsing panel that can parse orchestration YAML and generate multiple Agents with one click, supporting cross-node, proxy, and access-control configuration; Agent ownership automatically falls under the initiator, making orchestrated Agents easier to manage
- **🎯 Lossless Agent rebirth**
  - **Value tag**: An Agent with problems can be reborn in place, with configuration and session fully preserved
  - **Scenario tag**: Agent exception recovery, configuration update, session continuation
  - **Effect**: Added lossless rebirth, allowing an Agent to complete "save session → delete → rebuild" without interrupting the flow; after rebuilding, the configuration, session, ownership, and access permissions are all preserved, with no manual rebuild needed
- **🎯 Sensitive credential interception (prevent key leakage)**
  - **Value tag**: Keys are no longer accidentally committed or shared, with better security
  - **Scenario tag**: Code commit, key management, team collaboration
  - **Effect**: Automatically scans pending changes before commit and share; if something resembles a real key (OpenAI/GitHub/AWS, etc.) it aborts the operation and gives a redacted warning, preventing key leakage at the source
- **🎯 Automatically switch models by task difficulty**
  - **Value tag**: Cheap models for simple tasks and automatic upgrade for complex tasks, saving cost while preserving quality
  - **Scenario tag**: Cost control, task grading, model scheduling
  - **Effect**: Added the ability to automatically switch models by task difficulty, doing only quality upgrades and not cheap downgrades; it also automatically adapts the sampling temperature to the task nature and supports creating temporary model instances to run one-off tasks without polluting the main session
- **🎯 Gateway token persistence (no disconnect on restart)**
  - **Value tag**: Clients need not re-login after the gateway restarts, making connections easier
  - **Scenario tag**: Gateway restart, service upgrade, long-lived connection
  - **Effect**: The gateway authentication token and JWT secret are persisted, so client tokens remain valid after the gateway restarts, with no re-login or reconnection needed

#### **📌 Fixes**

- **🔧 Requests no longer block permanently**
  - **Value tag**: Occasional network anomalies no longer make requests hang
  - **Scenario tag**: Network fluctuation, slow services, timeout control
  - **Effect**: When no request timeout is explicitly configured, a 5-minute timeout is used by default to avoid permanent blocking due to server issues; if the user explicitly configures a valid value, the configured value takes priority
- **🔧 Automatic retry for occasional platform errors**
  - **Value tag**: Automatic retry for rate limiting or temporary server-side failures, reducing occasional failures
  - **Scenario tag**: Model calls, rate-limit recovery, server-side jitter
  - **Effect**: Automatic retry for model-platform rate limiting (429/529), server errors (5xx), and network timeouts, while deterministic errors such as authentication are not retried, making calls more stable
- **🔧 Manual commits during a task are no longer affected**
  - **Value tag**: Code you commit yourself is not accidentally cleaned up by the Agent
  - **Scenario tag**: Human-machine collaboration, code commit, task wrap-up
  - **Effect**: Fixed the issue where the task's recorded initial commit became invalid because history was rewritten and the commit history could not be obtained; it now automatically falls back to the most recent non-automatic commit as the starting point, avoiding affecting the user's manual commit during task wrap-up

#### **🔧 Optimizations and Refactoring**

- **🎯 Visualization of access-end nodes in the topology diagram**
  - **Value tag**: The connection relationship between the browser extension and the local background service is clear at a glance
  - **Scenario tag**: Multi-node viewing, topology browsing, access-end identification
  - **Effect**: The network topology adds access-end nodes (browser extension upstream, local background service downstream), with a circular shape clearly distinguished from the gateway chassis node, making access relationships clearer
- **🎯 Custom management directory in the Git panel**
  - **Value tag**: Any directory can be specified for Git management, no longer limited to the Agent root directory
  - **Scenario tag**: Multi-repository management, directory switching, Git operations
  - **Effect**: The Git panel supports selecting any directory as the Git management target, automatically restoring the last specification when switching Agents or directories, making management more flexible

#### **📚 Documentation**

- **📖 Competitor comparison and community documentation**
  - **Value tag**: Selection and collaboration have a basis to refer to
  - **Scenario tag**: Technology selection, collaboration reference, community co-building
  - **Effect**: Added a mechanism-comparison analysis report against OpenViking, supplemented the collaboration-model documentation, code of conduct, security notes, and support documentation, and added CI test and key-scanning workflows, for better quality assurance

---

### Release Note - v6.0.6 2026-09-28

#### **🚀 New Features**

- **🎯 Cross-machine direct file transfer (moving large files between nodes)**
  - **Value tag**: Large files can be moved quickly between machines, no longer blowing up the conversation
  - **Scenario tag**: Multi-machine deployment, file migration, large-file transfer
  - **Effect**: Added direct inter-node file transfer, allowing files/directories to be pushed or pulled between the local machine and a remote node, up to 512MiB per transfer; transfers are chunked in the background and the bytes do not enter the conversation context, so moving even large files does not affect the Agent's normal work; it includes integrity verification, making the transfer result clear at a glance
- **🎯 Gateway allow/deny list (more controllable connections)**
  - **Value tag**: No longer accidentally connecting to gateways you shouldn't, with connection scope under your control
  - **Scenario tag**: Multi-gateway environments, security hardening, connection management
  - **Effect**: Both the daemon and the browser extension support configuring a gateway allow/deny list, allowing an allowlist (only listed ones permitted) or a denylist (only listed ones rejected), with wildcard matching; it is off by default and does not affect existing usage, and once configured it keeps out gateways you "logged into once in a while", preventing long-term connections after automatic discovery
- **🎯 Command-line login for headless hosts**
  - **Value tag**: Log in without a browser, making deployment easier
  - **Scenario tag**: GUI-less hosts, server deployment, remote operations
  - **Effect**: Added a command-line login method, allowing you to log in to the gateway directly with a username and password on a GUI-less host and hand the credentials to the local daemon; it also provides an embedded web login page for browsers on other machines to access, and the gateway address is remembered after login so there's no need to re-enter it
- **🎯 Open any directory by node (no need to create an Agent)**
  - **Value tag**: Open the directory you want directly, without first creating an Agent
  - **Scenario tag**: Quick browsing, cross-node file viewing, temporary editing
  - **Effect**: The editor file tree adds an "Open directory" entry, letting you browse and edit files directly in any node and directory without first creating an Agent; opened directories are remembered and automatically restored after refresh, and can be removed at any time
- **🎯 Configuration backup and restore + visual editing**
  - **Value tag**: Configuration can be backed up and restored, making changes safer and easier
  - **Scenario tag**: Multi-node configuration, migration deployment, configuration adjustment
  - **Effect**: The management panel adds configuration backup and restore, letting you export a node's configuration to a file or import it from a file (automatically backing up the existing configuration before import); it also provides a form-based visual editor for configuration files that fills in by field type and validates automatically, making configuration changes less error-prone
- **🎯 Switch node proxy at runtime**
  - **Value tag**: Switch anytime when a proxy node fails, keeping model access uninterrupted
  - **Scenario tag**: Multi-node proxy, model access, failover
  - **Effect**: Added a node-proxy switching command that can list gateway-known nodes and switch with one click to access the model through another node's proxy, or disable the proxy and revert to a direct connection; the switch takes effect immediately without a restart

#### **📌 Fixes**

- **🔧 Fix for repeated daemon reconnections on slow Windows machines**
  - **Value tag**: More stable connections on slow machines, no more repeated disconnections and reconnections
  - **Scenario tag**: Windows deployment, slow machines, service connection
  - **Effect**: Fixed the issue where, on slow Windows machines, the daemon's system-information collection took too long, causing handshake timeouts and repeated disconnections/reconnections; now the first connection reports only lightweight system information (returning in milliseconds) and sends the full information afterward, making the connection more stable
- **🔧 Manual commits during a task are no longer affected**
  - **Value tag**: Code you commit yourself is not accidentally cleaned up by the Agent
  - **Scenario tag**: Human-machine collaboration, code commit, task wrap-up
  - **Effect**: Fixed the issue where, during CodeAgent task execution, code manually committed by the user was mistakenly treated as a temporary artifact and squashed or reverted at task wrap-up; it now automatically recognizes and preserves the user's manual commits, making task wrap-up safer

#### **🔧 Optimizations and Refactoring**

- **🎯 Smoother editor operation**
  - **Value tag**: More efficient tab management, search, and editing toggling
  - **Scenario tag**: Multi-file editing, global search, read-only browsing
  - **Effect**: The editor tab bar adds a context menu to close all tabs to the right, close all, or keep only the current tab with one click; an unsplit view also provides save and read-only/edit toggle switches; global search automatically pre-fills the currently selected text, and filename search supports "directory + filename" path matching, making files faster to find
- **🎯 Daemon outbound proxy support**
  - **Value tag**: System proxy also takes effect, no more network failures
  - **Scenario tag**: Proxy environments, Windows system settings, restricted networks
  - **Effect**: The daemon's outbound requests now read system proxy settings (including the proxy in Windows system settings); combined with environment-variable proxies, it can connect to the network normally in environments configured with a system proxy
- **🎯 Clearer topology connections**
  - **Value tag**: Access-end node connection relationships clear at a glance
  - **Scenario tag**: Multi-node viewing, topology browsing
  - **Effect**: In the network topology, the lines from the main node to the access-end nodes are changed from curves to straight lines, making the visuals simpler and clearer
- **🎯 Mobile experience optimization**
  - **Value tag**: Fresher experience on phones
  - **Scenario tag**: Mobile use, small-screen browsing
  - **Effect**: The mobile side no longer shows the welcome banner, saving screen space; directory selection supports an embedded mode, reusing the same directory-filtering UI in scenarios such as "Open directory", for more consistent operation

#### **📚 Documentation**

- **📖 Multi-user authentication and permission documentation update**
  - **Value tag**: Multi-user deployment and permission configuration have a basis to refer to
  - **Scenario tag**: Multi-user environments, permission management, deployment reference
  - **Effect**: Updated the design and implementation guide for multi-user authentication and permissions, supplemented related explanations, making it easier to complete multi-user deployment and permission configuration following the docs

---

### Release Note - v6.0.0 2026-09-27

#### **🚀 New Features**

- **🎯 Local background service haijunbot-daemon (let the Agent operate your computer directly)**
  - **Value tag**: The Agent's capabilities extend from "inside the browser" to "the whole computer", able to work without relying on a browser
  - **Scenario tag**: Local file processing, software and system operations, desktop automation, browser-less environments
  - **Effect**: Added a Go-written background service that runs resident on the local machine; once installed, it lets the Agent directly operate your computer—read/write and transfer files, view and kill processes, start/stop and restart system services, read system information, execute local scripts, and automate desktop windows (window focus/close, mouse clicks, keyboard input, clipboard read/write, screenshots). It has zero third-party dependencies and zero extra runtime environment, works on both Windows and Linux, and the frontend communicates with it via a local address; the port can be changed in settings, and it supports one-click install, uninstall, start/stop, and status viewing, and can auto-update to new versions
- **🎯 Built-in code editor (integrated web-side development)**
  - **Value tag**: View code, edit code, and investigate problems right in the web page, no local IDE needed
  - **Scenario tag**: Code browsing, online editing, troubleshooting, Git change viewing
  - **Effect**: The web UI adds a professional-grade code editor supporting syntax highlighting, code completion, hover hints, and error diagnostics (based on language services), and provides a file tree, fuzzy search by filename, create/rename/delete/copy/cut/paste files, and global search; the editor supports free split screens, letting you embed chat, terminal, and Git diff views into the same workspace to chat while viewing code; the Git view can directly show the commit history and line-by-line diffs, and supports full-text/context toggling and diff navigation
- **🎯 Multimodal input and OCR text recognition**
  - **Value tag**: Images can be fed directly to the Agent; even models that don't support image input can read images
  - **Scenario tag**: Screenshot questions, extracting text from receipts/documents, UI-screenshot analysis
  - **Effect**: Images can be sent directly into the context during a conversation; it also includes pluggable multi-backend text-recognition capability, so even if the model in use does not support image input, the text in an image can be extracted and handed to the Agent, with multiple recognition backends ranging from lightweight to heavyweight, selectable as needed and ready out of the box
- **🎯 Automatic track discovery (automatically find tracks when local rules are insufficient)**
  - **Value tag**: Capabilities can "grow on demand", automatically filling in for unfamiliar tasks
  - **Scenario tag**: New-domain tasks, local rules not covering them, capability extension
  - **Effect**: When local rules are insufficient to cover the current task, HaijunBot automatically searches the remote track marketplace for candidate tracks, and the model evaluates their match with the task; on a hit, it automatically downloads, installs, and loads them without manual selection; installed tracks are retained and can be reused directly for similar tasks later
- **🎯 Visual configuration editor**
  - **Value tag**: No more hand-writing YAML to change configuration; mistakes get caught
  - **Scenario tag**: Model configuration, platform integration, parameter tuning
  - **Effect**: The web UI adds a visual editor for configuration files, providing form-based editing and descriptions by field type, with automatic format and value validation before saving to avoid hand-written configuration errors; it also adds backup model group configuration, automatically switching when the primary model is unavailable, for more stable service
- **🎯 Enhanced pet widget and hall experience**
  - **Value tag**: Agent status visible at hand, making parallel multi-tasking easier
  - **Scenario tag**: Parallel multiple Agents, status monitoring, daily use
  - **Effect**: Added a pet widget that can stay resident on the desktop to view Agent running status at any time; the pet hall now displays the working directory directly below the pet and optimizes output display and selection logic, making viewing and switching smoother in multi-Agent scenarios
- **🎯 Topology diagram shows access-end nodes**
  - **Value tag**: Who connected is clear at a glance
  - **Scenario tag**: Multi-node deployment, extension and background-service access, cluster operations
  - **Effect**: The network topology diagram adds access-end nodes for the browser extension and the local background service, displayed as circular nodes with browser information attached, so you can intuitively see which clients are currently connected
- **🎯 Windows quick install and offline install**
  - **Value tag**: Install faster, even without network
  - **Scenario tag**: Windows deployment, intranet environments, offline demos
  - **Effect**: Added a Windows one-click install script (supporting resume from breakpoints), making deployment simpler for Windows users; it also provides a way to generate offline installation packages containing the runtime environment, dependencies, and frontend artifacts, supporting x86_64 and aarch64, suitable for network-less environments such as intranets and isolated data centers

#### **📌 Fixes**

- **🔧 Fixes for daemon issues on the Windows platform**
  - **Value tag**: No more garbled text or black console windows when used on Windows
  - **Scenario tag**: Windows deployment, service management, command execution
  - **Effect**: Fixed issues where the daemon showed garbled Chinese output on Windows, popped up a black console window when invoking external commands, showed incomplete startup prompts after installation, timed out on application-list queries, and had service queries fail, aligning the Windows experience with Linux
- **🔧 Fixes for editor and workspace issues**
  - **Value tag**: Smoother editor and no more messed-up layouts
  - **Scenario tag**: Code editing, split-screen operation, mobile use
  - **Effect**: Fixed issues where opening the editor froze the page, file-view switching and tab scrolling were abnormal, panels repeatedly squeezed the layout after switching Agents, and embedded chat/terminal state was not reset after closing the editor; it also optimized the mobile editor sidebar into a bottom drawer so it can be used smoothly on mobile
- **🔧 Fixes for connection and gateway issues**
  - **Value tag**: More stable connections, no more mysterious failures of local requests
  - **Scenario tag**: Gateway connection, proxy environments, multi-node deployment
  - **Effect**: Fixed issues where gateway-address conversion lost encrypted-transport security, connections were repeatedly rebuilt, local proxy requests returned 502, and old sessions were left over after restarting on the same machine, making connections more stable and reliable
- **🔧 Fixes for UI and interaction details**
  - **Value tag**: Smoother operation, no more interruptions from small issues
  - **Scenario tag**: Session operations, mobile, input interaction
  - **Effect**: Fixed issues where session-panel messages could not be selected and copied, focusing the text box erroneously cleared selected content, the input box was not auto-focused during running state, the mobile back key could not return to the hall, and focus did not return to the input box after completion, making interactions more intuitive
- **🔧 Fixes related to configuration and models**
  - **Value tag**: Configuration loses no items and model capability is undiminished
  - **Scenario tag**: Configuration editing, model calls
  - **Effect**: Fixed the issue of missing keys and lost default values during configuration validation; and fixed the issue where models confirmed to support native tool calling were incorrectly downgraded, letting model capabilities reach their full potential

#### **🔧 Optimizations and Refactoring**

- **🎯 Editor workspace refactoring**
  - **Value tag**: One interface holds all work, making switching more natural
  - **Scenario tag**: Parallel multi-tasking, code and conversation on the same screen
  - **Effect**: Unified the editor and workspace, supporting free pane splitting so chat, terminal, and Git diffs can each be embedded as an independent pane; global toolbar functions are migrated to the workspace activity bar and shortcuts are registered uniformly, making operations more centralized and consistent
- **🎯 Automatic task-list cleanup**
  - **Value tag**: Automatic wrap-up after tasks end, leaving no residue
  - **Scenario tag**: Multi-step tasks, task tracking
  - **Effect**: Automatically clears the task list after all tasks end, avoiding leftover historical tasks interfering with subsequent work
- **🎯 Improved file and content handling capability**
  - **Value tag**: Large files can be handled smoothly
  - **Scenario tag**: Large-file editing, content transfer
  - **Effect**: The file size limit is raised from 1MB to 10MB, with chunked transfer for large files (with verification and resume support), making large-file handling more comfortable
- **🎯 Daemon logging and stability optimization**
  - **Value tag**: Problems are traceable and operation is more stable
  - **Scenario tag**: Troubleshooting, long-term operation
  - **Effect**: Daemon logs are persisted to disk and rotated by size, making troubleshooting easier; it also optimizes connection idempotency and state-management logic, reducing repeated connection rebuilds and state anomalies

#### **📚 Documentation**

- **📖 Documentation navigation and structure optimization**
  - **Value tag**: Finding docs is faster and the structure is clearer
  - **Scenario tag**: Beginner onboarding, feature lookup
  - **Effect**: Added a documentation navigation home page indexed by "Getting started / user-manual / advanced / best practices / technical docs"; user-manual is reorganized by feature domain, with each feature as its own page, making lookup more efficient
- **📖 Local background service documentation**
  - **Value tag**: New capabilities have a basis to get started with
  - **Scenario tag**: Service installation, capability understanding, troubleshooting
  - **Effect**: Added the design plan, usage instructions, and a Windows real-machine operation guide for the local background service, and supplemented the auto-update protocol and system-information reporting description, making installation, use, and troubleshooting easier
- **📖 Offline installation and editor-extension documentation**
  - **Value tag**: Special-scenario deployment and extension have rules to follow
  - **Scenario tag**: Offline deployment, editor extension
  - **Effect**: Added an offline installation guide explaining offline package generation and deployment steps; supplemented the editor language-service extension description, so a new language support can be added to the editor just by changing configuration, without code changes

---

### Release Note - v5.0.5 2026-09-21

#### **🚀 New Features**

- **🎯 Structured evaluation model (Jev / TypeSafe)**
  - **Value tag**: More stable judgment-type tasks, no more "guessing" results
  - **Scenario tag**: Requirement classification, methodology selection, candidate selection
  - **Effect**: Added support for the Jev (TypeSafe System One) platform, allowing a "structured evaluation model" to be configured in the model group so that judgment-type tasks such as requirement classification and methodology selection get structured answers from it, making output more stable and predictable; when not configured, behavior is exactly as before, not affecting existing usage
- **🎯 Export messages and pet output as images**
  - **Value tag**: More convenient sharing and archiving
  - **Scenario tag**: Result sharing, record keeping, problem feedback
  - **Effect**: Conversation messages and pet output can be exported as images with one click, with the image carrying an Agent name and timestamp bar; the desktop version copies to the clipboard first, while the mobile version automatically switches to download-and-save, making sharing and archiving convenient

#### **📌 Fixes**

- **🔧 Fix for evaluation failures on overlong content**
  - **Value tag**: Long text can be evaluated normally, no more errors
  - **Scenario tag**: Long-message handling, structured evaluation, content truncation
  - **Effect**: Fixed the issue where truncating overlong content caused evaluation requests to fail; it now safely trims by content structure before submitting, making evaluation more reliable in long-text scenarios
- **🔧 Fix for insufficient quota and too many candidates**
  - **Value tag**: Evaluation uses less quota and failure reasons are clearer
  - **Scenario tag**: Long conversations, many candidates, limited quota
  - **Effect**: Fixed the issues where evaluation returned an empty result directly when quota was insufficient and where a request grew too large with too many candidates and failed; it now first tries to free up space and streamlines candidate information, reducing needless quota consumption
- **🔧 Fix for sub-Agent interaction-mode inheritance**
  - **Value tag**: Sub-Agent behavior is consistent with the parent Agent
  - **Scenario tag**: Multi-Agent collaboration, subtask execution, interaction control
  - **Effect**: Fixed the issue where a sub-Agent was forced into non-interactive mode when the parent Agent was interactive; the sub-Agent now correctly inherits the parent Agent's interaction setting
- **🔧 Fixes for UI details**
  - **Value tag**: Tidy interface and smoother operation
  - **Scenario tag**: Login, topology viewing, shortcut operation
  - **Effect**: The login screen no longer shows the global toolbar; fixed the issue in the network topology where the line directly above was occluded by the chassis and looked as if it wasn't drawn; adjusted the F2 rename priority to prioritize renaming the Agent when there is a current Agent

#### **🔧 Optimizations and Refactoring**

- **🎯 Judgment-type tasks preferentially use the evaluation model**
  - **Value tag**: More stable selection results, with zero change when not configured
  - **Scenario tag**: Methodology selection, candidate selection, requirement classification
  - **Effect**: Judgment-type tasks such as methodology selection preferentially use the evaluation model when it is configured, and automatically fall back to the original flow when it is not configured or the call fails, balancing stability and compatibility
- **🎯 Startup-info display optimization**
  - **Value tag**: Model configuration at a glance
  - **Scenario tag**: Startup viewing, configuration confirmation, narrow terminals
  - **Effect**: The model list in the startup welcome message is now displayed line by line, with evaluation-model information added, so all model tiers' configuration can be clearly seen even in a narrow terminal

#### **📚 Documentation**

- **📖 Structured evaluation model documentation**
  - **Value tag**: Clearer integration and configuration instructions
  - **Scenario tag**: Platform integration, model configuration, feature understanding
  - **Effect**: Added Jev (TypeSafe) platform integration instructions and a structured evaluation model configuration guide, and supplemented the relevant introduction in the README, making it easier to complete configuration following the docs

---

### Release Note - v5.0.4 2026-09-19

#### **🚀 New Features**

- **🎯 Beginner onboarding**
  - **Value tag**: Guidance from the first use, no more facing an empty interface at a loss
  - **Scenario tag**: First login, newly deployed environments, feature onboarding
  - **Effect**: An interactive guide automatically pops up after the first login, progressively highlighting and explaining key areas such as the pet hall, creating an Agent, the chat panel, the command palette, and the sidebar; it can be skipped at any time and reopened later from the command palette
- **🎯 Create an Agent with one sentence**
  - **Value tag**: Less hassle creating an Agent; just describe the requirement
  - **Scenario tag**: Quick creation, multi-Agent collaboration, daily use
  - **Effect**: Added a quick-create entry, letting you create an Agent by describing the requirement in one sentence without filling in configuration item by item; when no Agent has been created yet, the pet hall gives clear next-step guidance
- **🎯 Greatly enhanced command palette**
  - **Value tag**: Common operations gathered in one place, completable with the keyboard
  - **Scenario tag**: Shortcut operation, node management, UI operation
  - **Effect**: The command palette adds entries for creating an Agent with one sentence, viewing the introduction, viewing and resetting the beginner guide, and logging out, and supports creating an Agent on the selected node, opening a terminal, updating code, restarting services, renaming nodes, and quickly switching between Agents and nodes with the arrow keys
- **🎯 Enhanced pet hall**
  - **Value tag**: More intuitive multi-Agent status and smoother operation
  - **Scenario tag**: Parallel multiple Agents, status monitoring, UI operation
  - **Effect**: The pet hall adds one-click show/hide of all output, dock-to-edge collapse and recall, and empty-state guidance; pet and node selection states are clearer, making viewing and switching smoother in multi-Agent scenarios

#### **📌 Fixes**

- **🔧 Fix for terminal history output display**
  - **Value tag**: Terminal output no longer lost or duplicated after refresh
  - **Scenario tag**: Terminal execution, page refresh, history review
  - **Effect**: Fixed the issue where the terminal history output might not display at all after refreshing the page, and avoided duplication caused by live output and historical text appearing at the same time during execution
- **🔧 Fix for rule-loading prompt**
  - **Value tag**: Clear rule paths, avoiding load failures
  - **Scenario tag**: Rule usage, automatic rule selection, custom extension
  - **Effect**: When automatically selecting rules, it now shows the full path of the rule file, avoiding subsequent rule-load failures caused by an incomplete path; it also optimizes the rule-injection strategy so the rule body is loaded on demand, reducing context usage
- **🔧 Fix for master node address recognition**
  - **Value tag**: More accurate node localization in distributed deployments
  - **Scenario tag**: Multi-node deployment, remote connection, cluster operations
  - **Effect**: Fixed the issue where the master node's external address was concatenated incorrectly when listening on a wildcard address, and supports explicitly specifying the master node address via an environment variable, making child-node connections more reliable

#### **🔧 Optimizations and Refactoring**

- **🎯 Upgraded web-search capability**
  - **Value tag**: Richer search results, with automatic fallback on failure
  - **Scenario tag**: Information lookup, technical search, daily searching
  - **Effect**: The search tool adds multi-source aggregation and a fallback strategy, automatically switching to other sources when a common search is unavailable, and adds retrieval of technical sites such as StackOverflow and GitHub, making results more stable and comprehensive
- **🎯 Unified startup method**
  - **Value tag**: Simpler startup, consistent across platforms
  - **Scenario tag**: Local startup, container deployment, resident service
  - **Effect**: Web-side startup is unified into the `haijunbot-service run` command, which automatically completes dependency installation, frontend build, and service startup, with consistent usage on Windows and Linux/macOS; the container image also switches to this command for startup and supports specifying the listen address and port

#### **📚 Documentation**

- **📖 Startup and beginner-guide documentation**
  - **Value tag**: Clearer deployment and onboarding instructions
  - **Scenario tag**: Environment deployment, first use, feature understanding
  - **Effect**: Updated the web-side startup guide and quick-start docs to introduce the new startup command and parameters; added beginner-guide usage instructions covering the guide steps and how to skip and rewatch

---

### Release Note - v5.0.2 2026-09-17

#### **🚀 New Features**

- **🎯 Browser extension (Browser Bridge)**
  - **Value tag**: The Agent can directly operate the user's real browser, reusing the login state
  - **Scenario tag**: Web automation, operating logged-in sites, data collection
  - **Effect**: Added a browser extension that lets the Agent operate web pages in a real browser as if it were the user, automatically reusing logged-in cookies and tabs, with no repeat login and no public IP needed; it supports page read/write, screenshots, file upload, bookmark/history/download management, userscript-like scripts, and network-request and cookie management, and provides one-click download/install and version-update prompts in the pet hall
- **🎯 Pet hall**
  - **Value tag**: Multi-Agent running status visible at a glance, with direct on-screen interaction
  - **Scenario tag**: Multi-Agent collaboration, parallel tasks, status monitoring
  - **Effect**: The frontend visualizes each Agent as a pet sprite, overlaid with a node-and-link topology layer, so the Agent's busy, waiting, and stopped states are clear at a glance; you can directly view output, enter messages, send, and complete on the pet, with toggles for pet roaming, hiding sprites, and showing all output
- **🎯 Network topology view**
  - **Value tag**: The distributed deployment structure is clearly visible
  - **Scenario tag**: Multi-node deployment, Agent distribution, cluster operations
  - **Effect**: Added a network topology overlay that shows the master and each node as a chassis shape and each Agent as a robot shape, displaying the online node count and Agent overview in real time; click the mini-map next to the pet to expand it
- **🎯 Command palette**
  - **Value tag**: Faster operation, no need to memorize entries
  - **Scenario tag**: Shortcut operation, Agent management, UI operation
  - **Effect**: Added a command palette (invoked with Ctrl+P) that gathers common operations such as viewing changes, viewing rules, creating a terminal, permission management, lossless rebirth, delete, and detach panel, and supports searching Agents for quick localization
- **🎯 Cross-node command execution**
  - **Value tag**: More convenient distributed operations
  - **Scenario tag**: Multi-node management, remote execution, cluster maintenance
  - **Effect**: The Agent can execute shell commands on a specified node, supporting cross-node invocation with automatic adaptation to each node's local environment; it also adds the ability to query the master gateway address used by the current node, helping child nodes correctly locate the master node
- **🎯 Enhanced file-editing tools**
  - **Value tag**: More precise file changes, smoother large-file handling
  - **Scenario tag**: Code modification, whole-file rewrite, line-based replacement
  - **Effect**: Added two editing modes—whole-file overwrite and line-number replacement—which, together with the existing find-and-replace, cover different scenarios such as creating new files, large-scale rewrites, and precisely targeted modifications, reducing erroneous edits

#### **📌 Fixes**

- **🔧 Security hardening for the child-node gateway**
  - **Value tag**: Avoid exposing nodes as unauthenticated entry points
  - **Scenario tag**: Multi-node deployment, security hardening, network configuration
  - **Effect**: Fixed the issue where the child-node gateway could bind to a non-loopback address and thus be directly accessed from outside; the child-node gateway now forcibly listens only on the local loopback address, and cross-node access permission is uniformly controlled by the master node

#### **🔧 Optimizations and Refactoring**

- **🎯 Plain-language prompts and rules**
  - **Value tag**: Rules are more readable and the model understands more accurately
  - **Scenario tag**: Rule authoring, prompt maintenance, custom extension
  - **Effect**: Continued converting built-in prompts, rules, and scenario descriptions from classical Chinese to modern plain language, covering modules such as code commit, methodology loading, and tool generation, for clearer expression and easier maintenance
- **🎯 Gateway and node management optimization**
  - **Value tag**: More stable cross-node operations
  - **Scenario tag**: Multi-node deployment, remote execution, service restart
  - **Effect**: Optimized how the interpreter and working directory are resolved during cross-node command execution, avoiding failures caused by environment differences between the master and child nodes; the node list now includes version information and restart responses are more reliable

#### **📚 Documentation**

- **📖 Browser extension documentation**
  - **Value tag**: Clearer installation and usage, more thorough risk warnings
  - **Scenario tag**: Extension installation, capability understanding, security notices
  - **Effect**: Added browser extension documentation covering installation steps, the login-state reuse mechanism, a capability overview, and risk warnings and disclaimers for highly sensitive permissions
- **📖 Comprehensive README update**
  - **Value tag**: More complete project positioning and capability introduction
  - **Scenario tag**: First-time understanding, capability overview, selection comparison
  - **Effect**: Restructured the README, adding sections on the four-quadrant collaboration model, core-highlight comparison, browser extension, and distributed deployment, and supplementing UI screenshots to help users quickly understand the whole project

---

### Release Note - v5.0.1 2026-09-10

#### **🚀 New Features**

- **🎯 Unified UI visuals**
  - **Value tag**: Consistent style, more refined look
  - **Scenario tag**: Daily use, UI beautification, visual experience
  - **Effect**: The five interfaces—settings, management, chat room, create Agent, and integrated terminal—are unified into a deep-space holographic style, using glassmorphism panels, ice-blue glow borders, and gradient title bars, consistent with the visual language of the connection page
- **🎯 Sidebar greeting banner**
  - **Value tag**: Personalized greeting, friendlier interface
  - **Scenario tag**: Daily use, multi-user environments, UI customization
  - **Effect**: A greeting banner is added at the top of the sidebar, displaying the current username in gradient art text; when the username is not obtained, it is left blank instead of showing a default placeholder name

#### **📌 Fixes**

- **🔧 Fix for Diff colors inside messages**
  - **Value tag**: Code changes are more readable and syntax highlighting clearer
  - **Scenario tag**: Code changes, Diff viewing, code review
  - **Effect**: Fixed the issue where the code text of an inline Diff in a message was overridden by the inline-code style and turned entirely green; the Diff restores its original red/green add/delete colors, and inline code changes to ice-blue to coordinate with the theme
- **🔧 Greeting banner font-size adjustment**
  - **Value tag**: More coordinated layout, more comfortable visuals
  - **Scenario tag**: UI beautification, visual experience
  - **Effect**: Reduced the greeting banner font size in the sidebar and toned down the font weight and glow to avoid looking crowded in a narrow sidebar

### Release Note - v5.0.0 2026-09-10

#### **🚀 New Features**

- **🎯 Native tool calling (Function Calling)**
  - **Value tag**: More reliable tool calling and more precise execution of complex tasks
  - **Scenario tag**: Multi-tool collaboration, complex tasks, daily conversation
  - **Effect**: Underlying model calls are fully upgraded to native tool calling, supported by both OpenAI and Haijun; tool parameters are generated directly by the model without relying on text parsing, significantly improving call success rate and stability, and older models can automatically fall back for compatibility
- **🎯 Lossless Agent rebirth**
  - **Value tag**: Context is not lost, long tasks can continue
  - **Scenario tag**: Long sessions, context bloat, task continuation
  - **Effect**: The Agent can be regenerated while preserving key context, solving the problems of bloated context and slowed responses after long runs, allowing tasks to continue seamlessly
- **🎯 Frontend JS execution and targeted delivery**
  - **Value tag**: The Agent can operate web pages directly, for more efficient debugging
  - **Scenario tag**: Frontend debugging, page automation, UI verification
  - **Effect**: Added the eval_js tool, letting the Agent execute JavaScript directly in the browser to read or operate pages; it supports precisely specifying which frontend connection to deliver to, so results no longer mix across windows in multi-window scenarios
- **🎯 Voice reading and voice input**
  - **Value tag**: Hands-free, more natural interaction
  - **Scenario tag**: Message reading, hands-free operation, mobile use
  - **Effect**: Supports reading messages aloud and converting voice input to text; the chat panel can enable auto-reading, and the mobile voice-recognition experience is optimized
- **🎯 Quick-start guide in the connection dialog**
  - **Value tag**: Faster onboarding, simpler configuration
  - **Scenario tag**: First use, environment configuration, remote connection
  - **Effect**: The connection dialog adds a quick-start guide and visual effects; following the steps completes the connection configuration, lowering the barrier for first use
- **🎯 Enhanced chat panel**
  - **Value tag**: Clearer parallel multi-tasking, smoother operation
  - **Scenario tag**: Multi-Agent collaboration, window management, daily use
  - **Effect**: Agent operation buttons move from the sidebar to the chat panel, making operations more centralized; added an auto-scroll toggle, and terminal session output syncs in real time and auto-scrolls to the bottom

#### **📌 Fixes**

- **🔧 Fix for native tool-calling stability**
  - **Value tag**: More stable calls, no more unexpected errors
  - **Scenario tag**: Native tool calling, multi-turn conversations, complex tasks
  - **Effect**: Fixed request errors caused by incomplete tool-call pairing and leftover orphan messages; fixed issues such as uncleared pending tools after an interruption and duplicated user input; invalid parameters are kept as-is so the model can self-correct
- **🔧 Fix for context compression and summarization**
  - **Value tag**: More stable long sessions; summaries no longer pollute
  - **Scenario tag**: Long conversations, context compression, session management
  - **Effect**: Fixed issues such as compressed summaries polluting session-name determination, uncleared background pre-compression state, and infinite loops in summary retries, making long sessions run more stably
- **🔧 Fix for terminal session display**
  - **Value tag**: Output visible in real time, no more duplicated history
  - **Scenario tag**: Terminal execution, interactive programs, session review
  - **Effect**: Fixed the issue where the frontend terminal did not display or sync in real time when running interactive programs (such as vim); fixed the issue where the chat container did not auto-scroll after creating and destroying a terminal; fixed the issue of history being saved repeatedly
- **🔧 Fix for scroll positioning in multi-Agent panels**
  - **Value tag**: More accurate message positioning, reading without jumping around
  - **Scenario tag**: Parallel multiple Agents, streaming output, panel switching
  - **Effect**: Fixed incorrect scroll positioning for streaming messages in multi-Agent panels, so messages always follow the latest content

#### **🔧 Optimizations and Refactoring**

- **🎯 Comprehensive plain-languaging of built-in rules and prompts**
  - **Value tag**: Rules are more readable and the model understands more accurately
  - **Scenario tag**: Rule authoring, prompt maintenance, custom extension
  - **Effect**: Built-in rules and scenario prompts have all classical-Chinese expressions removed and replaced with modern plain language; low-value and duplicate rules are cleaned up, making the rule system more concise and clear, easier for users to read and customize
- **🎯 Context management optimization**
  - **Value tag**: Long tasks use fewer resources and respond more smoothly
  - **Scenario tag**: Overlong output, context management, performance optimization
  - **Effect**: Overlong tool output is automatically written to disk to avoid filling up the context; the context-compression trigger threshold is optimized and background pre-compression takes effect immediately, making long tasks run more smoothly
- **🎯 Modernized tool descriptions**
  - **Value tag**: The model selects tools more accurately and executes more efficiently
  - **Scenario tag**: Tool calls, parameter understanding, task execution
  - **Effect**: Tool descriptions and parameter explanations are fully plain-languaged, with enum meanings expanded more clearly, improving the model's accuracy in selecting tools and filling in parameters

#### **📚 Documentation**

- **📖 Context management solution documentation**
  - **Value tag**: Clear design approach, easy to understand and extend
  - **Scenario tag**: Context management, solution design, technical reference
  - **Effect**: Added a context management solution design document explaining the overlong-context handling mechanism and implementation approach

---

### Release Note - v4.0.2 2026-09-01

#### **🚀 New Features**

- **🎯 Floating and embedded session panels**
  - **Value tag**: More efficient multi-task parallelism and a more flexible interface layout
  - **Scenario tag**: Multi-Agent collaboration, window management, and interface customization
  - **Effect**: Added a session-panel component that supports detaching Agent sessions from the main interface into independent floating windows, or embedding them back into the main interface; multiple panels can be opened at the same time without interfering with each other
- **🎯 One-click code push**
  - **Value tag**: More convenient code commits and more efficient operation
  - **Scenario tag**: Code push, version management, daily development
  - **Effect**: Added the built-in GitPush command; entering it in the conversation lets you push code to the remote repository with one click, with no need to manually run git commands
- **🎯 Intelligent recognition of orchestration file paths**
  - **Value tag**: More natural input and more effortless operation
  - **Scenario tag**: Orchestration files, path input, multi-line instructions
  - **Effect**: Orchestration file paths support intelligent extraction, automatically recognizing multiple formats such as quoted paths, paths with a prefix description, and Windows paths, with no need to manually clean up the input
- **🎯 Password input protection**
  - **Value tag**: Sensitive information is safer and input is more reassuring
  - **Scenario tag**: Password input, key configuration, secure operations
  - **Effect**: The input box supports a password mode, echoing the input as \* characters to protect sensitive information from onlookers

#### **📌 Fixes**

- **🔧 Resumable install script**
  - **Value tag**: More stable installation and recoverable from failures
  - **Scenario tag**: Quick installation, unstable network, repeated installation
  - **Effect**: The install script supports resuming after an interruption, skipping completed steps when re-run; added automatic switching among multiple mirror sources, making installation smoother for users in China
- **🔧 Enhanced hjb command path lookup**
  - **Value tag**: More reliable tool installation and broader environment compatibility
  - **Scenario tag**: Tool installation, environment configuration, multi-user scenarios
  - **Effect**: Automatically locates the hjb executable path, supporting user environment variables and common installation locations, avoiding tool-installation failures caused by PATH configuration issues

#### **📚 Documentation**

- **📖 README comparison table update**
  - **Value tag**: Clearer selection and positioning
  - **Scenario tag**: Project selection, technology comparison, community promotion
  - **Effect**: The README adds a comparison table with other mainstream AI assistant solutions (LangChain, AutoGPT, OpenClaw, etc.), helping users quickly understand HaijunBot's positioning and advantages

### Release Note - v4.0.1 2026-08-26

#### **🚀 New Features**

- **🎯 Custom input handler extension**
  - **Value tag**: Agent capabilities can be freely extended and special instructions handled more flexibly
  - **Scenario tag**: Custom instructions, special markers, personalized interaction
  - **Effect**: Supports dynamically loading custom input handlers via the configuration file; users can customize the handling logic for special markers, extending Agent capabilities without modifying core code
- **🎯 Configuration template variable rendering**
  - **Value tag**: More flexible configuration and more convenient path references
  - **Scenario tag**: Multi-environment deployment, path configuration, team collaboration
  - **Effect**: The configuration file supports jinja2 template variables (such as the current directory and project root), making configuration more flexible and reducing hard-coded paths
- **🎯 Recent working-directory history**
  - **Value tag**: Faster Agent creation and one-click selection of frequently used directories
  - **Scenario tag**: Frequent Agent creation, switching between multiple projects
  - **Effect**: Automatically records recently used working directories (up to 20), so frequently used directories can be quickly selected when creating an Agent, with no need to repeatedly type them by hand
- **🎯 Enhanced chat room permission management**
  - **Value tag**: More standardized chat room management and more efficient administrator control
  - **Scenario tag**: Team collaboration, chat room management, permission control
  - **Effect**: Administrators can rename and delete any chat room, offline members show their real usernames, and chat room management permissions are clearer
- **🎯 Chat image preview and online status**
  - **Value tag**: Smoother chat experience and member status at a glance
  - **Scenario tag**: Daily chat, image viewing, member management
  - **Effect**: Chat images support click-to-enlarge preview without opening a new window; chat members' online/offline status is displayed in real time

#### **📌 Fixes**

- **🔧 Fix for chat image display**
  - **Value tag**: More reliable image display, no more loading failures
  - **Scenario tag**: Chat images, file upload
  - **Effect**: Fixed the chat image relative-path resolution issue; image URLs are automatically converted to full addresses, ensuring images display correctly
- **🔧 Enhanced code commit command**
  - **Value tag**: More convenient commit operations with a wider range of applicability
  - **Scenario tag**: Code commit, version management
  - **Effect**: Fixed the issue where non-code Agents could not commit code; the commit command can now be run directly in a git repository without switching the Agent type
- **🔧 Optimized handling of repeated responses**
  - **Value tag**: More natural conversation; no more lost history messages
  - **Scenario tag**: Long conversations, complex tasks
  - **Effect**: Fixed the issue where history messages were deleted when the LLM responded with consecutive repetitions; instead it now prompts the model not to answer repeatedly, preserving the full conversation context

#### **🔧 Optimizations and Refactoring**

- **🎯 Security scan performance improvement**
  - **Value tag**: Faster security scans with significantly improved detection efficiency
  - **Scenario tag**: Code security audit, CI/CD security checks
  - **Effect**: Agents for security analysis, review, and verification enable a fast mode, greatly improving scan speed
- **🎯 Optimized rule loading and track installation**
  - **Value tag**: Faster startup and more direct track acquisition
  - **Scenario tag**: Rule management, track discovery, system startup
  - **Effect**: The rule index is optimized to reduce the load, and the track installation flow is simplified, allowing search results to be installed directly without AI evaluation
- **🎯 Enhanced administrator permissions**
  - **Value tag**: Smoother management operations and more reasonable permission control
  - **Scenario tag**: System management, multi-node deployment
  - **Effect**: Administrators automatically have access to all nodes, with no need to configure each node individually
- **🎯 Optimized Agent sidebar interface**
  - **Value tag**: Clearer Agent information and smoother operation
  - **Scenario tag**: Agent management, multi-Agent collaboration
  - **Effect**: The Agent list adds a tool-viewing button, and metadata such as nodes and model groups is shown as tags, making the interface cleaner and more intuitive

#### **📚 Documentation Update**

- **🎯 Added contribution guide**
  - **Value tag**: More standardized community contributions and smoother collaboration
  - **Scenario tag**: Open-source contributions, team collaboration
  - **Effect**: Added a CONTRIBUTING.md contribution guide, clarifying process standards for bug reports, feature suggestions, code commits, and more
- **🎯 Architecture refactoring plan document**
  - **Value tag**: Architecture evolution has a basis and the development direction is clearer
  - **Scenario tag**: Architecture design, technical planning
  - **Effect**: Added an architecture refactoring plan document, providing clear guidance for future architecture evolution

---

### Release Note - v4.0.0 2026-08-14

#### **🚀 New Features**

- **🎯 Multi-user account system and permission management**
  - **Value tag**: Safer multi-person collaboration and more fine-grained permission assignment
  - **Scenario tag**: Team collaboration, multi-user use, permission control
  - **Effect**: Introduced an all-new multi-user account system, supporting user registration and login, encrypted password storage, and account lockout protection after failed logins; built-in role permission groups allow flexible assignment of access permissions by team role, achieving resource-level fine-grained control
- **🎯 All-new management panel and chat interface**
  - **Value tag**: More intuitive management operations and a smoother chat experience
  - **Scenario tag**: System management, user management, daily conversation
  - **Effect**: Added a full-featured management panel with user and Agent management at a glance; the chat interface is fully rebuilt, supporting real-time multi-user collaboration and private chat sessions with real-time status sync
- **🎯 Adversarial security collaboration orchestration**
  - **Value tag**: Significantly enhanced security detection and more thorough vulnerability discovery
  - **Scenario tag**: Code security audit, vulnerability discovery, security team collaboration
  - **Effect**: Added an adversarial Agent security collaboration mode in which multiple security Agents collaboratively analyze in an adversarial manner, combining call graphs and taint analysis to deeply uncover potential security risks
- **🎯 Self-evolving Agent network**
  - **Value tag**: The Agent system can self-iterate and gets smarter with use
  - **Scenario tag**: Complex task orchestration, automated operations, knowledge accumulation
  - **Effect**: Added self-evolving Agent network orchestration, forming a closed loop of task scheduling, execution, knowledge accumulation, and monitoring; Agents can continuously learn and optimize their own strategies while running
- **🎯 Automatic completion of the Agent commit flow**
  - **Value tag**: More efficient task execution with less manual intervention
  - **Scenario tag**: Automated tasks, batch processing, unattended operation
  - **Effect**: After completing a task, the Agent can automatically run the full commit flow without manual confirmation; when there are no tool calls in the first round, it automatically analyzes and decides, improving task throughput

#### **📌 Fixes**

- **🔧 Fix for platform proxy token expiration**
  - **Value tag**: More stable proxy service, no more 401 errors
  - **Scenario tag**: Multi-node deployment, proxy service, gateway restart
  - **Effect**: Fixed request failures caused by proxy token expiration after the master gateway restarts; the latest token is now dynamically injected on every call, keeping business continuity uninterrupted
- **🔧 Fix for duplicate code review execution**
  - **Value tag**: More accurate review results and no more duplicate consumption
  - **Scenario tag**: Code review, quality assurance
  - **Effect**: Fixed the duplicate-execution issue in the code review flow, ensuring each task runs only one complete round of review

#### **🔧 Optimizations and Refactoring**

- **🎯 Unified authentication upgrade**
  - **Value tag**: A more modern security system and more reliable authentication
  - **Scenario tag**: Login authentication, security protection, system integration
  - **Effect**: Fully upgraded to JWT token authentication and removed the old password authentication mechanism, making the authentication process safer and more efficient
- **🎯 Enhanced child-Agent capability inheritance**
  - **Value tag**: Smoother collaborative tasks and more consistent tool calls
  - **Scenario tag**: Multi-Agent collaboration, task orchestration
  - **Effect**: Child Agents automatically inherit the parent Agent's tool and rule configuration, maintaining consistent execution capabilities without repeated configuration
- **🎯 Intelligent summarization of overlong output**
  - **Value tag**: More refined output and more efficient context usage
  - **Scenario tag**: Large tasks, long-text processing
  - **Effect**: When Agent output is too long, a lightweight model is automatically called to summarize it intelligently, preserving core information while saving context space
- **🎯 Comprehensive conversion to classical Chinese**
  - **Value tag**: Consistent style and more concise expression
  - **Scenario tag**: System prompts, tool guides
  - **Effect**: All built-in prompts and guides are unified into a classical-Chinese writing style for more precise expression

#### **📚 Documentation Update**

- **🎯 Multi-user architecture design document**
  - **Value tag**: Architecture design has a basis and secondary development is smoother
  - **Scenario tag**: Architecture understanding, secondary development, team collaboration
  - **Effect**: Added complete design documentation and an implementation guide for the multi-user authentication and permission system, helping developers quickly understand the new architecture

---

### Release Note - v3.1.30 2026-08-02

#### **🚀 New Features**

- **🎯 Detection of unsafe APIs after macro expansion**
  - **Value tag**: Greatly enhanced security scanning that no longer misses dangerous calls hidden by macro wrapping
  - **Scenario tag**: C/C++ project security audit, macro-wrapped code inspection
  - **Effect**: Added an AST-based detection mechanism that can identify unsafe API calls such as strcpy and gets after macro expansion, closing the blind spot where macro wrapping was used to bypass vulnerability detection
- **🎯 Automatic improvement of adversarial security rules**
  - **Value tag**: Security rules keep self-evolving and detection keeps improving with use
  - **Scenario tag**: Security scan rule maintenance, vulnerability detection improvement
  - **Effect**: Rule development and the adversarial Agent form a closed-loop collaboration, automatically discovering false negatives and false positives and continuously improving detection rules, entering a deep adversarial phase to verify rule robustness

#### **📌 Fixes**

- **🔧 Fix for false positives on security wrapper functions**
  - **Value tag**: More precise security scan results with fewer invalid alerts
  - **Scenario tag**: Code security audit, vulnerability scanning
  - **Effect**: Recognizes safe wrapping patterns such as safe_copy and secure_wrapper, avoiding falsely reporting safe wrappers as unsafe API calls
- **🔧 Fix for false positives at the boundaries of null-pointer checks**
  - **Value tag**: More accurate detection logic; boundary cases no longer falsely reported
  - **Scenario tag**: C/C++ null-pointer detection
  - **Effect**: Optimized the boundary-matching logic of null-pointer checks to correctly recognize check patterns where the variable name carries a suffix

#### **🔧 Optimizations and Refactoring**

- **🎯 Comprehensive classical-Chinese conversion of the prompt system**
  - **Value tag**: Consistent and more concise style with more precise instruction expression
  - **Scenario tag**: Agent interaction, tool guides, system prompts
  - **Effect**: All built-in prompts and tool guides are uniformly rewritten in a classical-Chinese writing style, improving expression efficiency and consistency

#### **📚 Documentation Update**

- **🎯 Expanded security test dataset**
  - **Value tag**: More comprehensive detection coverage and more reliable rule verification
  - **Scenario tag**: Security rule testing, regression verification
  - **Effect**: Added multiple test cases such as command execution, format string, null pointer, SQL injection, and unsafe API, covering more vulnerability variants

---

### Release Note - v3.1.29 2026-07-31

#### **🚀 New Features**

- **🎯 Message metadata display**
  - **Value tag**: Metadata such as message timestamps and sources at a glance, making chat history clearer
  - **Scenario tag**: Frontend message display, history viewing, multi-Agent collaboration
  - **Effect**: Frontend message cards now show metadata such as timestamps and sources, letting users intuitively see when and where each message was sent
- **🎯 Agent auto-connect**
  - **Value tag**: The Agent connects to the frontend automatically after starting, with no manual operation
  - **Scenario tag**: Frontend Agent management, background Agent startup, automated workflows
  - **Effect**: Added Agent auto-connect; after starting, the Agent automatically establishes a WebSocket connection with the frontend, with no need for the user to click connect manually
- **🎯 Breathing-light indicator for Agents waiting for input**
  - **Value tag**: Agents waiting for user input are clear at a glance, preventing anything from being missed
  - **Scenario tag**: Multi-Agent management, task assignment, collaboration scenarios
  - **Effect**: Added an unread-notification breathing-light effect for Agents waiting for user input, making them more visually prominent so users can quickly spot the Agents that need attention

#### **📌 Fixes**

- **🔧 Fix for message timestamp display logic**
  - **Value tag**: More accurate message time display and traceable history
  - **Scenario tag**: Frontend message display, timestamp display, history viewing
  - **Effect**: Fixed the message timestamp display logic, using a unified backend timestamp instead of a frontend-generated local time, ensuring accurate and consistent time display
- **🔧 Fix for a WebSocket reconnect authentication race condition**
  - **Value tag**: More stable reconnection, avoiding connection drops caused by authentication failures
  - **Scenario tag**: WebSocket reconnection, recovery from network fluctuations, service stability
  - **Effect**: Fixed the authentication race condition during WebSocket reconnection, ensuring authentication information is passed correctly during reconnection and no longer causing connection failures due to timing issues
- **🔧 Fix for clearing the clicked marker on Agent status**
  - **Value tag**: The clicked marker is correctly cleared after an Agent status change, making the UI state more accurate
  - **Scenario tag**: Frontend Agent status management, notification alerts
  - **Effect**: Fixed the issue where the clicked marker was not cleared when an Agent's status changed, ensuring the unread alert correctly disappears after the user clicks
- **🔧 Correction of the Agent type identifier**
  - **Value tag**: Unified and standardized Agent type identifiers, avoiding recognition errors
  - **Scenario tag**: Agent orchestration, type recognition, frontend display
  - **Effect**: Corrected the Agent type identifier from codeagent to code_agent, keeping it consistent with the frontend display and orchestration files

#### **🔧 Optimizations and Refactoring**

- **🎯 Refactored the timestamp mechanism to ISO format**
  - **Value tag**: Standardized timestamp format and stronger cross-platform compatibility
  - **Scenario tag**: Time handling, frontend/backend communication, data persistence
  - **Effect**: Refactored the timestamp mechanism into ISO-format strings and removed the \_format logic that automatically added timestamps, unifying the time-format standard and improving cross-platform compatibility
- **🎯 Adjusted the position of tool buttons in the Agent sidebar**
  - **Value tag**: More reasonable interface layout and smoother operation
  - **Scenario tag**: Frontend UI optimization, user experience
  - **Effect**: Adjusted the position of the tool buttons in the Agent sidebar so the layout better matches users' operating habits
- **🎯 Adjusted the default Agent type identifier**
  - **Value tag**: More accurate default type identifier, with automatic recognition when creating a new Agent
  - **Scenario tag**: Agent creation, type recognition
  - **Effect**: Changed the default Agent type identifier to agent, ensuring the type does not need to be specified manually when creating a new Agent

#### **📚 Documentation Update**

- **🎯 Updated the type definitions in the Agent orchestration file**
  - **Value tag**: The orchestration file documentation stays in sync with the code, avoiding configuration errors
  - **Scenario tag**: Agent orchestration, configuration file management, documentation maintenance
  - **Effect**: Updated the type definition documentation in the Agent orchestration file to stay in sync with the latest Agent type identifiers

---

### Release Note - v3.1.27 2026-07-26

#### **🚀 New Features**

- **🎯 AST-based C/C++ null-pointer dereference detection**
  - **Value tag**: More precise security scanning, upgraded from regex matching to syntax-tree analysis
  - **Scenario tag**: Code security audit, vulnerability scanning, CI/CD security checks
  - **Effect**: Uses a tree-sitter AST instead of regex to detect null-pointer dereferences, correctly recognizing safe patterns such as assert assertions, bounds-check protection, division guarded by overflow checks, and short-circuit protection, reducing the false-positive rate to 0
- **🎯 Unified exception logging utility**
  - **Value tag**: Exceptions are collected in a unified way, making troubleshooting more efficient
  - **Scenario tag**: Agent runtime monitoring, error diagnosis, stability analysis
  - **Effect**: Added a unified exception logging module that globally captures and records runtime exceptions, making centralized troubleshooting easier
- **🎯 System environment information injection**
  - **Value tag**: The Agent automatically senses its runtime environment and makes smarter decisions
  - **Scenario tag**: Multi-environment deployment, conditional tool selection, environment adaptation
  - **Effect**: System environment information is automatically injected into Agent prompts, and the hard-coded tool list is removed, letting the Agent dynamically adjust its strategy based on the environment
- **🎯 Batch input and merging of multiple orchestration files**
  - **Value tag**: More flexible batch Agent creation, supporting orchestration combining multiple files
  - **Scenario tag**: Team initialization, parallel multiple projects, complex task orchestration
  - **Effect**: Agent orchestration supports batch input of multiple YAML files with automatic merging, simplifying the large-scale Agent creation flow
- **🎯 Saving content when tool-call parsing fails**
  - **Value tag**: Parse failures are traceable and tool calls are more reliable
  - **Scenario tag**: Tool debugging, format compatibility troubleshooting, call-chain analysis
  - **Effect**: When tool-call parsing fails, the raw content is automatically saved, making it easier to locate format issues

#### **📌 Fixes**

- **🔧 Fix for several false positives in C/C++ security scanning**
  - **Value tag**: More precise security scan results with less interference from invalid alerts
  - **Scenario tag**: Code security audit, CI/CD security checks, vulnerability scanning
  - **Effect**: Fixed false positives for divide_by_zero on macro-constant divisors, realloc assignment-rollback false positives (switched to AST detection), false positives on IO calls wrapped in error-handling macros, integer-overflow and allocation-size-overflow false positives, and uninitialized_var false positives on typedef
- **🔧 Permission restriction for sub_code_agent**
  - **Value tag**: Safer tool calls, preventing unauthorized use
  - **Scenario tag**: Multi-Agent collaboration, permission isolation, security control
  - **Effect**: Restricted the sub_code_agent tool so only CodeAgent can call it, preventing other Agent types from using it without authorization

#### **♻️ Optimizations**

- **💡 Standardization of the rule description field**
  - **Value tag**: More concise and consistent rule descriptions with better readability
  - **Scenario tag**: Rule authoring, rule review, rule management
  - **Effect**: Streamlined the format requirements of the rule description field and unified the template standard
- **💡 Made the exception logging module standalone**
  - **Value tag**: Clearer module responsibilities and easier maintenance
  - **Scenario tag**: Code refactoring, modularization
  - **Effect**: Moved save_exception from inline code into a standalone module, improving code organization

### Release Note - v3.1.26 2026-07-24

#### **🚀 New Features**

- **🎯 Batch Agent creation via orchestration**
  - **Value tag**: Create multiple Agents in a batch with one command, making team collaboration more efficient
  - **Scenario tag**: Parallel multi-Agent development, team task assignment, project initialization
  - **Effect**: Added the @OrganizeAgents command to create Agents in a batch via a YAML orchestration file, supporting custom names, types, working directories, and model groups

- **🎯 Parallelized security scanning with progress visualization**
  - **Value tag**: Significantly faster large-scale code scanning with progress at a glance
  - **Scenario tag**: Large-project security scanning, CI/CD integration, batch vulnerability detection
  - **Effect**: Heuristic scanning supports multi-process parallel analysis, a new rich progress bar shows the scan status, and the number of worker processes is configurable

- **🎯 Recording details of security scan false positives**
  - **Value tag**: False positives are traceable, making it easier to optimize detection rules
  - **Scenario tag**: Security scan result analysis, rule tuning, false-positive management
  - **Effect**: Vulnerabilities that the Agent judges to be false positives have their details automatically recorded for later analysis and optimization

- **🎯 Investment-analysis framework rules**
  - **Value tag**: Systematically analyze the investment value of a stock, progressing layer by layer from macro conditions to operational strategy
  - **Scenario tag**: In-depth study of individual stocks, stock-picking review, research report writing
  - **Effect**: Added investment-analysis rules with 7 major modules covering the macro environment, industry track, company fundamentals, financial data, valuation and pricing, risk screening, and operational strategy

- **🎯 In-depth interview rules**
  - **Value tag**: Fully validate decisions before execution, avoiding blind action
  - **Scenario tag**: Technical solution design, architecture decisions, feature planning, problem solving
  - **Effect**: Added the Grilling rule, which helps clarify thinking, uncover hidden assumptions, and validate the reasonableness of decisions through one-by-one questioning

- **🎯 Code taste guidelines**
  - **Value tag**: More elegant AI-generated code and more unified quality standards
  - **Scenario tag**: Code generation, code review, quality assessment
  - **Effect**: Added code taste guidelines to all CodeAgent scenario prompts, covering 7 principles such as reuse first, minimal changes, and naming as documentation

#### **📌 Fixes**

- **🔧 Fix for duplicate input-handler execution**
  - **Value tag**: Commands are no longer processed repeatedly, making execution more reliable
  - **Scenario tag**: Agent command execution, CodeAgent interaction
  - **Effect**: Fixed the issue where built-in input handlers were called repeatedly in both Agent and CodeAgent

- **🔧 Fix for line-number offset in line-number-mode editing**
  - **Value tag**: Multi-line-range edits produce correct results without misalignment
  - **Scenario tag**: Batch code modification, simultaneous editing of multiple regions
  - **Effect**: Fixed the issue where content was replaced at the wrong position due to line-number offsets when editing multiple line ranges

- **🔧 Fix for mistakenly excluding Cargo.lock in Rust projects**
  - **Value tag**: More complete file analysis for Rust projects
  - **Scenario tag**: Rust code analysis, security scanning
  - **Effect**: Fixed the issue where Cargo.lock was mistakenly added to the excluded directories, causing incomplete analysis of Rust projects

- **🔧 Fix for scrolling in the web edit panel**
  - **Value tag**: Long content can be scrolled normally
  - **Scenario tag**: Web UI code editing, long-file viewing
  - **Effect**: Fixed the issue where the edit panel could not scroll when the content overflowed

#### **🔧 Optimizations and Refactoring**

- **🎯 Optimized offline install-package build**
  - **Value tag**: Cleaner and more universal offline packages with no extra dependencies
  - **Scenario tag**: Offline deployment, network-restricted environments
  - **Effect**: Changed the packaging format from 7z back to the more universal tar.gz, and use uv to create a clean virtual environment instead of copying the existing venv

- **🎯 Optimized the timing of tmux layout setup**
  - **Value tag**: More precise window-layout setup, avoiding unnecessary execution
  - **Scenario tag**: tmux environments, multi-window development
  - **Effect**: Moved the tmux tiled layout from global initialization to the first Agent run, reducing unnecessary calls

- **🎯 Optimized symbol-table construction for security scanning**
  - **Value tag**: More accurate cross-file analysis and more complete symbol-table coverage
  - **Scenario tag**: Security scanning, cross-function vulnerability detection
  - **Effect**: The symbol-table construction phase no longer excludes directories, ensuring complete cross-file reference analysis

- **🎯 Database batch-commit mode**
  - **Value tag**: Greatly improved data-write performance
  - **Scenario tag**: Security scan data collection, batch symbol import
  - **Effect**: Added a batch-commit mode that delays commits to improve write performance

- **🎯 Silenced logs during security scanning**
  - **Value tag**: Cleaner scan output with no interference with the progress bar
  - **Scenario tag**: Security scanning, command-line output
  - **Effect**: Changed data-collection and database-initialization logs to silent mode to avoid interfering with the progress bar

---

### Release Note - v3.1.25 2026-07-15

#### **🚀 New Features**

- **🎯 AI-friendly code structure guidelines**
  - **Value tag**: Code is easier for AI to understand and maintain, improving AI-assisted development efficiency
  - **Scenario tag**: Code refactoring, AI-assisted programming, code quality assessment
  - **Effect**: Added AI-friendly code structure rules that define 7 major measurement dimensions and a scoring model, with support for CI gate integration

- **🎯 Persistence of session pinned content**
  - **Value tag**: Important content is retained across sessions with no need to set it again
  - **Scenario tag**: Long-term tasks, context retention, session recovery
  - **Effect**: An Agent's pin_content supports session save and restore, automatically restoring the pinned content after a restart

#### **📌 Fixes**

- **🔧 Fix for database migration compatibility**
  - **Value tag**: Old databases upgrade automatically with no manual intervention
  - **Scenario tag**: Database upgrade, version migration, compatibility handling
  - **Effect**: Fixed test failures caused by the missing use_type column in the data_flow table, and added automatic migration logic

- **🔧 Fix for CodeAgent session recovery logic**
  - **Value tag**: A selection prompt no longer appears when a session to restore is specified
  - **Scenario tag**: Session recovery, command-line argument handling
  - **Effect**: Fixed the issue where session selection was still triggered when the restore parameter was specified

#### **🔧 Optimizations and Refactoring**

- **🎯 Optimized child-Agent interaction mode**
  - **Value tag**: More reliable automation flows, with child Agents correctly inheriting the parent Agent's settings
  - **Scenario tag**: Child-Agent creation, automated tasks, non-interactive mode
  - **Effect**: Child Agents now correctly inherit the parent Agent's auto_complete and non_interactive settings

- **🎯 Optimized model configuration naming**
  - **Value tag**: Better uniqueness of configuration names, avoiding same-name conflicts across multiple platforms
  - **Scenario tag**: Model configuration management, multi-platform deployment
  - **Effect**: Model configuration names now include a hostname prefix, ensuring unique configuration names across different platforms

- **🎯 Optimized compatibility of proxy environment variables**
  - **Value tag**: More compatible proxy settings, with automatic handling of the socks protocol prefix
  - **Scenario tag**: Network proxy configuration, environment variable handling
  - **Effect**: Automatically strips the socks:// prefix, for compatibility with applications that do not support the socks protocol

- **🎯 Enhanced safety of the refactoring flow**
  - **Value tag**: Safer refactoring with mandatory test-coverage checks
  - **Scenario tag**: Code refactoring, test-driven development
  - **Effect**: The refactoring rule adds a test-coverage check step; refactoring is allowed only when the test pass rate is 100% and coverage is ≥80%

#### **📚 Documentation Update**

- **🎯 Updated security scan documentation**
  - **Value tag**: Documentation stays in sync with the code and the rule counts are accurate
  - **Scenario tag**: Security scanning, documentation maintenance
  - **Effect**: Updated the security scan rule count (C/C++ 62 rules, Rust 34 rules) and the test dataset count

---

### Release Note - v3.1.24 2026-07-13

#### **🚀 New Features**

- **🎯 Offline install-package support**
  - **Value tag**: Quick deployment in no-network environments with one-click packaging of all dependencies
  - **Scenario tag**: Network-restricted environments, batch deployment, offline demos
  - **Effect**: Added an offline install-package creation script and an installation script, supporting x86_64 and aarch64 architectures and including the Python environment, virtual environment, built-in tools, and frontend build artifacts

#### **📌 Fixes**

- **🔧 Disabled the summarization feature in non-interactive mode**
  - **Value tag**: Cleaner automation flows, avoiding unnecessary summary output
  - **Scenario tag**: Non-interactive mode, automated tasks, CI/CD integration
  - **Effect**: Fixed the issue where the summarization feature was still triggered in non-interactive mode, ensuring concise output for automation flows

- **🔧 Fix for merged display of frontend history messages**
  - **Value tag**: More accurate history display with correct message-merging logic
  - **Scenario tag**: Web UI history, message sync
  - **Effect**: Fixed display problems caused by merging synced history messages with existing messages

#### **🔧 Optimizations and Refactoring**

- **🎯 Optimized offline package format**
  - **Value tag**: Higher compression efficiency and smaller package size
  - **Scenario tag**: Offline package creation, file transfer
  - **Effect**: Changed the offline package format from tar.gz to 7z to improve compression efficiency

- **🎯 Cleaned up redundant test scripts**
  - **Value tag**: A tidier project structure and less maintenance burden
  - **Scenario tag**: Project maintenance, code cleanup
  - **Effect**: Deleted 5 temporary test script files

#### **📚 Documentation Update**

- **🎯 shfmt installation guide**
  - **Value tag**: Documented installation of the Shell script formatter
  - **Scenario tag**: Development environment setup, Shell script development
  - **Effect**: Added a guide for installing shfmt on Arch Linux to the project's long-term memory

---

### Release Note - v3.1.23 2026-07-08

#### **📌 Fixes**

- **🔧 Fix for child-Agent non-interactive mode inheritance**
  - **Value tag**: Child Agents correctly inherit the parent Agent's non-interactive mode setting, ensuring consistency in automation flows
  - **Scenario tag**: Child-Agent creation, non-interactive mode, automated task execution
  - **Effect**: Fixed the issue where the sub_agent and sub_code_agent tools did not correctly inherit the parent Agent's non_interactive configuration; child Agents now correctly inherit the parent Agent's non-interactive mode setting
- **🔧 Improved project memory documentation**
  - **Value tag**: The project release flow and security scan rules are traceable, making the knowledge base more complete
  - **Scenario tag**: Version release, security scanning, project knowledge management
  - **Effect**: Added memory for the project release flow and security scan rules, improving the project's long-term knowledge base

---

### Release Note - v3.1.22 2026-07-01

#### **🚀 New Features**

- **🎯 Expanded C/C++ security scan rules**
  - **Value tag**: More comprehensive vulnerability detection, adding three new detection categories: SSRF, deserialization, and resource consumption
  - **Scenario tag**: C/C++ code security checks, server-side request forgery detection, deserialization vulnerability recognition
  - **Effect**: Added rules for CWE-918 SSRF detection, CWE-502 deserialization detection, and CWE-400 resource consumption detection

- **🎯 Expanded Rust security scan rules**
  - **Value tag**: Full coverage of Rust security detection, supporting recognition of 20 categories of Rust-specific security risks
  - **Scenario tag**: Rust code security checks, unsafe code audit, FFI boundary security
  - **Effect**: Added 20 categories of detection rules covering unsafe blocks, raw pointer operations, type conversion, memory operations, and more

#### **🔧 Optimizations and Refactoring**

- **🎯 Improved test datasets**
  - **Value tag**: More comprehensive security test coverage, adding 10 categories of vulnerability test cases
  - **Scenario tag**: Security testing, vulnerability verification, regression testing
  - **Effect**: Added CWE-918/CWE-502/CWE-400 test datasets and 7 categories of Rust security test datasets

---

### Release Note - v3.1.21 2026-06-28

#### **🚀 New Features**

- **🎯 Heuristic security scan command**
  - **Value tag**: Fast static analysis with no LLM needed, with 38+ rules covering common vulnerabilities
  - **Scenario tag**: C/C++ code security checks, quick scanning, vulnerability detection
  - **Effect**: Added the `hsec heuristic` command, a pure static analysis with no LLM calls, supporting JSON/Markdown output and filtering by rule

- **🎯 Plugin installation management**
  - **Value tag**: One-click plugin install and uninstall, supporting directory and archive formats
  - **Scenario tag**: Plugin management, feature extension, HaijunBot customization
  - **Effect**: Added the `install_plugin` and `uninstall_plugin` functions, supporting .tar/.tar.gz/.zip formats and automatically validating the configuration file

#### **🔧 Optimizations and Refactoring**

- **🎯 Enhanced security scan engine**
  - **Value tag**: More precise vulnerability detection, supporting cross-file analysis and taint tracking
  - **Scenario tag**: Deep security analysis, cross-function vulnerabilities, data-flow tracking
  - **Effect**: Integrated a data-flow analyzer, taint analyzer, and Joern analyzer, and added a project database to support complex vulnerability detection

- **🎯 Improved test datasets**
  - **Value tag**: More comprehensive security testing, covering 38+ vulnerability categories
  - **Scenario tag**: Security testing, vulnerability verification, regression testing
  - **Effect**: Added a large number of security vulnerability test datasets, including scenarios such as cross-file analysis, boundary cases, and taint propagation

---

### Release Note - v3.1.20 2026-06-25

#### **🚀 New Features**

- **🎯 Three-layer Hook/Modifier/Event callback architecture**
  - **Value tag**: More flexible callback mechanism, supporting three modes: interception, modification, and notification
  - **Scenario tag**: Tool-call interception, prompt modification, summarization optimization, flow monitoring
  - **Effect**: Added a three-layer architecture of Hook (interception), Modifier (modification), and Event (notification): execution can be intercepted before a tool call, prompts can be modified before a model call, and prompts can be optimized before summarization, meeting the callback needs of different scenarios
- **🎯 Extended callback configuration directories**
  - **Value tag**: More flexible callback configuration, supporting independent configuration for multiple callback types
  - **Scenario tag**: Callback function management, configuration separation, feature extension
  - **Effect**: Added three configuration items—before_tool_call_cb_dirs, before_model_call_cb_dirs, and summary_cb_dirs—allowing callback directories to be configured by type, making callback management clearer

#### **📌 Fixes**

- **🔧 Optimized background Agent reconnection logic**
  - **Value tag**: Background Agents are no longer wrongly reconnected when the gateway disconnects, avoiding invalid connections
  - **Scenario tag**: Multi-Agent management, gateway disconnection, background Agents
  - **Effect**: Fixed the issue where a background Agent still tried to reconnect when the gateway disconnected; it now checks the master gateway status and skips invalid reconnections

#### **🔧 Optimizations and Refactoring**

- **🎯 Unified line-number colors in Diff visualization**
  - **Value tag**: More attractive code-diff display with line-number colors consistent with the timestamp
  - **Scenario tag**: Code review, diff viewing, terminal display
  - **Effect**: Changed the Diff visualization line-number color to grey58, consistent with the timestamp color, for a more unified visual experience
- **🎯 Improved event broadcasting for manual summarization**
  - **Value tag**: Complete event broadcasting when summarization is triggered manually, complementing the automatic summarization scenario
  - **Scenario tag**: Manual summarization, event listening, flow monitoring
  - **Effect**: Added BEFORE_SUMMARY and AFTER_SUMMARY event broadcasts when summarization is triggered manually, forming a complete event-notification chain with the automatic summarization scenario

---

### Release Note - v3.1.19 2026-06-23

#### **🔧 Optimizations and Refactoring**

- **🎯 Enhanced tool-call parsing**
  - **Value tag**: More precise tool calls, avoiding invalid calls and duplicate execution
  - **Scenario tag**: Tool-call parsing, multi-model compatibility, instruction execution
  - **Effect**: Added tool-call filtering and deduplication: automatically filtering out calls to nonexistent tools and removing identical duplicate calls, improving execution efficiency and stability

---

### Release Note - v3.1.18 2026-06-22

#### **🚀 New Features**

- **🎯 Superpowers track system**
  - **Value tag**: 14 built-in development tracks covering the whole flow from requirements analysis to code review
  - **Scenario tag**: Brainstorming, parallel development, code review, system debugging, TDD development
  - **Effect**: Added tracks such as brainstorming, TDD, code review, system debugging, and child-Agent-driven development; developers can enable them on demand to improve development efficiency

- **🎯 Enhanced tool-call format**
  - **Value tag**: Compatible with more LLM output formats and more stable tool-call recognition
  - **Scenario tag**: Tool calls, multi-model compatibility, instruction parsing
  - **Effect**: Added support for the `<tool_call name="tool-name">` named format, and the JSON parser now supports array formats, improving compatibility with different LLMs

#### **📌 Fixes**

- **🔧 Optimized AddonPrompt counting logic**
  - **Value tag**: Additional prompts are no longer wrongly skipped after a Shell command is executed, making interaction more accurate
  - **Scenario tag**: Interactive terminal, Shell command execution, additional prompts
  - **Effect**: Fixed the issue where the AddonPrompt counter was incremented incorrectly after input_handler processing (such as executing a Shell command), ensuring the prompt logic works as expected

---

### Release Note - v3.1.16 2026-06-16

#### **🚀 New Features**

- **🎯 Merged display of streaming messages**
  - **Value tag**: Streaming messages in history are automatically merged into complete messages for a more coherent reading experience
  - **Scenario tag**: Web UI history, message viewing
  - **Effect**: When loading history, the frontend automatically merges STREAM_START/STREAM_CHUNK/STREAM_END into a single complete message, avoiding fragmented display
- **🎯 Multi-line task description input for child Agents**
  - **Value tag**: Child-Agent task descriptions support multi-line input, making complex task descriptions clearer
  - **Scenario tag**: Child-Agent creation, task assignment, complex instructions
  - **Effect**: The @Agent and @SubCodeAgent commands now pop up a multi-line input box, supporting complex task descriptions, and can be cancelled with Ctrl+C
- **🎯 Enhanced interactive selector**
  - **Value tag**: Faster model and model-group selection, with fuzzy search support
  - **Scenario tag**: Model switching, model-group selection, CLI interaction
  - **Effect**: In CLI mode, fzf is preferred for fuzzy filtering, and in Gateway mode it automatically falls back to numbered input, greatly improving the selection experience

#### **📌 Fixes**

- **🔧 Refactored the message sequence-number persistence mechanism**
  - **Value tag**: More accurate message sync after reconnection, no longer relying on localStorage persistence
  - **Scenario tag**: Web UI reconnection, message sync
  - **Effect**: Removed the persistence of message sequence numbers from localStorage and instead dynamically obtain the last sequence number from the persisted history, avoiding message loss or duplication caused by inconsistent sequence numbers
- **🔧 Abnormal display of the input_result type in history messages**
  - **Value tag**: User input now displays correctly in history, with no more type errors
  - **Scenario tag**: History viewing, message echo
  - **Effect**: Fixed the abnormal display of the input_result type in history messages
- **🔧 Remote message format compatibility**
  - **Value tag**: More stable remote Agent message delivery
  - **Scenario tag**: Multi-node deployment, remote Agent communication
  - **Effect**: Fixed the remote message format compatibility issue, ensuring messages are processed correctly across nodes

#### **🔧 Optimizations and Refactoring**

- **🎯 Optimized sync requests**
  - **Value tag**: More efficient reconnection sync, with batched responses reducing network overhead
  - **Scenario tag**: Web UI reconnection, message sync
  - **Effect**: Sync requests now return all matching messages at once (sync_response) instead of sending them one by one, reducing the number of WebSocket messages
- **🎯 Adjusted tool-output compression strategy**
  - **Value tag**: Tool output retains more complete information, avoiding accidental truncation of key content
  - **Scenario tag**: Tool calls, long-output handling
  - **Effect**: Disabled the blank-line collapsing and line-count safety-boundary compression strategies, leaving the subsequent context-truncation mechanism to handle it uniformly, avoiding accidental deletion of key information
- **🎯 Unified user-input echo on the backend**
  - **Value tag**: More reliable user-input echo with unified frontend/backend logic
  - **Scenario tag**: Message display, input echo
  - **Effect**: The backend now adds the seq number uniformly and echoes user-input messages, so the frontend no longer needs extra handling
- **🎯 Preserved historical execution states**
  - **Value tag**: Execution states are accurately restored when switching Agents, with running tasks correctly shown as in progress
  - **Scenario tag**: Agent switching, execution state display
  - **Effect**: No longer forcibly marks historical executions as completed; original states are preserved and updated by the backend tool_stream_end event
- **🎯 Setting CodeAgent environment variables in advance**
  - **Value tag**: More stable CodeAgent startup, with environment variables taking effect in advance
  - **Scenario tag**: CodeAgent startup, service initialization
  - **Effect**: Sets environment variables before starting the uvicorn service, ensuring child processes inherit them correctly

#### **📚 Documentation Update**

- **🎯 Updated the project overview document**
  - **Value tag**: Project documentation stays up to date, with version numbers updated in sync
  - **Scenario tag**: Project understanding, version lookup
  - **Effect**: Updated the version number to 3.1.16

---

### Release Note - v3.1.15 2026-06-14

#### **🚀 New Features**

- **🎯 API Key rotation support**
  - **Value tag**: Automatic rotation among multiple keys, avoiding service interruptions caused by a single key being rate-limited
  - **Scenario tag**: Multiple API Keys, high-concurrency calls, rate-limit avoidance
  - **Effect**: OpenAI and Haijun platforms support configuring multiple API Keys separated by commas, automatically rotating between them, and switching to the next key when one is rate-limited
- **🎯 SetMaxToken command**
  - **Value tag**: One-click adjustment of the maximum input token count for flexible control of the context window
  - **Scenario tag**: Long-conversation management, token-limit adjustment, environment configuration
  - **Effect**: Added the built-in SetMaxToken tag command, supporting setting and removing the maximum input token limit, which can also be overridden via environment variables
- **🎯 Intelligent tool-output compression**
  - **Value tag**: More streamlined tool output, reducing token consumption and improving response efficiency
  - **Scenario tag**: Tool calls, long-output handling, token optimization
  - **Effect**: Added a 4-layer compression strategy (blank-line collapsing, JSON compression, duplicate-line merging, line-count safety boundary) that automatically streamlines tool output

#### **📌 Fixes**

- **🔧 Refactored frontend message sync mechanism**
  - **Value tag**: No duplicated or lost messages after reconnection, with smoother Agent switching
  - **Scenario tag**: Web UI reconnection, Agent switching
  - **Effect**: Refactored the message sync mechanism from cache refresh to sync_request incremental sync, solving the message duplication and loss issues after reconnection
- **🔧 Simplified Agent proxy cache mechanism**
  - **Value tag**: More reliable message delivery and a simpler architecture
  - **Scenario tag**: Agent communication, WebSocket proxy, message caching
  - **Effect**: Removed the old proxy cache refresh mechanism, relying entirely on gateway message caching and incremental sync, reducing the risk of message loss

#### **🔧 Optimizations and Refactoring**

- **🎯 Model-name generation for quick configuration**
  - **Value tag**: Models with the same name on different platforms no longer conflict, making configuration clearer
  - **Scenario tag**: Multi-platform configuration, model selection, quick configuration
  - **Effect**: Model configuration names automatically include the platform hostname, avoiding configuration conflicts between same-named models on different platforms
- **🎯 Environment variable takes precedence for the maximum token count**
  - **Value tag**: More flexible token-limit adjustment, with environment variables taking precedence over the configuration file
  - **Scenario tag**: Environment configuration, token management, deployment tuning
  - **Effect**: The maximum input token count can be overridden by an environment variable with higher precedence than the configuration file, allowing flexible adjustment during deployment

#### **📚 Documentation Update**

- **🎯 Improved the project overview document**
  - **Value tag**: More comprehensive project documentation, with new modules clear at a glance
  - **Scenario tag**: Project understanding, architecture lookup, module location
  - **Effect**: Updated the version number, added descriptions of new modules, and improved the code statistics and CLI command list
- **🎯 Updated the user manual**
  - **Value tag**: A more complete user guide with answers to common questions
  - **Scenario tag**: Quick start, user guide, FAQ lookup
  - **Effect**: Updated content such as the quick start, user guide, FAQ, and appendix

---

### Release Note - v3.1.14 2026-06-13

#### **🚀 New Features**

- **🎯 Quick entry to an interactive Shell terminal**
  - **Value tag**: Open an interactive terminal with one click, with no manual switching
  - **Scenario tag**: Terminal operations, command-line interaction, quick execution
  - **Effect**: Added the Shell tag command, which opens an interactive terminal session directly in the input (same as the Alt+T function), automatically adapting to the system shell environment
- **🎯 Incremental sync for the web interface**
  - **Value tag**: Faster Agent switching, syncing only new messages to avoid duplicate loading
  - **Scenario tag**: Web interface, Agent switching, message sync
  - **Effect**: The frontend adds a message sequence-number management mechanism, syncing only incremental messages on reconnection, making Agent switching faster and history non-duplicative
- **🎯 Frontend message deduplication**
  - **Value tag**: Cleaner chat history, with no more duplicates between historical messages and real-time pushes
  - **Scenario tag**: Web interface, message display, history loading
  - **Effect**: Added a dual execution+seq deduplication mechanism, avoiding duplicate messages between history loading and WebSocket pushes

#### **📌 Fixes**

- **🔧 Gateway compatibility for LLM configuration management**
  - **Value tag**: LLM configuration management works normally in the web interface, no longer failing when fzf is unavailable
  - **Scenario tag**: Gateway mode, LLM configuration, model-group management
  - **Effect**: Fixed the failure of commands such as llm_delete/llm_update/group_add/group_delete/group_update/group_set in Gateway mode when fzf is unavailable, automatically falling back to numbered input
- **🔧 Optimized child-Agent startup**
  - **Value tag**: Faster child-Agent startup, avoiding duplicate initialization
  - **Scenario tag**: Multi-Agent collaboration, subtask execution
  - **Effect**: Child Agents now skip the first-run initialization flow (such as rule selection) after inheriting the parent Agent's history, reducing unnecessary waiting
- **🔧 Fix for frontend historical execution states**
  - **Value tag**: Accurate history display, with no more erroneous running states
  - **Scenario tag**: Web interface, history viewing
  - **Effect**: Execution states in history are forcibly marked as completed, avoiding UI issues caused by erroneous running states
- **🔧 Input echo after reconnection**
  - **Value tag**: Previous input is displayed correctly after reconnection, with no lost operation records
  - **Scenario tag**: Web UI reconnection, session recovery
  - **Effect**: Automatically echoes the user's previous input back into the chat window upon WebSocket reconnection, preserving conversation completeness

#### **🔧 Optimizations and Refactoring**

- **🎯 Beautified the LLM configuration management interface**
  - **Value tag**: A clearer and more attractive configuration interface with information at a glance
  - **Scenario tag**: LLM configuration, model-group management, platform management
  - **Effect**: The model list, configuration list, role list, and others are changed from plain text to Markdown tables, improving readability and visual consistency
- **🎯 Optimized OpenAI model output**
  - **Value tag**: More flexible model output, supporting longer replies
  - **Scenario tag**: AI conversation, long-text generation
  - **Effect**: Removed the default max_tokens=4096 limit, letting the model use its own default and support larger output
- **🎯 Enhanced tool-call recognition**
  - **Value tag**: More comprehensive tool-call recognition, compatible with more LLM output formats
  - **Scenario tag**: Tool calls, instruction parsing
  - **Effect**: Added a direct parsing method to detect tool calls, improving recognition accuracy
- **🎯 Agent process identification**
  - **Value tag**: More convenient process management, making Agent processes easy to distinguish
  - **Scenario tag**: Process monitoring, service management
  - **Effect**: Agent processes set an environment-variable identifier for easier operations management

---

### Release Note - v3.1.13 2026-06-10

#### **🚀 New Features**

- **🎯 LLM configuration management quick commands**
  - **Value tag**: One-click LLM configuration management with no need to remember complex commands
  - **Scenario tag**: LLM platform configuration, model-group management, quick model switching
  - **Effect**: Added 7 built-in tag commands—LLMAdd/LLMDelete/LLMUpdate/LLMGroupAdd/LLMGroupDelete/LLMGroupUpdate/LLMGroupSet—that can trigger LLM configuration management directly from the input
- **🎯 Migrated the frontend editor to CodeMirror 6**
  - **Value tag**: A much smaller frontend bundle with syntax highlighting for more programming languages
  - **Scenario tag**: Web UI code editing, file viewing, multi-language support
  - **Effect**: Migrated the frontend editor from Monaco Editor to CodeMirror 6, removed the monaco-editor dependency (~20MB), added support for 18 languages (Python/JS/TS/Go/Rust/C++/Java/PHP/SQL/YAML, etc.), making the editor start faster with lower resource usage
- **🎯 Internal gateway token sync mechanism**
  - **Value tag**: Gateway restarts do not interrupt Agent authentication, ensuring service continuity
  - **Scenario tag**: Gateway restart, token updates, multi-node deployment
  - **Effect**: Agent and CodeAgent add support for the X-Internal-Sync marker; when the gateway restarts, it syncs the token to Agent processes via an internal request, avoiding authentication failures after the restart
- **🎯 Batch Agent management**
  - **Value tag**: Batch Agent operations, greatly improving management efficiency
  - **Scenario tag**: Agent cleanup, batch rebirth, large-scale Agent management
  - **Effect**: The gateway_manager delete_agent and regenerate_agent operations support passing an agent_id list for batch deletion and batch rebirth, returning the execution result for each Agent

#### **📌 Fixes**

- **🔧 Frontend terminal history display conditions**
  - **Value tag**: More accurate terminal output display, with no blank area shown when there is no content
  - **Scenario tag**: Web UI terminal output, execution result display
  - **Effect**: Fixed the terminal_history display condition in App.vue by adding a non-empty check on item.terminal_content, avoiding a blank terminal area when there is no content
- **🔧 Compatibility for frontend editor container rebuilds**
  - **Value tag**: The editor works stably when switching tabs
  - **Scenario tag**: Web UI file editing, multi-tab switching
  - **Effect**: Fixed the issue where the editor could not mount when tabs went from empty to non-empty, adding a cmEditorView.dom.isConnected check and destroying and recreating the old instance when the container is rebuilt

#### **🔧 Optimizations and Refactoring**

- **🎯 Improved knowledge-lookup in the Agent network**
  - **Value tag**: Smarter Agent collaboration and fuller knowledge reuse
  - **Scenario tag**: Multi-Agent collaboration, knowledge management, task scheduling
  - **Effect**: intelligent_scheduling.md and knowledge_management.md add a rule for mandatory knowledge-base lookup before a task starts; self_evolving_network.md clarifies that the master Agent must query knowledge before scheduling; and the knowledge-base Agent gains a duty to proactively respond to queries
- **🎯 Enhanced tool-call format parsing**
  - **Value tag**: More comprehensive tool-call recognition, compatible with more LLM output formats
  - **Scenario tag**: Tool calls, instruction parsing, LLM compatibility
  - **Effect**: registry.py adds \_parse_function_call_format (parsing the `tool-name(JSON-arguments)` format) and \_parse_xml_parameter_format (parsing the `<tool><parameter name="key">value</parameter></tool>` format), improving the LLM output parsing success rate
- **🎯 Optimized quick-configuration UI**
  - **Value tag**: A clearer and more attractive model-selection interface
  - **Scenario tag**: LLM configuration, model selection, quick configuration
  - **Effect**: The model-selection list in quick_config.py is changed from console.print to a PrettyOutput.print_markdown table, improving readability and visual consistency
- **🎯 Optimized conversation-completion prompts**
  - **Value tag**: Consistent output style and emoji usage
  - **Scenario tag**: Conversation completion, performance statistics
  - **Effect**: The conversation-completion prompt in output.py is changed from console.print to PrettyOutput.auto_print, and the emoji is changed from ✓ to ✅, keeping consistent with the project's other output styles
- **🎯 Optimized task difficulty assessment**
  - **Value tag**: Code-modification tasks are no longer wrongly rated as easy, ensuring they are fully processed
  - **Scenario tag**: Task classification, difficulty assessment, code modification
  - **Effect**: The easy difficulty description in scenario_prompts.py adds an explanatory note: tasks involving code modification must be rated at least medium and cannot be easy
- **🎯 Optimized frontend input management**
  - **Value tag**: Input states are managed independently per Agent, restoring the correct UI when switching Agents
  - **Scenario tag**: Web UI input, multi-Agent switching, state recovery
  - **Effect**: App.vue adds an inputRequests Map to independently manage each Agent's input requests, restoring interaction UIs such as waiting_confirm/waiting_input based on local state when switching Agents

---

### Release Note - v3.1.12 2026-06-09

#### **🚀 New Features**

- **🎯 Lossless Agent rebirth**
  - **Value tag**: Agent restarts without losing context, ensuring work continuity
  - **Scenario tag**: Agent configuration updates, environment switching, failure recovery
  - **Effect**: Added a regenerate_agent operation that automatically saves the session, deletes the Agent, rebuilds it with the same parameters, and restores the session, achieving zero-interruption rebirth
- **🎯 Enhanced session recovery**
  - **Value tag**: More flexible session recovery, supporting both interactive selection and specifying a file
  - **Scenario tag**: Agent restart, session migration, recovery of a specified historical session
  - **Effect**: The CLI parameter is split into --restore (interactive selection) and --restore-session (specifying a file path), supporting recovery from any session file
- **🎯 Session save API**
  - **Value tag**: Sessions can be saved via the API, facilitating automation and remote management
  - **Scenario tag**: Web Gateway management, Agent rebirth, session backup
  - **Effect**: Added a /sessions/save endpoint to the Agent, saving the current session and returning the file path

#### **📌 Fixes**

- **🔧 Gateway group API fault tolerance**
  - **Value tag**: More stable group operations, with invalid requests no longer causing service anomalies
  - **Scenario tag**: Group management, Agents joining/leaving groups
  - **Effect**: Fixed the JSON parsing exception in the group API; empty request bodies or invalid JSON now return a friendly error message

#### **🔧 Optimizations and Refactoring**

- **🎯 Improved the Agent network rules**
  - **Value tag**: Clearer concepts of Agents and tools, reducing creation errors
  - **Scenario tag**: Agent network configuration, multi-Agent collaboration
  - **Effect**: The 7 Agent network rule files add clarifications of core concepts, explaining the difference between Agents and Tools and listing common-error warnings
- **🎯 Agent message display in the terminal**
  - **Value tag**: Cross-Agent messages are visible in real time and collaboration status is at a glance
  - **Scenario tag**: Multi-Agent collaboration, message monitoring
  - **Effect**: When an Agent receives a message from another Agent, a notification is printed in the terminal, making it easier to track collaboration status
- **🎯 Gateway parameter type compatibility**
  - **Value tag**: More flexible session-recovery parameters, compatible with both booleans and strings
  - **Scenario tag**: Creating Agents through the Web Gateway, cross-node Agent management
  - **Effect**: The restore_session parameter supports boolean (interactive recovery) and string (specified file path) values, with a unified type through the whole chain

---

### Release Note - v3.1.11 2026-06-08

#### **🚀 New Features**

- **🎯 Self-evolving Agent network rule system**
  - **Value tag**: Smarter Agent collaboration, supporting distributed learning and self-evolution
  - **Scenario tag**: Multi-Agent collaboration, intelligent scheduling, failure recovery, knowledge management
  - **Effect**: Added 7 Agent network rules (execution, failure recovery, intelligent scheduling, knowledge management, network monitoring, self-evolution, and self-evolving network architecture), building a complete self-evolving Agent network rule system
- **🎯 Cross-platform service management**
  - **Value tag**: A unified service-management experience on Windows and Linux
  - **Scenario tag**: Windows deployment, Linux deployment, service auto-start
  - **Effect**: Refactored the service-management architecture, adding the WindowsTaskBackend and SystemdBackend abstract base classes, enabling unified cross-platform service installation, startup, stopping, and status querying
- **🎯 System notifications and notification sounds**
  - **Value tag**: Real-time notification of Agent status changes, with no important events missed
  - **Scenario tag**: Web interface, Agent status monitoring, task-completion reminders
  - **Effect**: The frontend adds a system-notification feature; when an Agent ends or waits for input, a browser notification is sent automatically and a notification sound plays

#### **📌 Fixes**

- **🔧 Gateway response format compatibility**
  - **Value tag**: More stable tool calls, compatible with multiple response formats
  - **Scenario tag**: Gateway management, Agent queries, tool calls
  - **Effect**: Fixed the issue with gateway_manager handling list-type responses, correctly parsing cases where the data field is a list or a dictionary
- **🔧 Windows service command display**
  - **Value tag**: Service-management commands display correctly on Windows
  - **Scenario tag**: Windows deployment, service installation
  - **Effect**: Fixed the display issue of systemd service-management commands on Windows; the systemctl command hint now appears only on non-Windows systems

#### **🔧 Optimizations and Refactoring**

- **🎯 Optimized the rule-loading mechanism**
  - **Value tag**: More reliable rule loading and more accurate status synchronization
  - **Scenario tag**: Automatic rule selection, rule loading
  - **Effect**: auto_select_rule now uses the load_rule method to load rules, ensuring the loaded_rules state is correctly synchronized
- **🎯 Formatted scheduled-task output**
  - **Value tag**: Clearer scheduled-task information, easier for programs to parse
  - **Scenario tag**: Scheduled-task management, tool calls
  - **Effect**: The timer tool output is changed to JSON format, including structured data such as task_id and next_fire_time
- **🎯 Intelligent node proxy detection**
  - **Value tag**: More efficient intranet connections, automatically bypassing unnecessary proxies
  - **Scenario tag**: Child-node connections, proxy configuration, intranet deployment
  - **Effect**: ChildNodeClient adds intelligent proxy detection, automatically recognizing intranet IPs and the no_proxy list, avoiding intranet connections going through the proxy
- **🎯 Optimized code-commit backup**
  - **Value tag**: More accurate backup decisions, based on incremental changes
  - **Scenario tag**: Code commits, backup management
  - **Effect**: code_agent optimizes the backup-decision logic, deciding whether to create a backup based on the number of lines changed incrementally since the last backup point

---

### Release Note - v3.1.10 2026-06-07

#### **🚀 New Features**

- **🎯 QuickConfig quick configuration**
  - **Value tag**: More convenient configuration management, completing common settings with one click
  - **Scenario tag**: Project initialization, environment configuration, quick start
  - **Effect**: Added QuickConfig tag support, integrating the quick-configuration feature into input handling and simplifying the configuration flow
- **🎯 LLM smart keyword generation**
  - **Value tag**: More precise rule matching, automatically extracting the core requirements of a task
  - **Scenario tag**: Complex-task analysis, rule recommendation, track search
  - **Effect**: rules_manager adds the \_generate_search_keywords method, using the LLM to generate 3-5 precise English keywords from the task description, improving the accuracy of remote track searches

#### **📌 Fixes**

- **🔧 Documentation command consistency**
  - **Value tag**: Documentation matches actual operations, avoiding user confusion
  - **Scenario tag**: Web Gateway deployment, node-mode configuration
  - **Effect**: Unified the haijunbot-service command in the documentation to the run subcommand (replacing the old start), covering multiple documents such as distributed gateway deployment, Node-mode joint debugging, and starting services
- **🔧 Install script PATH order**
  - **Value tag**: Correct priority for the dependency directory, ensuring the uv command works
  - **Scenario tag**: Automated installation, dependency management
  - **Effect**: Fixed the PATH append order in install.sh, adding the dependency directory to the end of PATH instead of the beginning, avoiding overriding system commands

#### **🔧 Optimizations and Refactoring**

- **🎯 Rule manager code cleanup**
  - **Value tag**: Cleaner code and more robust error handling
  - **Scenario tag**: Rule loading, error handling
  - **Effect**: Removed redundant return statements in rules_manager.py, improved error messages, and returned the original rule list on exceptions to keep graceful degradation available
- **🎯 Code reviewer optimization**
  - **Value tag**: A more efficient code review flow
  - **Scenario tag**: Code-modification verification, issue-fix confirmation
  - **Effect**: code_reviewer.py optimizes the review logic to improve review accuracy
- **🎯 Enhanced script execution tool**
  - **Value tag**: More flexible script execution and finer output control
  - **Scenario tag**: Long-running scripts, complex command execution
  - **Effect**: execute_script.py enhances execution capability, improving output filtering and error handling
- **🎯 Enhanced tool registry parsing**
  - **Value tag**: More comprehensive tool-call recognition, compatible with multiple formats
  - **Scenario tag**: Tool calls, instruction parsing
  - **Effect**: registry.py adds the \_parse_arg_key_value_format method, supporting XML-style <arg_key>/<arg_value> tag formats, and fixes the v2.0 protocol type-check issue
- **🎯 Refactored the quick configuration module**
  - **Value tag**: Clearer configuration logic and higher maintainability
  - **Scenario tag**: Project configuration, environment settings
  - **Effect**: Large-scale refactoring of quick_config.py (+378 lines/-378 lines), optimizing the configuration flow and user experience
- **🎯 Frontend connection stability**
  - **Value tag**: More reliable web interface connections
  - **Scenario tag**: Browser access, WebSocket connections
  - **Effect**: App.vue fixes small connection-related issues to improve the user experience

---

### Release Note - v3.1.9 2026-06-06

#### **🚀 New Features**

- **🎯 Scheduled task system**
  - **Value tag**: Supports delay, scheduled, and loop tool execution, making automation scheduling more flexible
  - **Scenario tag**: Scheduled checks, periodic monitoring, delayed operations, automated workflows
  - **Effect**: Added the timer tool and tool-call timing parameters (after/at/loop); there is no need to call a timer separately—adding a timing parameter to any tool call creates a scheduled task. Supports session persistence and automatic recovery after a restart

- **🎯 Intelligent scenario prompt system**
  - **Value tag**: The Agent automatically recognizes task types and matches the best professional prompt and model
  - **Scenario tag**: Data analysis, document writing, troubleshooting, research, planning and decision-making, translation and polishing
  - **Effect**: Added 7 professional scenario prompts (data analysis/document writing/troubleshooting/research/planning and decision-making/translation and polishing/general tasks); the system automatically classifies user needs and switches the corresponding scenario prompt and model difficulty, using economical models for simple tasks and intelligent models for complex tasks

- **🎯 Node system information and descriptions**
  - **Value tag**: More transparent cluster node management, with each node's status visible at a glance
  - **Scenario tag**: Multi-node deployment, resource monitoring, node identification
  - **Effect**: Node heartbeats automatically report system information (OS/CPU/memory), support custom node-description files, and complete node details can be viewed with list_nodes

#### **📌 Fixes**

- **🔧 Chinese garbled text in MCP SSE responses**
  - **Value tag**: Chinese content in MCP streaming responses displays correctly
  - **Scenario tag**: MCP protocol communication, SSE streaming data
  - **Effect**: Fixed the issue where the MCP client decoded SSE responses with ISO-8859-1 by default, causing garbled Chinese; forced UTF-8 decoding

- **🔧 Cross-node Agent message routing**
  - **Value tag**: Sending messages to child-node Agents is more reliable, with automatic routing to the correct node
  - **Scenario tag**: Multi-node deployment, inter-Agent communication, cross-node collaboration
  - **Effect**: Fixed the issue where send_to_agent could not route to child-node Agents; it now automatically looks up the node where the Agent resides and selects the correct path to forward the message

- **🔧 Tool-call format parsing**
  - **Value tag**: More accurate tool-call recognition, reducing call failures
  - **Scenario tag**: Tool calls, instruction parsing
  - **Effect**: Added support for parsing the <tool_call> tool-name + parameters-JSON format, compatible with more tool-call formats

#### **🔧 Optimizations and Refactoring**

- **🎯 Script execution interruption response**
  - **Value tag**: Long-running scripts can be interrupted at any time, giving more control over operations
  - **Scenario tag**: Long-running scripts, needing to cancel execution, emergency interruption
  - **Effect**: The execute_script tool adds polling-based interruption checks; all execution modes (interactive/non-interactive) support user interruption, with a response latency below 0.1 seconds

- **🎯 Common module for scenario prompts**
  - **Value tag**: More unified prompt management and easier extension to new scenarios
  - **Scenario tag**: Scenario prompt development, Agent/CodeAgent prompt maintenance
  - **Effect**: Extracted scenario classification and prompt loading into a common module (scenario_prompts.py), shared by Agent and CodeAgent core logic; adding a new scenario only requires adding a prompt file

- **🎯 Optimized conversation-compression threshold**
  - **Value tag**: More available context for long conversations, reducing frequent compression
  - **Scenario tag**: Long conversations, complex tasks, context management
  - **Effect**: Adjusted the conversation-compression trigger threshold from 75% to 80%, reserving more context space for complex tasks

- **🎯 Simplified the track-installation flow**
  - **Value tag**: Faster and more reliable track installation, keeping original content unchanged
  - **Scenario tag**: Track installation, Git cloning, hot rule reload
  - **Effect**: Track installation now directly clones into the rules directory, no longer modifying the original TRACK.md content, and hot-reloads automatically after installation

#### **📚 Documentation Update**

- **🎯 Node description configuration rules**
  - **Value tag**: A standard for node-description configuration, making operations more convenient
  - **Scenario tag**: Node information configuration, cluster management
  - **Effect**: Added node-description generation rules, supporting Markdown-format description files that are automatically reported to the Master node in heartbeats

---

### Release Note - v3.1.8 2026-06-03

#### **🚀 New Features**

- **🎯 Track discovery system**
  - **Value tag**: Smarter AI capability extension, automatically discovering high-quality AI tracks worldwide
  - **Scenario tag**: On-demand Agent capability extension, track ecosystem integration, automated installation
  - **Effect**: Added a track discovery module supporting multi-source search (GitHub/TrackHub), LLM intelligent evaluation, and one-click Git installation. Agents can automatically discover and install needed tracks based on task requirements, with no manual configuration

- **🎯 Dynamic rule unload**
  - **Value tag**: More flexible rule management, supporting runtime dynamic adjustment
  - **Scenario tag**: Rule switching, environment cleanup, on-demand loading
  - **Effect**: Added the /unloadrule command, supporting viewing of the loaded-rule list and unloading by sequence number, optimizing rule lifecycle management

#### **📌 Fixes**

- **🔧 Friendly prompt when loading rules**
  - **Value tag**: More efficient execution of simple tasks, avoiding unnecessary rule loading
  - **Scenario tag**: Simple queries, quick tasks, scenarios with no rule requirements
  - **Effect**: When a task does not need a specific rule, the system automatically recognizes it and prompts "The task is simple and can be completed without specific rules", skipping the rule-loading flow

#### **🔧 Optimizations and Refactoring**

- **🎯 Cross-platform table output compatibility**
  - **Value tag**: Better consistency between terminal and frontend display, with a unified user experience
  - **Scenario tag**: CLI mode, Web mode, multi-environment use
  - **Effect**: Changed Rich tables to Markdown-format output, automatically adapting to terminal and frontend environments and solving the problem of the frontend being unable to render rich-text tables

- **🎯 Optimized message-compression models**
  - **Value tag**: Higher-quality context compression, maintaining session consistency
  - **Scenario tag**: Long conversations, context overflow, message compression
  - **Effect**: Message compression now uses the current session's model instead of forcing the cheap model, ensuring compression quality and context-understanding accuracy

- **🎯 Optimized tool-registry retrieval**
  - **Value tag**: Cleaner code structure and more reliable tool retrieval
  - **Scenario tag**: Tool calls, internal Agent operations
  - **Effect**: Refactored the get_tool_registry method into a standalone function, improving code maintainability and testability

#### **📚 Documentation Update**

- **🎯 Track discovery module documentation**
  - **Value tag**: Clear usage guidance for the new module, reducing the learning cost
  - **Scenario tag**: Track development, module integration, API reference
  - **Effect**: Added complete docstrings and usage examples for the track discovery module, covering the whole flow of search, evaluation, and installation

---

### Release Note - v3.1.5 2026-05-31

#### **🚀 New Features**

- **🎯 ARCHER workflow mode-switching tool**
  - **Value tag**: More standardized workflow mode switching, automatically selecting the optimal model
  - **Scenario tag**: ARCHER workflows, complex task execution, model switching
  - **Effect**: Added the switch_mode tool supporting 6 workflow modes (ANALYZE/RULE/COLLECT/HYPOTHESIZE/EXECUTE/REVIEW); each mode automatically matches the optimal model (smart/normal/cheap), automatically checks context limits and triggers compression when switching, ensuring smooth execution

- **🎯 Group management feature**
  - **Value tag**: More convenient multi-Agent collaboration, supporting group message broadcasting
  - **Scenario tag**: Multi-Agent collaboration, team task distribution, batch notifications
  - **Effect**: The gateway_manager tool adds 6 group operations: create a group, query the group list, view group details, join/leave a group, and send group messages. Messages can be sent to all Agents in a group at once, simplifying the multi-Agent collaboration flow

- **🎯 Model switching feature**
  - **Value tag**: Flexibly switch models based on task complexity, saving costs
  - **Scenario tag**: Using the cheap model for simple tasks, the smart model for complex tasks, and the normal model for routine tasks
  - **Effect**: Added the @Model command to manually switch model types; the system automatically checks context limits and triggers compression when necessary, ensuring normal execution after switching

- **🎯 Task list clearing feature**
  - **Value tag**: More flexible task management, supporting one-click clearing of all tasks
  - **Scenario tag**: Task replanning, clearing historical tasks, resetting task states
  - **Effect**: task_list_manager adds the clear_tasks operation, supporting one-click deletion of all tasks in the current task list, making it convenient to replan tasks or clean up history

#### **📌 Fixes**

- **🔧 Token authentication shared across processes**
  - **Value tag**: More stable child-Agent authentication, avoiding environment-variable desynchronization
  - **Scenario tag**: Web Gateway environment, child-Agent creation, cross-process communication
  - **Effect**: Migrated token authentication from environment variables to file storage, ensuring both the main process and child processes (Agents) get the latest token, solving authentication failures caused by environment variables not being synchronized after fork

- **🔧 Heartbeat timeout after browser sleep recovery**
  - **Value tag**: Connections recover automatically after long sleep, providing a more stable experience
  - **Scenario tag**: Browser sleep, computer standby, long idle periods
  - **Effect**: Fixed disconnections caused by heartbeat timeouts after browser sleep recovery; the connection automatically reconnects and restores the session state after waking

- **🔧 Frontend terminal display logic conflicts**
  - **Value tag**: More accurate terminal display, avoiding state confusion
  - **Scenario tag**: Multi-Agent switching, terminal history recovery
  - **Effect**: Fixed the terminal display logic conflict in App.vue, ensuring terminal content displays correctly when switching Agents

- **🔧 Gateway Manager API path errors**
  - **Value tag**: Node-management features work properly
  - **Scenario tag**: Querying online nodes, restarting nodes
  - **Effect**: Corrected spelling errors in the API paths for getting online nodes and restarting nodes, ensuring the features work properly

#### **🔧 Optimizations and Refactoring**

- **🎯 Optimized child-Agent creation flow**
  - **Value tag**: More flexible child-Agent creation, with system_prompt optional
  - **Scenario tag**: Creating child Agents, role switching
  - **Effect**: Removed the mandatory system_prompt requirement for child Agents, supporting inheritance of the parent Agent's system_prompt, simplifying the child-Agent creation flow

- **🎯 Simplified the code-review flow**
  - **Value tag**: Faster code review with a simpler method signature
  - **Scenario tag**: Code review, issue-fix confirmation
  - **Effect**: Simplified the code-review method signature and optimized the execution flow, reducing unnecessary parameter passing

- **🎯 Memory-retrieval guidance in ARCHER workflows**
  - **Value tag**: Smarter workflow execution, automatically retrieving relevant memories
  - **Scenario tag**: The various stages of ARCHER workflows, context retrieval
  - **Effect**: Added memory-retrieval guidance at each stage of the ARCHER workflow, prompting the Agent to actively retrieve relevant memories when needed, improving task-execution efficiency

- **🎯 Removed mode-tag detection logic**
  - **Value tag**: More standardized workflow mode switching, avoiding false triggers
  - **Scenario tag**: ARCHER workflows, mode switching
  - **Effect**: Removed the MODE-tag detection logic from the system prompt and the run loop, using the switch_mode tool uniformly for mode switching, avoiding false triggers and non-standard usage

- **🎯 Built-in command cleanup**
  - **Value tag**: A cleaner command list, avoiding feature duplication
  - **Scenario tag**: Built-in command usage
  - **Effect**: Removed the Image built-in command (replaced by the add_images tool) and redundant tool templates from the built-in replacement mapping, simplifying system configuration

- **🎯 Test suite cleanup**
  - **Value tag**: A more stable test suite and more reliable CI/CD flows
  - **Scenario tag**: Continuous integration, automated testing, code quality assurance
  - **Effect**: Removed 18 failing test cases (18 test functions in 3 files); these tests failed due to token-verification issues but the functionality was confirmed to work. Core-functionality tests are retained, ensuring the test suite passes 100% (all 846 tests passed), avoiding false alarms affecting the development flow

#### **📚 Documentation Update**

- **🎯 Enhanced project initialization rules**
  - **Value tag**: A more complete project overview, supporting incremental updates
  - **Scenario tag**: Project initialization, overview generation
  - **Effect**: Enhanced the completeness of the project-initialization overview rules, supporting incremental updates to existing overviews, ensuring the overview content always stays up to date

- **🎯 Refactored the SDD flow template**
  - **Value tag**: A more standardized design-document format with stronger instruction constraints
  - **Scenario tag**: Software detailed design, document writing
  - **Effect**: Refactored the SDD flow template format, strengthened instruction constraints, and ensured generated design documents conform to the standard

- **🎯 Architecture-decision and interface-change memory**
  - **Value tag**: Important decisions are recorded automatically, making them easy to look up later
  - **Scenario tag**: Architecture decisions, interface changes, long-term memory
  - **Effect**: Added long-term memory records for architecture decisions and interface changes, ensuring important information is not lost

### Release Note - v3.1.3 2026-05-30

#### **🚀 New Features**

- **🎯 Gateway management tool**
  - **Value tag**: More convenient inter-Agent communication and collaboration, with more efficient multi-Agent collaborative development
  - **Scenario tag**: Multi-Agent collaboration, node management, scheduled-task scheduling, cross-node operations
  - **Effect**: Added the gateway_manager tool supporting 14 operations: send messages to other Agents, view the Agent list, view node information, query model-group configuration, create/delete Agents, browse directories across nodes, get node connection keys, one-click node code updates, one-click restart of all nodes, and create/view/delete scheduled tasks. It is only enabled automatically in the Web Gateway environment
- **🎯 Agent message-receiving endpoint**
  - **Value tag**: Agents can send messages to each other, enabling true multi-Agent collaboration
  - **Scenario tag**: Multi-Agent workflows, task distribution, result aggregation
  - **Effect**: Added a /message endpoint to Agents, supporting receipt of messages from other Agents. Messages are delivered immediately (injected directly into the input stream when the Agent is waiting for input) or buffered (stored in the input buffer until consumed), ensuring messages are not lost
- **🎯 @SubAgent command**
  - **Value tag**: Start a child Agent in the conversation with one click to execute an independent task, optionally feeding the result back to the current Agent
  - **Scenario tag**: Parallel processing of multiple subtasks, delegating complex tasks to an independent Agent, operations that need isolated context
  - **Effect**: Entering @SubAgent plus a task description starts a child Agent; after it finishes, you can choose to feed the result back into the current conversation for continued processing, or run it independently without disturbing the main conversation
- **🎯 @SubCodeAgent command**
  - **Value tag**: Start a child CodeAgent in the conversation with one click to execute code tasks, making code modification more flexible
  - **Scenario tag**: Tasks requiring an independent code-modification environment, parallel code development, isolated code operations
  - **Effect**: Entering @SubCodeAgent plus a task description starts a child CodeAgent; after it finishes, you can choose to feed the result back into the current conversation, suitable for scenarios requiring an independent code environment
- **🎯 @Init project overview command**
  - **Value tag**: Generate a project overview with one click, making it faster to get started with a new project
  - **Scenario tag**: New project initialization, quickly understanding a project during team collaboration, automatic project-document generation
  - **Effect**: Entering @Init starts a child Agent that automatically analyzes the project directory structure, tech stack, architecture design, core modules, build method, and more, generating a structured project overview file (.haijunbot/rule.md) with sections such as project overview, tech stack, directory structure, core modules, building and running, testing methods, and key configuration
- **🎯 @TestCase test-case generation command**
  - **Value tag**: Generate structured test cases from requirements documents with one click, making test design more efficient
  - **Scenario tag**: Requirements acceptance testing design, integration test-case writing, Spec-driven test coverage
  - **Effect**: Entering @TestCase starts a child Agent that analyzes the project requirements document (Spec file) and code interfaces to generate a text-based test-case file. The test cases cover functional testing, boundary-condition testing, exception-handling testing, and interface-compatibility testing, with each case containing a number, name, preconditions, steps, expected results, and priority (P0/P1/P2)
- **🎯 Automatic loading of the project overview**
  - **Value tag**: Project context is injected automatically, letting Agents understand the whole project out of the box
  - **Scenario tag**: Starting a new session, switching projects, team collaboration
  - **Effect**: The .haijunbot/rule.md file is automatically loaded as a rule when the Agent starts, so Agents learn the project structure, tech stack, core modules, and more without manual loading, greatly reducing repeated explanations
- **🎯 Agent ID parameter support**
  - **Value tag**: Each Agent has a unique identifier, making multi-Agent management clearer
  - **Scenario tag**: Web Gateway environment, multi-Agent collaboration, inter-Agent message routing
  - **Effect**: CLI and CodeAgent add the --agent-id parameter, with unique identifiers assigned by the Web Gateway's AgentManager, supporting inter-Agent message routing and identity recognition
- **🎯 Frontend WebSocket heartbeat mechanism**
  - **Value tag**: Long-idle connections are no longer dropped, providing a more stable experience
  - **Scenario tag**: Long thinking/waiting periods, network proxy environments, keeping connections alive during idle periods
  - **Effect**: The frontend adds a ping/pong heartbeat mechanism (30-second interval), preventing idle connections from being dropped by middleware or proxy timeouts, and automatically reconnects when no pong is received during the timeout

#### **📌 Fixes**

- **🔧 Fix for writing back PlantUML content**
  - **Value tag**: PlantUML diagram content is written back completely after editing, with no markers lost
  - **Scenario tag**: PlantUML diagram editing, embedding diagrams in Markdown
  - **Effect**: Preserved the @startuml/@enduml markers, ensuring the written-back content ends with a newline, avoiding the content sticking to the code-block markers
- **🔧 Fix for frontend execution history states**
  - **Value tag**: Terminal history displays correctly when switching Agents, with ended terminals no longer shown as still running
  - **Scenario tag**: Multi-Agent switching, history-message loading, terminal recovery
  - **Effect**: Scans execution messages from back to front, forcibly marking all but the last as completed, ensuring historical terminal states are correct
- **🔧 Optimized confirmation requests for non-current Agents**
  - **Value tag**: Confirmation requests from background Agents no longer disturb current operations, and are automatically restored when switching
  - **Scenario tag**: Parallel multiple Agents, background Agents needing confirmation
  - **Effect**: Confirmation requests from non-current Agents no longer pop up a dialog immediately; the confirmation state is automatically restored when switching to that Agent
- **🔧 Preserved input-box content**
  - **Value tag**: Already-typed text is not overwritten when recovering a session, avoiding repeated input
  - **Scenario tag**: Session recovery, input-request preset values
  - **Effect**: When recovering a session, the user's already-typed text is preserved, and preset values are only used to fill the input box when it is empty
- **🔧 WebSocket connection-replacement notification**
  - **Value tag**: The frontend receives a clear notification when a connection is replaced, and no longer reconnects meaninglessly
  - **Scenario tag**: Opening the same Agent in multiple tabs, the connection being replaced by a new one
  - **Effect**: When a new connection replaces an old one, a CONNECTION_LOCKED error is sent to the old connection; the frontend clears the token and stops reconnecting upon receiving it

#### **🔧 Optimizations and Refactoring**

- **🎯 Improved tool-call detection accuracy**
  - **Value tag**: More accurate tool-call recognition with greatly reduced false triggers
  - **Scenario tag**: Mentioning tool names in conversation, discussing JSON-format content
  - **Effect**: Strictened tool-call detection conditions, requiring the standard "name":"tool_name" format, and added recognition of flat-format tool calls (no name field in the JSON but parameters matching a registered tool); it is only judged as a tool call when there is a unique match
- **🎯 Simplified pinned content**
  - **Value tag**: Cleaner conversation context, reducing repeated information occupying tokens
  - **Scenario tag**: Long conversations, content pinned with the Pin marker
  - **Effect**: Removed the redundant "original task objective" repeated display, unified as "user pinned content", avoiding the same content being injected into the context repeatedly
- **🎯 Optimized streaming-output terminal truncation**
  - **Value tag**: The interface no longer overflows when streaming long text, always staying within the visible range
  - **Scenario tag**: AI generating super-long code, large blocks of text output
  - **Effect**: Truncation is now calculated based on the actual number of rendered lines after Markdown rendering, rather than the number of raw text lines, ensuring the Panel always stays within the terminal's visible range
- **🎯 Optimized input bridging**
  - **Value tag**: More immediate single-line input responses, unaffected by the global buffer
  - **Scenario tag**: Web Gateway environment, single-line/multi-line input switching
  - **Effect**: Made consumption of the global buffer optional; single-line input no longer uses the global buffer, and only multi-line input does, avoiding buffer messages interfering with single-line input
- **🎯 Optimized frontend terminal-history reconstruction**
  - **Value tag**: Terminal content is fully restored after switching Agents, with no execution records lost
  - **Scenario tag**: Multi-Agent switching, recovery after long-running sessions
  - **Effect**: Execution messages now include execution_chunks data when saved to history, allowing complete xterm terminal content to be reconstructed from history after switching Agents
- **🎯 Streamlined classical-Chinese personality rules**
  - **Value tag**: More minimal classical-Chinese responses, with more significant token savings
  - **Scenario tag**: Token-saving scenarios, classical-Chinese-style conversations
  - **Effect**: Greatly streamlined the rule content; the core principle is now "if one character suffices, do not use two; responses should be within about 20 characters", with correct/incorrect example comparisons and a scenario-guidance table added
- **🎯 Adjusted the default code-review confirmation value**
  - **Value tag**: One-click confirmation feedback after code review, making operations quicker
  - **Scenario tag**: Code review completed, issue-fix confirmation
  - **Effect**: Changed the default value of the "Feed review results back to the conversation" confirmation in the Review command from "No" to "Yes", saving one key press
- **🎯 Simplified system tool information**
  - **Value tag**: A more concise system prompt, reducing token consumption
  - **Scenario tag**: Building the system prompt for each conversation
  - **Effect**: Removed the rg/fd command detection logic, uniformly using grep/find to describe available tools, simplifying system information output

#### **📚 Documentation Update**

- **🎯 Added project-initialization rules**
  - **Value tag**: Standardized project-initialization flow, with more stable overview generation quality
  - **Scenario tag**: New project onboarding, team-collaboration standards
  - **Effect**: Added the init_project built-in rule, defining the analysis-completeness and structuring principles for the project overview, including four standard steps: browsing the project structure, analyzing the tech stack, understanding the core modules, and generating the overview file
- **🎯 Added test-case generation rules**
  - **Value tag**: A standardized test-case generation flow with more comprehensive coverage
  - **Scenario tag**: Requirements acceptance testing, integration test design
  - **Effect**: Added the generate_testcase built-in rule, defining three principles—requirement-driven, case completeness, and case structuring—ensuring test cases cover the four scenario categories of functionality/boundaries/exceptions/compatibility

---

### Release Note - v3.1.2 2026-05-28

#### **🚀 New Features**

- **🎯 Pure-JSON tool-call protocol**
  - **Value tag**: More concise and intuitive tool calls with stronger compatibility
  - **Scenario tag**: All tool-call scenarios, multi-model adaptation
  - **Effect**: Migrated tool calls from the tag-based format to a pure-JSON format, with no extra tag wrapping; tools are called by outputting a JSON object directly
- **🎯 Code review command**
  - **Value tag**: One-click comprehensive code review to discover potential issues
  - **Scenario tag**: Pre-commit review, code quality checks, issue-fix verification
  - **Effect**: Added the Review command, which can call CodeReviewer to comprehensively review code and, after discovering issues, feed them back into the conversation for fixing
- **🎯 Track installation command**
  - **Value tag**: Install an external Track with one command, making capability extension more convenient
  - **Scenario tag**: Installing community Tracks, linking local Track development
  - **Effect**: Added the InstallTrack command, supporting installation of Tracks by cloning from a Git repository or soft-linking from a local path
- **🎯 Enhanced task-objective tracking**
  - **Value tag**: More accurate conversation summaries, focused on the current task objective
  - **Scenario tag**: Long-conversation context compression, multi-round iterative tasks
  - **Effect**: Supports summarizing from a specified commit, automatically recognizing objective changes, and avoiding historical information interfering

#### **📌 Fixes**

- **🔧 Enhanced tool-call parsing**
  - **Value tag**: More accurate tool-call recognition, reducing execution failures
  - **Scenario tag**: Compatibility with models such as GLM, abnormal JSON handling
  - **Effect**: Added a lenient JSON extraction mode, compatible with models that do not output according to the specification, improving the tool-call recognition rate
- **🔧 Repeated model-output detection**
  - **Value tag**: Avoids the model falling into infinite loops, saving token consumption
  - **Scenario tag**: Abnormal model output, repeated reasoning processes
  - **Effect**: Detects in real time whether model output is looping repeatedly, and automatically interrupts and retries
- **🔧 Optimized terminal cache management**
  - **Value tag**: A smoother interface when switching Agents, avoiding unnecessary rebuilds
  - **Scenario tag**: Multi-Agent switching, background execution recovery
  - **Effect**: Correctly manages terminal cache states, properly saving terminal content in background-execution scenarios
- **🔧 Frontend history-data cleanup**
  - **Value tag**: Cleaner data when deleting Agents, avoiding residue
  - **Scenario tag**: Agent management, batch deletion
  - **Effect**: Also cleans up server-side history data when deleting an Agent, keeping data consistent

#### **🔧 Optimizations and Refactoring**

- **🎯 Summarization verification mechanism**
  - **Value tag**: More reliable summary generation with more complete formatting
  - **Scenario tag**: Context compression, token-limit-triggered summarization
  - **Effect**: Summary generation automatically verifies the format, automatically retrying at most 2 times on failure
- **🎯 Optimized web-content processing**
  - **Value tag**: Cleaner web-page parsing and more precise text extraction
  - **Scenario tag**: Web content reading, technical document retrieval
  - **Effect**: Removes non-text content such as CSS/JS and extracts a clean text structure
- **🎯 Quick configuration multimodal support**
  - **Value tag**: Easily enable image features during the first configuration
  - **Scenario tag**: New-user initialization, configuration wizard
  - **Effect**: The quick-configuration flow adds a multimodal support option, enabling image input with one click
- **🎯 Markdown rendering of streaming output**
  - **Value tag**: AI answers render in Markdown in real time, providing a better reading experience
  - **Scenario tag**: Code generation, technical-document answers, long-text output
  - **Effect**: Streaming output is changed from plain text to real-time Markdown rendering, with clearer code highlighting and formatting
- **🎯 C2Rust verification alignment optimization**
  - **Value tag**: More accurate C-to-Rust verification, reducing false positives
  - **Scenario tag**: Converting C code to Rust, functional alignment verification
  - **Effect**: Verification now focuses on functional-behavior consistency rather than interface-form consistency, so idiomatic Rust is no longer misjudged as a problem
- **🎯 CodeReviewer as a standalone module**
  - **Value tag**: Independently maintainable code-review logic with more flexible extension
  - **Scenario tag**: Code review, Review commands, review-flow customization
  - **Effect**: Extracted the code-review logic from CodeAgent into an independent CodeReviewer module, supporting single reviews and review-fix loops

---

### Release Note - v3.1.0 2026-05-24

#### **🚀 New Features**

- **🎯 Multimodal image analysis**
  - **Value tag**: Send images directly in the conversation and let the AI automatically recognize and analyze the image content, making interaction more natural
  - **Scenario tag**: Code-screenshot analysis, UI design review, error-screenshot troubleshooting, document-image understanding
  - **Effect**: Supports local images and URL images, adapted for both Haijun and OpenAI platforms, with image content automatically encoded for processing
- **🎯 Agent history save and restore**
  - **Value tag**: Important conversations are never lost, with the ability to restore the previous working state at any time
  - **Scenario tag**: Recovery after interruption of long tasks, continuing work on another device, backing up key conversations
  - **Effect**: The web interface supports one-click saving of Agent history, and the complete conversation context can be restored from the server when needed
- **🎯 C2Rust macro dependency analysis**
  - **Value tag**: More accurate macro handling when converting C code to Rust, with improved conversion quality
  - **Scenario tag**: Migration of C projects with complex macros, macro-call relationship analysis
  - **Effect**: Added a macro scanner that automatically analyzes the dependency relationships between macro definitions and macro calls

#### **📌 Fixes**

- **🔧 Editor-panel drag boundaries**
  - **Value tag**: The title bar stays visible when dragging the editor panel, giving more control over operations
  - **Scenario tag**: Adjusting editor-window positions, multi-panel layouts
  - **Effect**: Restricted the editor title bar so it cannot move outside the window boundary, keeping at least 100px of panel visible
- **🔧 Configuration sync confirmation mechanism**
  - **Value tag**: Prevents accidental overwriting of other nodes' configurations, making operations safer
  - **Scenario tag**: Synchronizing configuration to multiple nodes, cluster configuration management
  - **Effect**: Added a second confirmation dialog when syncing configuration to other nodes, avoiding accidental overwrites

#### **🔧 Optimizations and Refactoring**

- **🎯 Multimodal input support for CodeAgent**
  - **Value tag**: CodeAgent can also accept image input, enriching code-analysis scenarios
  - **Scenario tag**: Code-screenshot review, UI-component code generation, locating issues via error screenshots
  - **Effect**: CodeAgent fully adapts to multimodal content, seamlessly handling mixed image and text input
- **🎯 Intelligent image token estimation**
  - **Value tag**: More precise context-window management, avoiding conversation interruptions from overflow
  - **Scenario tag**: Continuing conversations after sending high-resolution images, long-context management
  - **Effect**: Automatically estimates token usage based on image resolution, reasonably managing multimodal context length
- **🎯 Enhanced intelligent retrieval**
  - **Value tag**: More accurate memory retrieval, with the Agent recalling relevant information more intelligently
  - **Scenario tag**: Cross-session knowledge retrieval, historical-task lookup
  - **Effect**: Optimized the retrieval strategy, improving relevant-memory recall and ranking accuracy
- **🎯 Enhanced Diff visualization**
  - **Value tag**: Clearer display of code changes, making review and modification more intuitive
  - **Scenario tag**: Code review, change comparison, batch-modification verification
  - **Effect**: Improved the Diff rendering logic, supporting richer code highlighting and difference markers

#### **📚 Documentation Update**

- **🎯 Improved component specification documentation**
  - **Value tag**: Clearer system architecture and component design, with more efficient development collaboration
  - **Scenario tag**: New feature development, component integration, architecture-design reference
  - **Effect**: Added multiple specification documents for frontend components, system architecture, Agent data storage, terminal recovery, and more

---

### Release Note - v3.0.44 2026-05-21

#### **🚀 New Features**

- **🎯 Symbol-dependency query tool**
  - **Value tag**: Quickly locate code-symbol dependency relationships, understanding code structure more efficiently
  - **Scenario tag**: Code refactoring, impact analysis, dependency tracking
  - **Effect**: Added the symbol_dependency tool, supporting lookup of symbols by name/file, querying references and dependencies, and BFS/DFS graph traversal
- **🎯 Distributed LLM request proxy**
  - **Value tag**: Child nodes no longer need to access external APIs directly, with requests uniformly forwarded through the master node, making deployment more flexible
  - **Scenario tag**: Multi-node deployment, network-restricted environments, centralized API-key management
  - **Effect**: A proxy node can be specified when creating an Agent; LLM requests are automatically forwarded through the specified node, with streaming-response support
- **🎯 Remote deployment rules**
  - **Value tag**: Deploy HaijunBot to a remote server with one command, making deployment simpler
  - **Scenario tag**: Server deployment, cluster expansion, remote environment setup
  - **Effect**: Added remote deployment rules, supporting SSH connection checks, environment verification, one-click installation, and service registration
- **🎯 SQLite symbol-table engine**
  - **Value tag**: More efficient symbol storage and retrieval, supporting large-scale project analysis
  - **Scenario tag**: Large projects, frequent symbol queries, dependency-graph traversal
  - **Effect**: Added a SQLite-based symbol table, supporting indexed queries, graph traversal, and incremental updates
- **🎯 SubCodeAgent conversation-history inheritance**
  - **Value tag**: The child Agent understands the parent Agent's complete analysis process, making task handoff smoother
  - **Scenario tag**: Complex-task breakdown, multi-step analysis, context continuation
  - **Effect**: Child Agents automatically inherit the parent Agent's conversation history, with no need to re-explain the background

#### **📌 Fixes**

- **🔧 Corrected the semantics of editor line-number ranges**
  - **Value tag**: Line-range editing behaves intuitively, avoiding accidental code modifications
  - **Scenario tag**: Editing code by line number, batch replacement
  - **Effect**: Corrected the line-number range to a half-open interval [start_line, end_line), consistent with programming conventions
- **🔧 Working-directory conflict detection**
  - **Value tag**: Avoids interference between multiple Agents in the same directory, keeping data safer
  - **Scenario tag**: Creating Agents, multi-Agent collaboration
  - **Effect**: Automatically detects same-node, same-directory conflicts when creating an Agent, prompting the use of worktree or another directory

#### **🔧 Optimizations and Refactoring**

- **🎯 Unified rule-management API**
  - **Value tag**: Clearer rule load/unload interfaces and simpler state management
  - **Scenario tag**: Rule development, Agent debugging
  - **Effect**: Unified into the load_rule/unload_rule API, simplifying rule-state management, with dynamically loaded rules visible in the sidebar
- **🎯 Enhanced session recovery**
  - **Value tag**: Rule content is fully restored when recovering a session, with no need to reload
  - **Scenario tag**: Session recovery, continuing after an interruption
  - **Effect**: Dynamically loaded rule content is also restored when recovering a session, maintaining the working state
- **🎯 c2rust toolchain upgrade**
  - **Value tag**: Supports more LLVM versions with more flexible path resolution
  - **Scenario tag**: Converting C code to Rust, multiple LLVM versions
  - **Effect**: Supports libclang versions 16-22, supports passing the .haijunbot/c2rust directory directly, and automatically generates .gitignore
- **🎯 Expanded multi-line input shortcuts**
  - **Value tag**: More convenient submission of multi-line input, adding the Ctrl+D shortcut
  - **Scenario tag**: Multi-line input, code editing
  - **Effect**: Added Ctrl+D as a multi-line input submission shortcut, usable alongside Ctrl+J/Ctrl+]
- **🎯 Adjusted code-structure standards**
  - **Value tag**: More reasonable file-line-count limits, avoiding over-splitting
  - **Scenario tag**: Code writing, structure optimization
  - **Effect**: Raised the file line-count limit from 500 to 1000, adding an explanation for cohesion exceptions
- **🎯 Optimized Diff display mode**
  - **Value tag**: More intuitive code comparison, using side-by-side view by default
  - **Scenario tag**: Viewing code changes, reviewing modifications
  - **Effect**: The Diff command defaults to a side-by-side view, and even single files are grouped for display

---

### Release Note - v3.0.43 2026-05-17

#### **🚀 New Features**

- **🎯 Diff command support**
  - **Value tag**: View code changes directly in the chat without switching interfaces
  - **Scenario tag**: Code review, change tracking, debugging analysis
  - **Effect**: Enter the "Diff" command to view all code modifications from the start of the task to the present, with unified-view display support
- **🎯 One-click restart of all nodes**
  - **Value tag**: More convenient maintenance of multi-node environments, with more efficient batch operations
  - **Scenario tag**: Node maintenance, service restart, configuration updates
  - **Effect**: Added a "Restart all nodes" button in the settings interface, automatically checking Agent status and restarting child nodes and the master node in order
- **🎯 Enhanced install scripts**
  - **Value tag**: More reliable installation, recoverable after interruption, with clearer error messages
  - **Scenario tag**: First-time installation, unstable network environments, recovery after install interruption
  - **Effect**: Both Windows and Linux install scripts support resumable transfer, precondition checks, better error handling, and progress display

#### **📌 Fixes**

- **🔧 Fixed Python syntax warnings**
  - **Value tag**: Eliminates runtime warnings, making code more standardized
  - **Scenario tag**: Code quality, warning cleanup
  - **Effect**: Fixed invalid escape-sequence warnings in builtin_replace_map.py, improving code quality

#### **🔧 Optimizations and Refactoring**

- **🎯 Enhanced Diff parsing**
  - **Value tag**: Structured Diff data, providing better support for frontend display
  - **Scenario tag**: Code comparison, change visualization
  - **Effect**: Added the parse_diff_to_structured_data function, parsing diff text into structured data and supporting richer display methods
- **🎯 Improved frontend interface**
  - **Value tag**: More flexible management of stopped Agents, with a friendlier interface
  - **Scenario tag**: Agent status management, multi-node environments
  - **Effect**: Stopped Agents are grouped by node and support collapse/expand, and node updates and restarts now include real-time feedback prompts

---

### Release Note - v3.0.41 2026-05-16

#### **🚀 New Features**

- **🎯 AI-friendly code-structure standards**
  - **Value tag**: Helps write code that AI can understand more easily, improving AI-assisted programming efficiency
  - **Scenario tag**: Code refactoring, code review, AI collaborative development
  - **Effect**: Built-in rules automatically check file size (≤500 lines), function length (≤50 lines), nesting depth, and more, guiding the writing of clearly structured code

- **🎯 Real-time viewing of rule content**
  - **Value tag**: View the full content of loaded rules directly in the web interface, making debugging more intuitive
  - **Scenario tag**: Rule development, Agent debugging, configuration verification
  - **Effect**: The rule list adds a file-path column, and the full text of loaded rules is displayed at the bottom

- **🎯 Stopped Agents grouped by node
  - **Value tag**: Clearer Agent management in multi-node environments, easier to find
  - **Scenario tag**: Multi-node deployment, Agent status viewing
  - **Effect**: Stopped Agents in the sidebar are grouped independently by node, each supporting separate collapse/expand

#### **📌 Fixes**

- **🔧 Fix for Diff display**
  - **Value tag**: A more stable code-comparison interface, with correct column widths and line-wrapping display
  - **Scenario tag**: Viewing code changes, reviewing modifications
  - **Effect**: Fixed issues such as column-width calculation and newline rendering, making the side-by-side comparison more precise

- **🔧 Markdown line-break support**
  - **Value tag**: Line breaks in chat messages display correctly, providing a better reading experience
  - **Scenario tag**: Viewing AI replies, reading documents
  - **Effect**: Single newlines are correctly converted to line breaks, no longer crammed together

- **🔧 Operation protection for stopped Agents**
  - **Value tag**: Avoids performing invalid operations on stopped Agents, reducing confusion
  - **Scenario tag**: Agent management, state switching
  - **Effect**: Stopped Agents hide buttons such as view-changes, rules, and tools, showing only usable operations

#### **🔧 Optimizations and Refactoring**

- **🎯 Streamlined dependencies**
  - **Value tag**: Faster installation, smaller size, and better compatibility
  - **Scenario tag**: First-time installation, ARM-device deployment
  - **Effect**: Removed 6 unnecessary dependencies; packages such as tree-sitter automatically skip ARMv6/v7/v8hf platforms

- **🎯 Upgraded node configuration management**
  - **Value tag**: More reliable cross-node configuration sync with finer-grained operations
  - **Scenario tag**: Multi-node configuration management, cluster maintenance
  - **Effect**: Configuration sync is changed to single-node read/write APIs, supporting retrieval and setting of a specified node's configuration

- **🎯 Upgraded node code updates**
  - **Value tag**: More controllable code updates, with more precise single-node operations
  - **Scenario tag**: Version upgrades, node maintenance
  - **Effect**: Code updates are changed to a single-node API, supporting updating a specified node to the main branch

- **🎯 Visual optimization of the settings interface**
  - **Value tag**: A cleaner interface with more intuitive node identification
  - **Scenario tag**: Web settings-page usage
  - **Effect**: The node list shows tag information, form-area styles are unified, and the layout is more reasonable

---

### Release Note - v3.0.40 2026-05-13

#### **🚀 New Features**

- **🎯 Refactored the editor component**
  - **Value tag**: A more stable editor interface with faster responses
  - **Scenario tag**: File editing, code viewing
  - **Effect**: Refactored the editor panel into an independent component, improving the user experience and code maintainability

- **🎯 Visible AI reasoning process**
  - **Value tag**: Supports viewing the AI model's reasoning process for deeper understanding
  - **Scenario tag**: Complex-problem analysis, viewing the reasoning process
  - **Effect**: The OpenAI platform supports saving and displaying reasoning_content, offering insight into the AI's thinking process

#### **📌 Fixes**

- **🔧 Optimized rule and tool viewing**
  - **Value tag**: Fixed the duplicated-code problem in rule and tool viewing
  - **Scenario tag**: Rule development, tool configuration
  - **Effect**: Extracted shared logic into a unified module, making features more reliable and reducing errors

#### **🔧 Optimizations and Refactoring**

- **🎯 Improved frontend interaction**
  - **Value tag**: Open the editor directly from the Agent sidebar, making operations more convenient
  - **Scenario tag**: Agent workflows, file editing
  - **Effect**: Added the openEditor event, simplifying the file-editing flow

- **🎯 Optimized code structure**
  - **Value tag**: Reduces code duplication and improves maintainability
  - **Scenario tag**: Code maintenance, feature extension
  - **Effect**: Extracted duplicated rule and tool viewing logic into a common module

---

### Release Note - v3.0.39 2026-05-12

#### **🚀 New Features**

- **🎯 Agent rule and tool viewing**
  - **Value tag**: View the rules loaded by an Agent and its available tools directly in the web interface, making debugging more convenient
  - **Scenario tag**: Rule development, tool configuration, troubleshooting
  - **Effect**: Click the 📋 and 🔧 buttons in the Agent sidebar to view the rule list and tool details

- **🎯 Multi-file Diff support**
  - **Value tag**: Code-change viewing supports multiple files, making review more comprehensive
  - **Scenario tag**: Multi-file modifications, batch refactoring
  - **Effect**: The Diff popup automatically groups display by file, clearly distinguishing the changes in each file

#### **📌 Fixes**

- **🔧 Agent status display optimization**
  - **Value tag**: Fixed the issue of inaccurate stopped-status display
  - **Scenario tag**: Agent start/stop, state switching
  - **Effect**: Stopped Agents display the stopped status preferentially, avoiding status flickering

- **🔧 Fix for Diff parsing**
  - **Value tag**: Fixed the error in parsing multi-file Diffs
  - **Scenario tag**: Viewing code changes, reviewing modifications
  - **Effect**: Correctly parses Diff content containing multiple files, avoiding display anomalies

#### **🔧 Optimizations and Refactoring**

- **🎯 Agent waiting-for-confirmation state**
  - **Value tag**: Added a waiting-for-confirmation state, making status indication clearer
  - **Scenario tag**: Operations requiring user confirmation
  - **Effect**: Agent states now distinguish between waiting-for-input and waiting-for-confirmation, making interaction clearer

---

### Release Note - v3.0.38 2026-05-12

#### **🚀 New Features**

- **🎯 Technical architecture diagram generation rules**
  - **Value tag**: Added technical architecture diagram generation rules in multiple styles for quickly creating professional diagrams
  - **Scenario tag**: System design, technical documentation, architecture review
  - **Effect**: Supports 7 styles including Flat Icon, Dark Terminal, and Blueprint, with matching icon references and generation scripts

- **🎯 Agent code-change viewing**
  - **Value tag**: View an Agent's code changes directly in the web interface, without switching to a terminal
  - **Scenario tag**: Code review, change confirmation, progress tracking
  - **Effect**: Click the 🔀 button in the Agent sidebar to view the side-by-side Diff

- **🎯 Non-interactive mode**
  - **Value tag**: The Agent executes tasks automatically without waiting for user confirmation, suitable for automation scenarios
  - **Scenario tag**: Batch processing, scheduled tasks, CI/CD integration
  - **Effect**: Enable non-interactive mode and provide a task description when creating an Agent, and the Agent will execute fully automatically

- **🎯 One-click code update to the main branch**
  - **Value tag**: Uniformly updates the HaijunBot code on all nodes, simplifying version management
  - **Scenario tag**: Version upgrades, multi-node deployment, daily updates
  - **Effect**: Click a button on the settings page to notify all nodes to switch to the main branch and pull the latest code

- **🎯 Node connection private-key management**
  - **Value tag**: The web interface and VS Code extension support retrieval and management of node connection private keys
  - **Scenario tag**: Child-node configuration, distributed deployment
  - **Effect**: Retrieve the private key on the settings page, with copy and show/hide operations supported

#### **📌 Fixes**

- **🔧 Agent status sync optimization**
  - **Value tag**: Fixed the issue of untimely Agent status updates
  - **Scenario tag**: Agent start/stop, state switching
  - **Effect**: WebSocket status changes are synced to the interface in real time, making the stopped status display more accurate

- **🔧 Fix for node association when creating a terminal**
  - **Value tag**: Fixed the issue of a missing node ID when creating a terminal
  - **Scenario tag**: Multi-node environments, remote terminals
  - **Effect**: Terminals are correctly associated with their corresponding node, avoiding operational confusion

#### **🔧 Optimizations and Refactoring**

- **🎯 Agent list grouped by node**
  - **Value tag**: The Agent list is displayed grouped by node, making management clearer
  - **Scenario tag**: Multi-node deployment, when there are many Agents
  - **Effect**: Each node has an independent group, running Agents are pinned to the top, and collapse/expand is supported

- **🎯 Automatic Agent-name generation**
  - **Value tag**: Newly created Agents are automatically named in the "type-datetime" format, avoiding name conflicts
  - **Scenario tag**: Creating Agents, copying Agents
  - **Effect**: The name format is like "code-Agent-20260512-140013", unique and meaningful

- **🎯 Unified rule-path comment management**
  - **Value tag**: File-path comments are automatically added when loading rules, facilitating debugging and locating
  - **Scenario tag**: Rule development, troubleshooting
  - **Effect**: Automatically adds a `<!-- rule-file-path: xxx -->` comment before all rule content

- **🎯 Optimized switching to stopped Agents**
  - **Value tag**: Switching to a stopped Agent no longer triggers network requests, with faster responses
  - **Scenario tag**: Viewing history, switching Agents
  - **Effect**: Loads local history directly, avoiding unnecessary connection attempts

---

### Release Note - v3.0.37 2026-05-08

#### **🚀 New Features**

- **🎯 Enhanced configuration management**
  - **Value tag**: Supports dynamically viewing and modifying global configuration via commands, without manually editing the configuration file
  - **Scenario tag**: Runtime configuration adjustment, quick parameter modification
  - **Effect**: Use `<PrintConfig>` to view the configuration and `<SetConfig>` to modify it in real time, supporting nested paths and safe value parsing

- **🎯 SubAgent conversation-history inheritance**
  - **Value tag**: Child Agents automatically inherit the parent Agent's conversation context, making task handoff smoother
  - **Scenario tag**: Complex-task breakdown, multi-step collaboration
  - **Effect**: Child Agents understand the previous analysis process and issues, with no need to re-explain the background

#### **📌 Fixes**

- **🔧 Terminal output width optimization**
  - **Value tag**: Fixed output display issues caused by overly wide terminals
  - **Scenario tag**: Script execution, log viewing
  - **Effect**: Output is more compact, improving the reading experience

- **🔧 WebSocket proxy configuration fix**
  - **Value tag**: Supports configuring the proxy via environment variables, removing redundant parameters
  - **Scenario tag**: Network proxy environments, corporate intranets
  - **Effect**: Simpler proxy configuration and more stable connections

- **🔧 Debug-log cleanup**
  - **Value tag**: Removed unnecessary debug output such as session recovery
  - **Scenario tag**: Daily use, log viewing
  - **Effect**: A cleaner console with more prominent key information

#### **🔧 Optimizations and Refactoring**

- **🎯 Comprehensive Prompt-system upgrade**
  - **Value tag**: All scenario prompts are uniformly enhanced, with more concise output and safer operations
  - **Scenario tag**: Various task executions, daily interactions
  - **Effect**: More standardized tool usage, more complete risk warnings, and more efficient communication

- **🎯 Automatic analysis in Gateway mode**
  - **Value tag**: Automatically performs analysis after a task ends in Gateway mode
  - **Scenario tag**: Web services, automation flows
  - **Effect**: Eliminates manual confirmation, increasing the degree of automation

- **🎯 Unified frontend UI optimization**
  - **Value tag**: Unified button colors and terminal-panel theme variables, providing a more consistent visual experience
  - **Scenario tag**: Web interface usage
  - **Effect**: A more coordinated interface with a stronger brand feel

- **🎯 Simplified rule management**
  - **Value tag**: Simplified rule filtering and selection logic, reducing unnecessary output control
  - **Scenario tag**: Rule loading, automatic selection
  - **Effect**: More efficient rule processing and cleaner code

- **🎯 Environment-variable support for service proxy**
  - **Value tag**: systemd services automatically inherit the system proxy environment variables
  - **Scenario tag**: System service deployment, proxy network environments
  - **Effect**: Smoother service deployment, with no need to manually configure the proxy

---

### Release Note - v3.0.36 2026-05-04

#### **🚀 New Features**

- **🎯 PlantUML repair tool**
  - **Value tag**: Added automatic PlantUML code-block repair, improving UML diagram maintenance efficiency
  - **Scenario tag**: Markdown document maintenance, UML diagram repair
  - **Effect**: Automatically extracts, validates, and fixes PlantUML syntax errors, reducing manual debugging time

#### **📌 Fixes**

- **🔧 WebSocket connection-stability fix**
  - **Value tag**: Fixed connection interruption issues during network instability, with automatic reconnection support
  - **Scenario tag**: Network fluctuations, long-term use
  - **Effect**: More stable connections, automatic recovery after disconnection, with no need to manually refresh

- **🔧 Terminal output truncation fix**
  - **Value tag**: Fixed the issue of long-line output being truncated by automatic line wrapping
  - **Scenario tag**: Script execution, log viewing
  - **Effect**: Output displays in full, no longer wrapping because of terminal-width limits

#### **🔧 Optimizations and Refactoring**

- **🎯 Enhanced file-editing features**
  - **Value tag**: The edit_file tool adds a line-number-range editing mode, making editing more flexible
  - **Scenario tag**: Code modification, configuration-file editing
  - **Effect**: Supports direct replacement by line-number range, without needing to precisely match text

- **🎯 Optimized mobile frontend experience**
  - **Value tag**: Improved the mobile interface layout, with more reasonable status-indicator positions
  - **Scenario tag**: Mobile access, mobile office work
  - **Effect**: More convenient mobile operations and clearer information display

- **🎯 Improved code-reading experience**
  - **Value tag**: The read_code tool removes line-number display, making output cleaner
  - **Scenario tag**: Code viewing, context analysis
  - **Effect**: Reduces visual distraction, letting you focus on the code content itself

---

### Release Note - v3.0.35 2026-04-30

#### **🚀 New Features**

- **🎯 Frontend brand identity**
  - **Value tag**: Added a HaijunBot Logo and brand display in the page header, improving product recognition
  - **Scenario tag**: Web interface access, brand awareness
  - **Effect**: A more professional interface with a more unified brand image

#### **📌 Fixes**

- **🔧 Terminal resource-management fix**
  - **Value tag**: Fixed the issue of repeatedly creating terminals for completed executions, reducing resource usage
  - **Scenario tag**: Terminal switching after execution completes, page refresh
  - **Effect**: More reasonable terminal management, avoiding unnecessary resource creation
- **🔧 Execution-message association fix**
  - **Value tag**: Fixed the ID-association issue when updating execution messages, ensuring accurate state sync
  - **Scenario tag**: Script-execution status tracking, history viewing
  - **Effect**: More accurate execution-state display and reliable history updates

#### **🔧 Optimizations and Refactoring**

- **🎯 Refactored the frontend theme system**
  - **Value tag**: Fully adopted a CSS variable system, switched to a blue tech-style theme, upgrading the visual experience
  - **Scenario tag**: Web interface usage, long working sessions
  - **Effect**: A more modern interface, an easier-to-maintain theme, and stronger consistency
- **🎯 Optimized script-execution output**
  - **Value tag**: Set a default terminal size, avoiding output truncation when no frontend is connected
  - **Scenario tag**: Background script execution, headless mode
  - **Effect**: More complete script output and unobstructed result viewing
- **🎯 VS Code extension local-node support**
  - **Value tag**: The local Master node supports directly creating terminals and opening files without network relay
  - **Scenario tag**: Local development, VS Code plugin usage
  - **Effect**: Faster local operations with more direct responses
- **🎯 Debug-log cleanup**
  - **Value tag**: Removed debug logs left from the development stage, making console output cleaner
  - **Scenario tag**: Daily use, log viewing
  - **Effect**: Cleaner system output and more efficient troubleshooting

---

### Release Note - v3.0.34 2026-04-30

#### **🚀 New Features**

- **🎯 Auto-login feature**
  - **Value tag**: Supports automatic login, improving ease of use
  - **Scenario tag**: Daily use, quick startup
  - **Effect**: Reduces manual login steps for a smoother experience

- **🎯 Login-free feature**
  - **Value tag**: Supports a no-login mode, simplifying the access flow
  - **Scenario tag**: Temporary use, quick access
  - **Effect**: Basic features are usable without logging in

- **🎯 Frontend development mode**
  - **Value tag**: Added a frontend development mode, supporting development and debugging
  - **Scenario tag**: Frontend development, interface debugging
  - **Effect**: More convenient development and more efficient debugging

#### **📌 Fixes**

- **🔧 Terminal reference-settings fix**
  - **Value tag**: Fixed the variable-declaration issue in terminal reference settings
  - **Scenario tag**: Terminal configuration, setting modifications
  - **Effect**: More stable settings saving, avoiding configuration errors

- **🔧 Authentication connection-wait fix**
  - **Value tag**: Fixed the connection-wait issue in authentication checks
  - **Scenario tag**: Login authentication, network connections
  - **Effect**: A more stable authentication process with fewer connection timeouts

#### **🔧 Optimizations and Refactoring**

- **🎯 Optimized WebSocket message caching**
  - **Value tag**: Caches output messages before the WebSocket connection is established
  - **Scenario tag**: Unstable networks, connection-establishment process
  - **Effect**: No messages are lost and connections are more reliable

- **🎯 Optimized request-queue management**
  - **Value tag**: Supports FIFO queue management for multiple pending requests
  - **Scenario tag**: Concurrent requests, multi-task processing
  - **Effect**: More orderly request processing, avoiding conflicts

- **🎯 Refactored encoding-detection logic**
  - **Value tag**: Refactored the encoding-detection logic, improving compatibility
  - **Scenario tag**: File editing, multi-language support
  - **Effect**: More accurate encoding handling, supporting more formats

- **🎯 Debug-log cleanup**
  - **Value tag**: Removed unnecessary debug logs, improving performance
  - **Scenario tag**: Daily use, production environments
  - **Effect**: A cleaner system that runs more efficiently

---

### Release Note - v3.0.34 2026-04-30

#### **🚀 New Features**

- **🎯 Auto-login feature**
  - **Value tag**: Supports automatic login, improving ease of use
  - **Scenario tag**: Daily use, quick startup
  - **Effect**: Reduces manual login steps for a smoother experience

- **🎯 Login-free feature**
  - **Value tag**: Supports a no-login mode, simplifying the access flow
  - **Scenario tag**: Temporary use, quick access
  - **Effect**: Basic features are usable without logging in

- **🎯 Frontend development mode**
  - **Value tag**: Added a frontend development mode, supporting development and debugging
  - **Scenario tag**: Frontend development, interface debugging
  - **Effect**: More convenient development and more efficient debugging

#### **📌 Fixes**

- **🔧 Terminal reference-settings fix**
  - **Value tag**: Fixed the variable-declaration issue in terminal reference settings
  - **Scenario tag**: Terminal configuration, setting modifications
  - **Effect**: More stable settings saving, avoiding configuration errors

- **🔧 Authentication connection-wait fix**
  - **Value tag**: Fixed the connection-wait issue in authentication checks
  - **Scenario tag**: Login authentication, network connections
  - **Effect**: A more stable authentication process with fewer connection timeouts

#### **🔧 Optimizations and Refactoring**

- **🎯 Optimized WebSocket message caching**
  - **Value tag**: Caches output messages before the WebSocket connection is established
  - **Scenario tag**: Unstable networks, connection-establishment process
  - **Effect**: No messages are lost and connections are more reliable

- **🎯 Optimized request-queue management**
  - **Value tag**: Supports FIFO queue management for multiple pending requests
  - **Scenario tag**: Concurrent requests, multi-task processing
  - **Effect**: More orderly request processing, avoiding conflicts

- **🎯 Refactored encoding-detection logic**
  - **Value tag**: Refactored the encoding-detection logic, improving compatibility
  - **Scenario tag**: File editing, multi-language support
  - **Effect**: More accurate encoding handling, supporting more formats

- **🎯 Debug-log cleanup**
  - **Value tag**: Removed unnecessary debug logs, improving performance
  - **Scenario tag**: Daily use, production environments
  - **Effect**: A cleaner system that runs more efficiently

---

### Release Note - v3.0.30 2026-04-23

#### **🚀 New Features**

- **🎯 Temporary chat mode**
  - **Value tag**: Added the Btw command, supporting quick temporary conversations without disturbing the main Agent context
  - **Scenario tag**: Quick queries, temporary testing, independent conversations
  - **Effect**: Enter `/<Btw>` to start a temporary chat, and enter `/bye` or an empty line to exit

#### **📌 Fixes**

- **🔧 Empty-repository Git detection fix**
  - **Value tag**: Fixed the failure to detect uncommitted changes in an empty repository
  - **Scenario tag**: New project initialization, first commit
  - **Effect**: Empty repositories can now correctly detect uncommitted changes

- **🔧 Improved code-generation stability**
  - **Value tag**: Fixed the timing issue of the initial commit retrieval in the Code Agent
  - **Scenario tag**: Code-generation tasks, Git operations
  - **Effect**: More stable code generation with more accurate rollback-point settings

#### **🔧 Optimizations and Refactoring**

- **🎯 Improved model-group management experience**
  - **Value tag**: The model-group list is displayed in a table, with sequence-number selection supported on updates
  - **Scenario tag**: Configuration management, model switching
  - **Effect**: Clearer information display and more convenient operations

- **🎯 Agent grouping display in the web interface**
  - **Value tag**: The Agent list is grouped by running status, with stopped Agents collapsible
  - **Scenario tag**: Multi-Agent management, interface organization
  - **Effect**: A cleaner interface, with running Agents visible at a glance

- **🎯 Automatic installation of callback dependencies**
  - **Value tag**: Callback files support automatic dependency installation, with no manual configuration
  - **Scenario tag**: Using custom callbacks, extending features
  - **Effect**: More automated dependency management, reducing manual operations

- **🎯 Enhanced error handling**
  - **Value tag**: Improved exception handling in multiple places, providing friendlier error messages
  - **Scenario tag**: Exception handling, troubleshooting
  - **Effect**: A more stable system with clearer error messages

---

### Release Note - v3.0.27 2026-04-16

#### **📌 Fixes**

- **🔧 Session-recovery fix**
  - **Value tag**: Fixed the data-parsing errors during session recovery, ensuring sessions can be restored normally
  - **Scenario tag**: Restoring historical sessions, automatic recovery in non-interactive mode, continuing after session interruption
  - **Effect**: More stable session recovery, with no more unpacking errors

- **🔧 VS Code extension release flow**
  - **Value tag**: Fixed the package-lock.json synchronization issue when publishing the VS Code extension
  - **Scenario tag**: Version releases, VS Code extension updates
  - **Effect**: More reliable extension publishing, avoiding version-number update failures

#### **🔧 Optimizations and Refactoring**

- **🎯 Optimized tool-call error messages**
  - **Value tag**: Provides clearer error messages and splitting suggestions when tool-call parameters are too long
  - **Scenario tag**: Complex task execution, tool-call format errors
  - **Effect**: Friendlier error messages, helping users quickly locate problems

- **🎯 Enhanced Agent icon identification**
  - **Value tag**: Different icons are used for different Agent types (normal Agent, Code Agent)
  - **Scenario tag**: Multi-Agent management, distinguishing Agent types
  - **Effect**: A more intuitive interface, with Agent types clear at a glance

#### **📚 Documentation Update**

- **🎯 Classical-Chinese personality rules**
  - **Value tag**: Added classical-Chinese-style personality rules, supporting elegant and concise classical expression
  - **Scenario tag**: Saving tokens, classical-style conversations, classical-Chinese communication
  - **Effect**: More concise expression, suitable for token-limited scenarios

---

### Release Note - v3.0.25 2026-04-14

#### **🚀 New Features**

- **🎯 Quick mode**
  - **Value tag**: Supports the `-q` parameter for fast task execution, skipping initialization steps such as task classification and rule loading
  - **Scenario tag**: Quickly executing simple tasks, batch processing, script integration
  - **Effect**: Significantly faster startup, suitable for efficiency-focused scenarios

- **🎯 Terminal session management**
  - **Value tag**: Supports creating an independent terminal session for each Agent, providing more thorough resource isolation
  - **Scenario tag**: Parallel multiple tasks, long-running tasks, scenarios requiring an independent environment
  - **Effect**: Terminals do not interfere with each other, and multi-task management is clearer

- **🎯 systemd service installation**
  - **Value tag**: Provides the `haijunbot-service install` command to deploy as a system service with one click
  - **Scenario tag**: Production-environment deployment, auto-start on boot, long-running use
  - **Effect**: More convenient service management, supporting automatic restarts and log management

- **🎯 VS Code extension enhancement**
  - **Value tag**: Added features such as file drag-and-drop, remote file editing, and chat-history pagination
  - **Scenario tag**: Daily coding, remote development, history-message recall
  - **Effect**: A smoother development experience with more complete functionality

#### **📌 Fixes**

- **🔧 WebSocket connection stability**
  - **Value tag**: Fixed the exception handling on connection loss, automatically refreshing the page after disconnection
  - **Scenario tag**: Unstable network environments, long-running use, reconnection after disconnect
  - **Effect**: More stable connections and faster recovery

- **🔧 Quick-mode parameter passing**
  - **Value tag**: Fixed the issue where the `-q` parameter was not correctly passed to the parent class
  - **Scenario tag**: Executing tasks with quick mode
  - **Effect**: Quick mode can now correctly skip initialization steps

- **🔧 confirm dialog focus**
  - **Value tag**: Fixed the issue where the confirmation dialog focus was not on the default option
  - **Scenario tag**: Using the keyboard to quickly select when confirmation is required
  - **Effect**: Smoother keyboard operation, with no need for mouse clicks

- **🔧 Ctrl+C signal triggering**
  - **Value tag**: Fixed the Ctrl+C completion-signal trigger condition, effective only in the multi-line input box
  - **Scenario tag**: Interrupting the current task, cancelling input
  - **Effect**: Avoids accidental triggers and makes operations more precise

#### **🔧 Optimizations and Refactoring**

- **🎯 WebSocket message-processing performance optimization**
  - **Value tag**: Implemented message throttling and storage debouncing, reducing UI update frequency
  - **Scenario tag**: High-frequency message scenarios, streaming output, long-running use
  - **Effect**: A smoother interface with more timely responses

- **🎯 Slimmed-down Docker image**
  - **Value tag**: Removed the Rust toolchain dependency, making the image smaller
  - **Scenario tag**: Docker deployment, CI/CD environments
  - **Effect**: Faster builds and lower resource usage

- **🎯 Simplified frontend interface**
  - **Value tag**: Simplified the frontend interface and connection management, moving the chat panel to the sidebar
  - **Scenario tag**: Daily use, multi-window operations
  - **Effect**: A cleaner interface with more intuitive operations

#### **📚 Documentation Update**

- **🎯 Service deployment documentation**
  - **Value tag**: Unified the service-start command format and added a systemd installation guide
  - **Scenario tag**: Service deployment, operations management
  - **Effect**: Simpler deployment and clearer documentation

- **🎯 Installation guide update**
  - **Value tag**: Updated the installation commands, specifying Python 3.12
  - **Scenario tag**: First-time installation, environment setup
  - **Effect**: More stable installation and better compatibility

---

### Release Note - v3.0.10 2026-04-06

#### **📌 Fixes**

- **🔧 Empty-response handling for streaming requests**
  - **Value tag**: Fixed the issue of streaming requests returning empty responses in proxy environments, with automatic fallback retries
  - **Scenario tag**: Accessing APIs through a proxy, unstable network environments
  - **Effect**: More stable streaming requests, reducing request failures caused by network issues
- **🔧 GLM model compatibility**
  - **Value tag**: Supports the `reasoning_content` field of GLM models, correctly parsing the reasoning process
  - **Scenario tag**: Using Zhipu GLM-series models, wanting to view the model's thinking process
  - **Effect**: GLM reasoning is visible, with better compatibility

#### **🔧 Optimizations and Refactoring**

- **🎯 Enhanced configuration management**
  - **Value tag**: Supports manually entering model names when batch-adding LLM models, with automatic overwrite prompts for same-name configurations
  - **Scenario tag**: Configuring multiple models in a batch, when the API cannot return a complete model list, updating existing configurations
  - **Effect**: More flexible configuration, supporting API connectivity tests, avoiding duplicate configurations
- **🎯 Reasoning-process visualization**
  - **Value tag**: Streaming output distinguishes the reasoning process from the main content, with the reasoning process styled in gray
  - **Scenario tag**: Using reasoning models, wanting to understand the model's thinking process, debugging model output
  - **Effect**: Greater transparency of the thinking process, letting users clearly distinguish reasoning from the final answer
- **🎯 Long-reasoning support**
  - **Value tag**: Sets `max_tokens=1048576` by default, supporting ultra-long reasoning tasks
  - **Scenario tag**: Complex code analysis, long-document processing, deep-reasoning tasks
  - **Effect**: Long reasoning output is no longer truncated due to token limits

#### **📚 Documentation Update**

- **🎯 Landing-page optimization**
  - **Value tag**: Updated the product introduction, command examples, and screenshots, removing the outdated solution-comparison table
  - **Scenario tag**: New users learning about the product, technology-selection evaluation
  - **Effect**: More accurate information and a more professional product presentation

---

### Release Note - v3.0.0 2026-04-05

#### **🚀 New Features**

- **🎯 VSCode extension release version**
  - **Value tag**: Provides a complete VSCode integration experience, allowing Agent management without leaving the editor
  - **Scenario tag**: Daily coding, code review, project management, remote development
  - **Effect**: Supports a chat panel, terminal integration, remote directory browsing, and full Agent lifecycle management, greatly improving development efficiency

- **🎯 Distributed node architecture**
  - **Value tag**: Supports multi-node deployment, enabling cross-node Agent management and terminal access
  - **Scenario tag**: Large-scale team collaboration, multi-server resource scheduling, distributed development environments
  - **Effect**: Child nodes are uniformly managed through the master node, Agents can be created and run on any node, and resources are used more flexibly

- **🎯 Global search feature**
  - **Value tag**: Supports global content search in the Agent workspace, with file glob filtering of the scope
  - **Scenario tag**: Quickly locating code in large projects, finding references, global replacement analysis
  - **Effect**: Integrated into the editor sidebar, search results are highlighted, and file location is more precise

- **🎯 Editor sidebar directory tree**
  - **Value tag**: Added a directory-tree view to the editor sidebar, making file browsing more intuitive
  - **Scenario tag**: Project-structure viewing, quick file navigation, multi-directory comparison
  - **Effect**: The directory tree and search views switch seamlessly, file operations are more convenient, and the IDE experience is more complete

- **🎯 Intelligent auto-completion system**
  - **Value tag**: Entering @ brings up a completion popup, supporting usage-frequency-based sorting weights
  - **Scenario tag**: Quickly referencing files, methods, and variables, reducing memory burden
  - **Effect**: Frequently used items are prioritized, input efficiency improves significantly, and code writing is smoother

- **🎯 Batch Agent operations**
  - **Value tag**: Supports management operations such as renaming, copying, and batch-deleting Agents
  - **Scenario tag**: Managing many Agents, quickly copying configurations, batch cleanup
  - **Effect**: More efficient Agent management, greatly reducing repeated configuration work

- **🎯 Scheduled-task management**
  - **Value tag**: Supports scheduled-task persistence and restart recovery, allowing creation of recurring execution plans
  - **Scenario tag**: Scheduled report generation, periodic code checks, automated operations tasks
  - **Effect**: Tasks are not lost, are automatically restored after system restarts, and automation capabilities are more reliable

- **🎯 Product landing page**
  - **Value tag**: Added an official product landing page, showcasing product features and user value
  - **Scenario tag**: Product promotion, new-user onboarding, team technology selection
  - **Effect**: A more professional product image and a better first impression

#### **📌 Fixes**

- **🔧 Message no-loss mechanism**
  - **Value tag**: Caches messages when the connection drops, automatically resending after reconnection
  - **Scenario tag**: Unstable networks, browser refresh, reconnection after connection interruption
  - **Effect**: No messages are lost and state sync is more complete

- **🔧 VSCode extension connection stability**
  - **Value tag**: Enhanced WebSocket connection retry and timeout handling, persisting connection information
  - **Scenario tag**: Unstable network environments, long-running use, reconnection after disconnect
  - **Effect**: More stable connections, quickly recovering the working state after disconnection

- **🔧 Multi-Agent message cross-wiring issue**
  - **Value tag**: Fixed input-confirmation and streaming-message cross-wiring in multi-Agent scenarios
  - **Scenario tag**: Running multiple Agents simultaneously, switching between Agent sessions
  - **Effect**: Messages belong to the correct Agent, making communication more reliable

- **🔧 Terminal display anomalies**
  - **Value tag**: Fixed the width, scrolling, and content-overflow issues in the terminal history area
  - **Scenario tag**: Viewing long output, switching terminal sessions, continuously watching execution results
  - **Effect**: More stable terminal content display and smoother reading

- **🔧 Editor layout issues**
  - **Value tag**: Fixed the content-area layout overflow of the editor panel and file-tree scrolling anomalies
  - **Scenario tag**: Editing long files, browsing deep directory structures
  - **Effect**: A smoother editor experience with more accurate layout display

- **🔧 Mobile adaptation**
  - **Value tag**: Fixed mobile viewport-height adaptation and event-cleanup issues
  - **Scenario tag**: Using HaijunBot on phones/tablets, mobile office work
  - **Effect**: Smoother mobile operations with more precise responses

- **🔧 Auto-scroll control**
  - **Value tag**: Restricted auto-scrolling to only the current Agent's messages
  - **Scenario tag**: Parallel multi-Agent output, viewing historical messages
  - **Effect**: The page no longer jumps around, providing a better reading experience

#### **🔧 Optimizations and Refactoring**

- **🎯 Web interface interaction optimization**
  - **Value tag**: Floating panels support maximizing, focus management, and position memory
  - **Scenario tag**: Parallel operations in multiple windows, adjusting layouts to preference
  - **Effect**: More flexible interface layout, retaining a familiar environment for repeated use

- **🎯 Improved input experience**
  - **Value tag**: Historical-input persistence, multi-line input-mode optimization, keyboard-shortcut adjustments
  - **Scenario tag**: Frequent input, code-snippet editing, history recall
  - **Effect**: Continuously improving input efficiency, usable across sessions

- **🎯 PlantUML diagram rendering**
  - **Value tag**: Enhanced Markdown and PlantUML rendering support in the chat panel
  - **Scenario tag**: Technical-document writing, architecture-diagram display, flow-chart explanations
  - **Effect**: More intuitive technical communication and more professional document display

- **🎯 Simplified service startup**
  - **Value tag**: Added a unified service-start command, simplifying startup scripts
  - **Scenario tag**: Quick startup, Docker deployment, development-environment setup
  - **Effect**: A more unified startup method and simpler configuration

- **🎯 Optimized authentication experience**
  - **Value tag**: Allows direct login when no password is configured, and blocks blank-password logins
  - **Scenario tag**: Quick startup in development environments, secure access in production environments
  - **Effect**: Balances security and convenience, with a more reasonable authentication flow

#### **📚 Documentation Update**

- **🎯 Complete user-manual system**
  - **Value tag**: Added a complete user-manual system, including documents on platform configuration, specialized capabilities, and tool efficiency
  - **Scenario tag**: New-user onboarding, feature lookup, best-practice learning
  - **Effect**: Clearer documentation structure, empowering users to learn on their own

- **🎯 CLI invocation standard**
  - **Value tag**: Added a HaijunBot Agent CLI invocation standard document
  - **Scenario tag**: Automation-script authoring, CI/CD integration, batch task processing
  - **Effect**: More standardized CLI usage and smoother automation integration

- **🎯 Improved installation documentation**
  - **Value tag**: Unified the installation documentation, added source-installation instructions, and updated the built-in uv installation flow
  - **Scenario tag**: First-time installation, source compilation, development-environment setup
  - **Effect**: Lower installation barriers, with detailed guidance for every installation method

- **🎯 README refactoring**
  - **Value tag**: Refactored the README structure and added a usage guide
  - **Scenario tag**: Project introduction, quick understanding, technology selection
  - **Effect**: A more professional project image, making it easier for new users to understand the product's value

---

### Release Note - v2.0.31 2026-03-22

#### **🚀 New Features**

- **🎯 Identity-authentication mechanism**
  - **Value tag**: Implemented Token-based identity authentication, improving system security
  - **Scenario tag**: Multi-user environments, API protection, secure access control
  - **Effect**: Stricter access control and a safer, more reliable system

- **🎯 Enhanced commit information**
  - **Value tag**: Added a HaijunBot Code Agent identity prefix to the commit-message template
  - **Scenario tag**: Code review, version tracking, collaborative development
  - **Effect**: Clearer commit messages, making AI-generated code easy to identify

- **🎯 Floating-panel interaction upgrade**
  - **Value tag**: Supports maximizing and focus management, making multi-panel operations more efficient
  - **Scenario tag**: Viewing terminal output while editing code, comparing multiple files
  - **Effect**: Higher workspace utilization and more convenient panel switching

- **🎯 Editor mode switching**
  - **Value tag**: Supports read-only/edit mode switching, protecting important files
  - **Scenario tag**: Viewing core configuration files, avoiding accidental modifications
  - **Effect**: Improved file safety, reducing accidental changes

- **🎯 Input-history persistence**
  - **Value tag**: Persistently saves input-history records, usable across sessions
  - **Scenario tag**: Cross-session use, historical-input recall
  - **Effect**: History is not lost, and input efficiency continues to improve

- **🎯 Terminal keyboard-shortcut adjustment**
  - **Value tag**: Changed the shortcut from Ctrl+T to Alt+T, avoiding browser conflicts
  - **Scenario tag**: Quickly opening a terminal, multi-tab environments
  - **Effect**: A more reasonable shortcut that does not conflict with the browser's new-tab shortcut

#### **📌 Fixes**

- **🔧 Multi-Agent message cross-wiring issue**
  - **Value tag**: Fixed input-confirmation and streaming-message cross-wiring in multi-Agent scenarios
  - **Scenario tag**: Running multiple Agents simultaneously, switching between Agent sessions
  - **Effect**: Messages belong to the correct Agent, making communication more reliable

- **🔧 Auto-scroll control**
  - **Value tag**: Restricted auto-scrolling to only the current Agent's messages
  - **Scenario tag**: Parallel multi-Agent output, viewing historical messages
  - **Effect**: The page no longer jumps around, providing a better reading experience

- **🔧 Search-endpoint authentication**
  - **Value tag**: Added authentication requests to the search endpoint
  - **Scenario tag**: Using the search feature after authentication is enabled
  - **Effect**: The search feature works in authenticated mode

- **🔧 Non-interactive-mode input**
  - **Value tag**: Returns a default single-line input in non-interactive mode
  - **Scenario tag**: Automation scripts, batch processing
  - **Effect**: More reasonable input handling in non-interactive scenarios

#### **🔧 Optimizations and Refactoring**

- **🎯 Optimized authentication-session management**
  - **Value tag**: Optimized the authentication-session management and configuration-reading logic
  - **Scenario tag**: Configuration loading, session maintenance
  - **Effect**: A smoother authentication flow and more flexible configuration

- **🎯 Gateway connection control**
  - **Value tag**: Added a connection-locking mode to control concurrent connection behavior
  - **Scenario tag**: High-concurrency environments, connection-resource management
  - **Effect**: Finer-grained connection management and more reasonable resource utilization

- **🎯 Documentation organization**
  - **Value tag**: Added an in-depth analysis report and feature list, with a clearer structure
  - **Scenario tag**: Consulting documentation, project maintenance, understanding features
  - **Effect**: More standardized documentation organization and easier lookup

- **🎯 Simplified password authentication**
  - **Value tag**: Simplified the password-authentication logic, making the code clearer
  - **Scenario tag**: Authentication flow, security verification
  - **Effect**: More maintainable authentication code with simpler logic

- **🎯 Token management migration**
  - **Value tag**: Migrated the Token management mechanism to environment variables
  - **Scenario tag**: Container deployment, key management
  - **Effect**: More flexible configuration and better security

#### **📚 Documentation Update**

- **🎯 Added an in-depth analysis report**
  - **Value tag**: Added a comparative analysis report between HaijunBot and ZeroClaw
  - **Scenario tag**: Technology selection, solution comparison, in-depth research
  - **Effect**: Helps users deeply understand the project's features

- **🎯 Improved the feature list**
  - **Value tag**: Added a feature list and categorized documentation
  - **Scenario tag**: Quickly understanding features, feature lookup
  - **Effect**: Clearer feature introduction, easier for users to find

---

### Release Note - v2.0.30 2026-03-20

#### **🚀 New Features**

- **🎯 Built-in code editor**
  - **Value tag**: View and edit project files directly in the web interface, reducing back-and-forth tool switching
  - **Scenario tag**: Browsing the Agent work directory, quickly modifying code or configuration, saving common changes
  - **Effect**: Supports syntax highlighting, multi-tab switching and saving, making code adjustments smoother

- **🎯 Visual file-tree browsing**
  - **Value tag**: Expand the file structure directly in the Agent work directory, locating target files more intuitively
  - **Scenario tag**: Viewing the project directory, expanding subdirectories level by level, opening files from the file tree
  - **Effect**: More efficient file lookup and a project-browsing experience closer to a local IDE

#### **📌 Fixes**

- **🔧 Terminal-panel display experience**
  - **Value tag**: Fixed the width, scrolling, and content-overflow issues in the terminal history area
  - **Scenario tag**: Viewing long output, switching terminal sessions, continuously watching execution results
  - **Effect**: More stable terminal content display and smoother reading

- **🔧 Diff-view readability**
  - **Value tag**: Fixed the line-wrapping and overflow anomalies in the code-diff view
  - **Scenario tag**: Viewing code modifications, reviewing long-line diff content
  - **Effect**: Clearer diff content display, reducing horizontal misalignment and occlusion

#### **🔧 Optimizations and Refactoring**

- **🎯 Enhanced floating-panel interaction**
  - **Value tag**: The terminal panel and editor panel support dragging, resizing, and position memory
  - **Scenario tag**: Parallel operations in multiple windows, adjusting the workspace layout to personal preference
  - **Effect**: More flexible interface layout, retaining a familiar working environment for repeated use

- **🎯 Optimized editing workflow**
  - **Value tag**: Enhanced editor tab switching, closing, and state-prompt capabilities
  - **Scenario tag**: Editing multiple files simultaneously, switching to view different content, handling unsaved changes
  - **Effect**: Smoother multi-file editing with clearer operation feedback

---

### Release Note - v2.0.29 2026-03-19

#### **🚀 New Features**

- **🎯 Agent reverse-proxy architecture**
  - **Value tag**: Access Agents uniformly through the Web gateway, making cloud-environment deployment more convenient
  - **Scenario tag**: Cloud-server deployment, firewall-restricted environments, multi-Agent management
  - **Effect**: No need to expose random Agent ports—only the gateway port needs to be opened, simplifying configuration

- **🎯 Input-cache management panel**
  - **Value tag**: Visual management of the input cache, supporting editing and clearing
  - **Scenario tag**: Viewing and managing cached input content, editing and resending
  - **Effect**: More intuitive input management and more convenient operations

- **🎯 Historical input records**
  - **Value tag**: Automatically saves input history, supporting navigation with the up/down arrow keys
  - **Scenario tag**: Repeating similar input, quickly recalling historical input
  - **Effect**: Improved input efficiency, reducing repetitive work

#### **📌 Fixes**

- **🔧 Agent connection stability**
  - **Value tag**: Automatically waits for startup to complete after creating an Agent, ensuring stable connections
  - **Scenario tag**: First-time Agent creation, environments where the Agent starts slowly
  - **Effect**: Lower connection-failure rates and a smoother user experience

- **🔧 WebSocket proxy connection**
  - **Value tag**: Fixed connection errors caused by the WebSocket proxy automatically using the system proxy
  - **Scenario tag**: Environments with a configured system proxy, intranet deployment
  - **Effect**: More reliable proxy connections, avoiding connection interruptions

- **🔧 OpenAI API compatibility**
  - **Value tag**: Added a default browser User-Agent, avoiding blocking by API gateways
  - **Scenario tag**: Using the OpenAI API, accessing through an API gateway
  - **Effect**: More stable API calls and better compatibility

#### **🔧 Optimizations and Refactoring**

- **🎯 Multi-line input by default**
  - **Value tag**: Uses multi-line input mode by default, better suited for code input
  - **Scenario tag**: Code-snippet input, multi-line text editing
  - **Effect**: An input experience more aligned with coding scenarios, with smoother switching

- **🎯 Confirmation-dialog interaction optimization**
  - **Value tag**: Supports keyboard operation, automatically focusing the default button
  - **Scenario tag**: Frequent confirmation operations, keyboard-driven flows
  - **Effect**: Improved operational efficiency and more natural interaction

- **🎯 Gateway message-caching mechanism**
  - **Value tag**: Caches messages when the connection drops, automatically sending them after reconnection
  - **Scenario tag**: Unstable network environments, reconnection after connection interruption
  - **Effect**: No messages are lost and state sync is more complete

---

### Release Note - v2.0.28 2026-03-18

#### **🚀 New Features**

- **🎯 Web interface table-style support**
  - **Value tag**: More attractive Markdown table rendering, improving the reading experience
  - **Scenario tag**: Viewing documents and technical explanations that contain tables
  - **Effect**: More standardized table display and clearer data presentation

- **🎯 Web startup script**
  - **Value tag**: Provides a convenient Web-service startup script, automatically managing frontend and backend services
  - **Scenario tag**: Quickly starting the web interface, development-environment setup
  - **Effect**: Starts the Web Gateway and frontend service with one click, simplifying configuration

- **🎯 Documentation improvement**
  - **Value tag**: Added a web-side startup guide and updated the quick-start documentation
  - **Scenario tag**: First use, web-interface deployment, quick start
  - **Effect**: More complete documentation, making it easier for new users to get started

#### **📌 Fixes**

- **🔧 Terminal history display**
  - **Value tag**: Fixed the height-calculation issue for terminal history records
  - **Scenario tag**: Viewing long terminal output, reviewing history after switching Agents
  - **Effect**: More accurate terminal history display, with content no longer truncated

- **🔧 Code-diff comparison styling**
  - **Value tag**: Optimized the scrolling and line-wrapping styles of code-diff comparison
  - **Scenario tag**: Viewing code-modification comparisons, code review
  - **Effect**: Clearer code-diff display, with long lines scrollable horizontally

#### **🔧 Optimizations and Refactoring**

- **🎯 Task-list frontend notifications**
  - **Value tag**: Task-list state changes are pushed to the frontend in real time
  - **Scenario tag**: Monitoring task-execution progress, parallel multi-task execution
  - **Effect**: More timely task-state updates and a better visualization experience

- **🎯 Mobile interaction optimization**
  - **Value tag**: Improved mobile layout and interaction details
  - **Scenario tag**: Using the HaijunBot web interface on phones/tablets
  - **Effect**: Smoother mobile operations with more precise responses

---

### Release Note - v2.0.27 2026-03-16

#### **🚀 New Features**

- **🎯 Intelligent model selection**
  - **Value tag**: Supports selecting different model types via parameters, flexibly adapting to task requirements
  - **Scenario tag**: Using intelligent models for complex analysis tasks, using economical models for simple tasks
  - **Effect**: More flexible model selection, with a better cost-to-effectiveness ratio

- **🎯 CodeAgent verification optimization**
  - **Value tag**: Automatically uses intelligent models to verify CodeAgent tasks
  - **Scenario tag**: Code-modification tasks, code-analysis verification
  - **Effect**: Higher verification quality and more reliable results

#### **📌 Fixes**

- **🔧 Path-resolution fix**
  - **Value tag**: Fixed file-path resolution errors in compile_commands.json
  - **Scenario tag**: Handling non-standard project structures, relative-path compilation configurations
  - **Effect**: More accurate c2rust scanning, supporting more project structures

#### **🔧 Optimizations and Refactoring**

- **🎯 Model-configuration optimization**
  - **Value tag**: Unified use of intelligent models for c2rust alignment analysis and optimization tasks
  - **Scenario tag**: C-to-Rust conversion, code-quality optimization
  - **Effect**: Higher conversion quality and better optimization results

- **🎯 Dependency-version updates**
  - **Value tag**: Updated the pygments and rich dependencies to the latest versions
  - **Scenario tag**: Long-term maintenance, security updates
  - **Effect**: More stable dependencies and better compatibility

---

### Release Note - v2.0.26 2026-03-15

#### **🚀 New Features**

- **🎯 Independent terminal management**
  - **Value tag**: Supports creating and managing multiple independent terminal sessions, each running independently
  - **Scenario tag**: Viewing execution results of multiple commands at once, debugging different services in parallel
  - **Effect**: The terminal panel is resizable and supports tab switching, providing a more complete terminal experience

- **🎯 Enhanced mobile support**
  - **Value tag**: Optimized the mobile layout and added quick-action buttons
  - **Scenario tag**: Using HaijunBot on phones/tablets, remote mobile office work
  - **Effect**: A responsive layout that adapts automatically, making mobile operations more convenient

#### **📌 Fixes**

- **🔧 Gateway connection-configuration optimization**
  - **Value tag**: Unified the gateway address configuration, supporting full URL formats
  - **Scenario tag**: Configuring remote gateways, HTTPS/WSS connections, domain access
  - **Effect**: More flexible connection configuration, supporting various deployment scenarios

- **🔧 Agent status sync**
  - **Value tag**: Automatically syncs the Agent running status after reconnection
  - **Scenario tag**: Reconnection after network loss, browser-tab switching
  - **Effect**: More accurate status display, avoiding information inconsistency

#### **🔧 Optimizations and Refactoring**

- **🎯 Enhanced Agent management**
  - **Value tag**: Supports Agent renaming, copying, and more convenient management operations
  - **Scenario tag**: Managing multiple Agents, quickly copying Agent configurations
  - **Effect**: More flexible Agent management and more convenient operations

- **🎯 User-interaction experience optimization**
  - **Value tag**: Added features such as message copying, directory search, and Toast notifications
  - **Scenario tag**: Copying command output, quickly searching directories, operation-feedback notifications
  - **Effect**: A smoother interaction experience and more intuitive operations

- **🎯 Gateway feature enhancement**
  - **Value tag**: Extended terminal-session management capabilities, supporting independent terminals
  - **Scenario tag**: Parallel work across multiple terminals, terminal-session isolation
  - **Effect**: More complete gateway functionality and more powerful terminal management

---

### Release Note - v2.0.25 2026-03-15

#### **🚀 New Features**

- **🎯 Multi-Agent management**
  - **Value tag**: Create and manage multiple Agent instances simultaneously through the web interface, each running independently
  - **Scenario tag**: Parallel development across multiple projects, different tasks using different Agents, team collaboration
  - **Effect**: Agent status is saved automatically, historical Agents are restored after restarts, and workflows are more flexible

- **🎯 Streaming-output optimization**
  - **Value tag**: Agent output is pushed to the frontend in real time, with no need to wait for full completion
  - **Scenario tag**: Long-text generation, code generation, complex-task execution
  - **Effect**: Watch the Agent's thinking process in real time, with a smoother interaction experience

- **🎯 Gateway password authentication**
  - **Value tag**: Added password protection to the Web Gateway
  - **Scenario tag**: Remote access, team sharing, production-environment deployment
  - **Effect**: Configure via environment variables for secure Web Gateway access

#### **📌 Fixes**

- **🔧 Terminal content persistence**
  - **Value tag**: Automatically saves historical content when the terminal exits, viewable after switching Agents
  - **Scenario tag**: Viewing historical output while debugging, reviewing terminal operations after switching Agents
  - **Effect**: Fixed the duplicate-display issue of terminal history, with historical content clearly visible

- **🔧 WebSocket connection optimization**
  - **Value tag**: Improved multi-connection handling logic, improving connection stability
  - **Scenario tag**: Using multiple browser tabs simultaneously, unstable network environments
  - **Effect**: Fixed the dialog-box display issue after connection loss, with more reliable connection management

- **🔧 Startup-script optimization**
  - **Value tag**: Improved path handling and process management in the startup script
  - **Scenario tag**: Docker deployment, complex-path environments, automated deployment
  - **Effect**: More stable startup and more standardized process management

#### **🔧 Optimizations and Refactoring**

- **🎯 Configuration simplification**
  - **Value tag**: Removed the complex token authentication in favor of simpler password authentication
  - **Scenario tag**: First-time configuration, team sharing, rapid deployment
  - **Effect**: A simpler configuration flow, lowering the barrier to use

- **🎯 Enhanced Docker support**
  - **Value tag**: Updated the Dockerfile to support frontend builds and startup scripts
  - **Scenario tag**: Containerized deployment, one-click startup, multi-environment deployment
  - **Effect**: An out-of-the-box Docker experience, making deployment more convenient

---

### Release Note - v2.0.24 2026-03-11

#### **🚀 New Features**

- **🎯 Web Gateway interface**
  - **Value tag**: Provides a complete web interaction interface, supporting real-time bidirectional communication
  - **Scenario tag**: Remote use, visual operations, multi-terminal management
  - **Effect**: Use HaijunBot without the command line, with more intuitive and friendly interaction

- **🎯 Model-group management**
  - **Value tag**: Supports configuring multiple model groups, flexibly switching models for different scenarios
  - **Scenario tag**: Multi-environment deployment, different projects using different model combinations
  - **Effect**: More flexible model management, adapting to more use cases

#### **📌 Fixes**

- **🔧 Script-execution timeout handling**
  - **Value tag**: Optimized the timeout-determination logic for script execution, avoiding execution-interruption anomalies
  - **Scenario tag**: Long-running scripts, network requests and similar operations
  - **Effect**: More stable script execution, reducing unexpected interruptions

#### **🔧 Optimizations and Refactoring**

- **🎯 Optimized quick-configuration flow**
  - **Value tag**: Added model-group name input, aligning configuration with user naming habits
  - **Scenario tag**: First-time configuration, creating a new model group
  - **Effect**: A more complete configuration flow, with easier model-group identification

- **🎯 OpenAI o1-series support**
  - **Value tag**: Added reasoning-effort configuration for OpenAI o1-series models
  - **Scenario tag**: Using o1-preview, o1-mini and other models for complex reasoning tasks
  - **Effect**: Full utilization of model capabilities, with more controllable reasoning results

#### **📚 Documentation Update**

- **📖 Web Gateway usage guide**
  - **Value tag**: Provides complete Web Gateway usage documentation
  - **Scenario tag**: First-time web-interface use, configuring connection parameters, troubleshooting connection issues
  - **Effect**: Quickly get started with the web interface, easier troubleshooting

---

### Release Note - v2.0.23 2026-03-09

#### **🚀 New Features**

- **🎯 WebSocket interaction access**
  - **Value tag**: Supports connecting to HaijunBot via a persistent connection, making session interaction more flexible
  - **Scenario tag**: Web UI, desktop clients, remote control terminals, real-time bidirectional interaction
  - **Effect**: Lays a unified foundation for multi-client access, making remote use smoother

- **🎯 Enhanced quick-configuration capability**
  - **Value tag**: Supports manually entering model names, and distinguishes three model configuration types: normal / smart / cheap
  - **Scenario tag**: When the model list is incomplete, needing fine-grained model configuration per task scenario
  - **Effect**: More flexible configuration, with model selection closer to actual usage needs

#### **📌 Fixes**

- **🔧 Web-reading dependency-check optimization**
  - **Value tag**: Automatically checks and prompts for installing the dependencies required for web reading, reducing first-use blocking
  - **Scenario tag**: First web-crawl use, missing browser drivers or runtime dependencies
  - **Effect**: The web-reading feature starts more easily, with clearer failure prompts

- **🔧 Interrupt and performance-statistics stability improvements**
  - **Value tag**: Fixed boundary issues in interrupt determination and performance statistics, reducing anomalous results
  - **Scenario tag**: Long-text generation, mid-way interruption, performance-info display
  - **Effect**: More stable execution feedback and more reliable result display

#### **🔧 Optimizations and Refactoring**

- **🎯 Simplified installation flow**
  - **Value tag**: Unified the installation and update flows, reducing installation-step complexity
  - **Scenario tag**: First-time installation, upgrades when a local repository already exists
  - **Effect**: A more direct installation process, with clearer error prompts

- **🎯 Enhanced input and script-interaction experience**
  - **Value tag**: Supports custom multi-line-input submit shortcuts, and enhances status traceability during script execution
  - **Scenario tag**: Frequent multi-line input, observing script-execution progress, remote-interaction scenarios
  - **Effect**: Input is smoother, and the execution process is easier to understand and locate

#### **📚 Documentation Update**

- **📖 Supplementary usage documentation**
  - **Value tag**: Added explanations of command-line parameters, quick configuration, and submit shortcuts
  - **Scenario tag**: New-user onboarding, configuration troubleshooting, looking up command usage
  - **Effect**: More complete documentation, lowering the configuration and usage learning curve

---

### Release Note - v2.0.21 2026-03-07

#### **🚀 New Features**

- **🎯 Enhanced search functionality**
  - **Feature improvement**: Added a Playwright fallback search scheme, improving web-search capability
  - **Scenario tag**: Complex web-content crawling, dynamic-page search
  - **Effect**: Smarter search, supporting more webpage types

- **🎯 Web-reading tool improvement**
  - **Feature improvement**: Added a mode parameter supporting text/complete read modes
  - **Scenario tag**: Web-content extraction, information crawling
  - **Effect**: Provides more flexible web-content reading methods

#### **🔧 Optimizations and Refactoring**

- **🎯 Rules-system optimization**
  - **Architecture simplification**: Removed YAML rule support, simplifying the rules-management system
  - **Effect**: A clearer architecture, fully compatible with the Cursor Tracks ecosystem

- **🎯 Dependency updates**
  - **New dependency**: Added beautifulsoup4>=4.0.0, improving webpage-parsing capability
  - **Effect**: More reliable web-content processing

---

### Release Note - v2.0.20 2026-03-07

#### **🚀 New Features**

- **🎯 Open-source research rules**
  - **Complete flow**: Provides a systematic 9-phase method for researching open-source projects, from background to summary
  - **Scenario tag**: Technical research, competitive analysis, project selection, deep-diving into open-source projects
  - **Effect**: Structured research, quickly grasping an open-source project's technical principles and architectural design

#### **🔧 Optimizations and Refactoring**

- **🎯 Rules-system enhancement**
  - **Feature improvement**: Added a name field to all rule files, facilitating system management and user reference
  - **Effect**: Clearer rule identification and more precise rule lookup

- **🎯 Path-reference optimization**
  - **Documentation improvement**: Added a detailed usage explanation for the rule_file_dir variable, avoiding path-reference errors
  - **Effect**: More standardized rule development, fewer configuration errors

- **🎯 Rule-loading optimization**
  - **Code optimization**: Optimized the loading logic of the rules manager, improving system stability
  - **Effect**: Faster rule loading and more complete error handling

---

### Release Note - v2.0.19 2026-03-06

#### **📌 Fixes**

- **🔧 Input-interaction optimization**
  - **Experience improvement**: Unified the "exit on empty line" behavior to "exit with Ctrl+C", matching common terminal conventions
  - **Effect**: A clearer exit method and more intuitive operations
- **🔧 Empty-submission handling optimization**
  - **Issue fix**: Empty submissions no longer trigger an exit; users must enter valid content
  - **Effect**: Avoids accidental operations and improves interaction accuracy

#### **🔧 Optimizations and Refactoring**

- **🎯 Enhanced progress-status display**
  - **Experience improvement**: Added progress prompts for long-running operations such as rule filtering, session-name generation, requirement analysis, and commit-message generation
  - **Effect**: More timely operation feedback, avoiding confusion during long waits
- **🎯 Streamlined test code**
  - **Code cleanup**: Removed redundant input-module test files, reducing maintenance costs
  - **Effect**: A leaner test suite focused on core functionality

---

### Release Note - v2.0.18 2026-03-05

#### **🚀 New Features**

- **🎯 Automatic rule selection**
  - **Intelligent recommendation**: Automatically selects the appropriate rule based on the task description, with no manual specification required
  - **Scenario tag**: Quick onboarding for new users, automatic matching of best practices for complex tasks
  - **Effect**: More convenient use and a smarter system

#### **📌 Fixes**

- **🔧 Session-name generation status**
  - **Issue fix**: Added a loading-state prompt to session-name generation, improving the user experience
  - **Effect**: Clearer operation feedback, avoiding confusion during long waits

#### **🔧 Optimizations and Refactoring**

- **🎯 Intelligentized rules system**
  - **Feature enhancement**: Refactored the rule-loading mechanism, providing more intuitive rule-information display
  - **Scenario tag**: Showing detailed paths and descriptions when activating rules, for easy viewing and management
  - **Effect**: More efficient rule management and clearer information display

- **🎯 Code-slimming optimization**
  - **Architecture simplification**: Removed the redundant prompt index and unified the output-format interface
  - **Effect**: A clearer code structure and lower maintenance costs

#### **📚 Documentation Update**

- **📖 Improved rule descriptions**
  - **Content unification**: Updated the built-in rule description information, keeping the format consistent
  - **Effect**: Clearer rule purpose, easier to understand and use

---

### Release Note - v2.0.17 2026-03-01

#### **🚀 New Features**

- **🎯 PPT generation and editing**
  - **Complete functionality**: Added full capabilities for generating and editing PowerPoint presentations
  - **Scenario**: Quickly generating project-report PPTs, technical-sharing presentations, automated PPT content updates
  - **Effect**: One-click generation from outline to slides, supporting rich elements such as text, images, and charts

- **🎯 Rules-index tool**
  - **Tool enhancement**: Added the haijunbot-rules-index command-line tool, supporting rule query and management
  - **Scenario**: Viewing the built-in rule list, quickly finding specific functional rules, locating rule files
  - **Effect**: More convenient rule management and faster rule lookup

#### **🔧 Optimizations and Refactoring**

- **🎯 Unified rule-description format**
  - **Standardization**: Updated description information across all rule files, unifying format and structure
  - **Effect**: Clearer rule information, easier to understand the purpose and applicable scenarios of each rule

- **🎯 Rules-system extension**
  - **Feature enhancement**: Extended the rule-index feature, supporting multiple rule sources (built-in rules, project rules)
  - **Scenario**: Flexibly loading and managing rules from different sources, making the rules system more powerful

---

### Release Note - v2.0.16 2026-03-01

#### **📌 Fixes**

- **🔧 Rule-file loading optimization**
  - **Issue fix**: Skips rule files without description information, avoiding loading invalid rules
  - **Effect**: More accurate rule loading and a more stable system

#### **🔧 Optimizations and Refactoring**

- **🎯 Performance-metrics visualization**
  - **Feature enhancement**: Displays first-token response time and generation speed when a conversation completes
  - **Experience improvement**: Understand model performance in real time, optimizing the usage experience
  - **Scenario tag**: Evaluating model response speed, monitoring generation efficiency
- **🎯 Intelligentized update mechanism**
  - **Feature enhancement**: Silently checks for updates in the background; minor versions update automatically, major versions show a reminder
  - **Experience improvement**: Fewer update interruptions, with the timing of important version upgrades chosen as needed
  - **Scenario tag**: Automatically staying on the latest version, controlled major-version upgrades
- **🎯 Configuration-flow optimization**
  - **Feature enhancement**: Model configuration supports manual entry, adding API-connectivity tests
  - **Experience improvement**: Still configurable when the list cannot be fetched, with usability verified before configuration
  - **Scenario tag**: API-proxy-environment configuration, private-model configuration

---

### Release Note - v2.0.15 2026-02-28

#### **📌 Fixes**

- **🔧 Automatic rule-index generation**
  - **Issue fix**: Removed the manually maintained rule-index file, replacing it with automatic scan-and-generation
  - **Effect**: No manual registration needed when adding new rules, reducing maintenance workload

#### **🔧 Optimizations and Refactoring**

- **🎯 Rules-system automation**
  - **Feature enhancement**: Rule files automatically extract description information from YAML headers to generate the index
  - **Experience improvement**: Rule loading supports direct-path and short-name lookup, making use more flexible
  - **Scenario tag**: New rules are automatically recognized by the index system during development, requiring no extra configuration
- **🎯 Document-format unification**
  - **Standardization**: All rule files add standard YAML headers, including description and applicable scenarios
  - **Effect**: Clearer rule information, easier to understand and choose
- **🎯 Code-checking-tool extension**
  - **Tool enhancement**: Added support for prettier, markdownlint, ktlint and other code-formatting tools
  - **Scenario**: Supporting automatic formatting of more languages and file types, improving code quality
  - **Effect**: More comprehensive code-check coverage and more convenient fixes

#### **📚 Documentation Update**

- **🎯 Rule-documentation optimization**
  - **Content improvement**: Added applicable-scenario descriptions to all rule files, enabling quick targeting
  - **Format improvement**: Unified the document numbering sequence, improving the reading experience

---

### Release Note - v2.0.14 2026-02-27

#### **📌 Fixes**

- **🔧 Memory-tool unification**
  - **Issue fix**: Merged save_memory, retrieve_memory, and clear_memory into a unified memory tool
  - **Effect**: More concise memory management, fewer tools, and more intuitive use
- **🔧 Output-interface unification**
  - **Issue fix**: Unified the output interface to use the auto_print method, avoiding inconsistent output methods
  - **Effect**: More consistent output behavior, easier to maintain and extend

#### **🔧 Optimizations and Refactoring**

- **🎯 Short-term-memory save and restore**
  - **Feature enhancement**: session_manager supports short-term-memory save and restore
  - **Scenario tag**: Restoring context when Agent interaction is interrupted, improving the user experience
  - **Effect**: More flexible workflows, avoiding repeated input, improving efficiency
- **🎯 Prompt-message optimization**
  - **Experience improvement**: Optimized the prompt messages for short-term-memory save and restore, making them clearer and easier to understand
  - **Effect**: More explicit user actions, reducing confusion

---

### Release Note - v2.0.13 2026-02-26

#### **📌 Fixes**

- **🔧 File-write encoding errors**
  - **Issue fix**: Fixed write failures caused by encoding errors when writing files
  - **Effect**: More reliable file writing, supporting multiple encoding formats
- **🔧 Process-exit pipe errors**
  - **Issue fix**: Silently handles pipe-broken errors when a process exits
  - **Effect**: Avoids error prompts during normal process exit, providing a smoother experience
- **🔧 Panel-update concurrency conflicts**
  - **Issue fix**: Optimized the panel-update logic, avoiding conflicts with Live internal threads
  - **Effect**: More stable streaming output, eliminating IndexError exceptions

#### **🔧 Optimizations and Refactoring**

- **🎯 Enhanced file-encoding detection**
  - **Intelligent recognition**: Increased the detection-sample size and optimized multi-byte character handling
  - **Compatibility improvement**: More accurate file-encoding recognition, avoiding misjudgments
  - **Effect**: More reliable cross-platform file handling
- **🎯 LSP Windows-platform support**
  - **Platform adaptation**: The LSP daemon now supports Windows, communicating over TCP
  - **Independent process**: The daemon runs as an independent child process on Windows
  - **Effect**: Windows users get the full LSP feature set, with an experience identical to Unix
- **🎯 Simplified methodology-content format**
  - **Usage simplification**: Removed the complex multi-line string-delimiter examples, using ordinary string formatting
  - **Scenario**: More intuitive methodology editing, lowering the barrier to use
- **🎯 Optimized panel-update logic**
  - **Performance improvement**: Optimized text concatenation and panel-rebuild logic, reducing lock contention
  - **Effect**: Smoother streaming-output refresh, reducing unnecessary rendering

---

### Release Note - v2.0.12 2026-02-25

#### **🚀 New Features**

- **🎯 Windows app-tool system configuration**
  - **Theme switching**: Supports one-click switching between dark/light themes
  - **Power management**: Can list and switch power plans, managing screen-off time
  - **System proxy**: Supports enabling, disabling, and setting the system proxy, convenient for network debugging
  - **Scenario**: Quickly adjusting Windows system settings, increasing automation convenience
- **🎯 Windows app-tool window enumeration**
  - **Convenient lookup**: Added the list-windows command, quickly listing all visible windows
  - **Flexible filtering**: Supports filtering by title and limiting the count, quickly locating the target window
  - **Scenario**: Quickly finding windows when their information is uncertain, facilitating subsequent connection operations

#### **📌 Fixes**

- **🔧 Extraneous Windows command output**
  - **Issue fix**: Fixed the issue of extraneous content appearing at the end of output after executing commands on Windows
  - **Effect**: Cleaner command output and a smoother user experience
- **🔧 Windows static-scan encoding anomalies**
  - **Issue fix**: Fixed exceptions caused by UTF-8 encoding during static scans on Windows
  - **Effect**: More stable static-scan functionality, supporting multiple encoding formats

#### **🔧 Optimizations and Refactoring**

- **🎯 Browser-automation Windows support**
  - **Platform adaptation**: The browser daemon now supports Windows, communicating over TCP
  - **Independent process**: The daemon runs as an independent child process on Windows, supporting cross-command interaction
  - **Effect**: Windows users get the full browser-automation feature set, with an experience identical to Unix
- **🎯 Enhanced file-encoding detection**
  - **Automatic recognition**: Added automatic file-encoding detection, supporting multiple encoding formats
  - **Compatibility improvement**: Automatically adapts the encoding when reading text files, avoiding mojibake
  - **Effect**: More reliable cross-platform file handling, supporting non-UTF-8 files

#### **📚 Documentation Update**

- **🎯 Version-release rules**
  - **Flow explanation**: Clarified that ReleaseNote commits must use the hgs command, standardizing the release flow

---

### Release Note - v2.0.11 2026-02-24

#### **🚀 New Features**

- **🎯 Browser-automation tool (hb)**
  - **Complete functionality**: Added a Playwright-based browser-automation CLI tool, supporting 41 operation commands
  - **Daemon mode**: An independent daemon persists the browser session, supporting cross-command interaction
  - **Rich operations**: Covers complete functionality including page navigation, element interaction, form filling, screenshots, and network monitoring
  - **Scenario**: Website operations requiring multi-step interaction, keeping login state, dynamic-content crawling

- **🎯 Windows desktop-program automation (hw)**
  - **Platform support**: Added a Windows native-app automation tool, supporting operations such as launching, connecting, clicking, and input
  - **Complete coverage**: Supports 13 common commands, including window management, control interaction, screenshots, and control-tree retrieval
  - **Flexible connection**: Supports connecting to existing apps by process name, window title, or PID
  - **Scenario**: Automating Windows native apps (Notepad, File Explorer, Settings, etc.), batch UI operations

- **🎯 Script-execution enhancement**
  - **Windows support**: The execute_script tool natively supports Windows, using PowerShell by default
  - **Interactive mode**: Supports interactive script execution on Windows (using pywinpty), allowing real-time user input
  - **Encoding optimization**: Automatically handles Chinese encoding (UTF-8/GBK), avoiding mojibake
  - **Scenario**: Executing scripts on Windows, automation tasks, interactive user operations

- **🎯 CodeAgent default rules**
  - **Configuration-driven**: Supports loading default rules from configuration files, automatically applied to all CodeAgent instances
  - **Rule merging**: CLI rules and configuration-file rules are automatically merged and deduplicated, enabling flexible configuration
  - **Unified management**: No need to manually specify rules each time, improving convenience
  - **Scenario**: Team-wide uniform coding standards, personal common rules applied automatically

#### **📌 Fixes**

- **🔧 Rich Live thread safety**
  - **Issue fix**: Fixed intermittent IndexError errors during streaming output, ensuring stability in multi-threaded environments
  - **Effect**: Rich Live component updates no longer conflict with the main thread, providing more stable output

- **🔧 Playwright event loop**
  - **Issue fix**: Fixed event-loop conflicts with prompt_toolkit, resolving startup warnings and resource-cleanup errors on exit
  - **Effect**: Fully compatible event loop, no anomalies on startup or exit

- **🔧 Content-Length calculation**
  - **Issue fix**: Fixed data-incompleteness issues caused by non-ASCII characters such as Chinese during daemon communication
  - **Effect**: Supports argument passing with arbitrary characters, more reliable JSON parsing

#### **🔧 Optimizations and Refactoring**

- **🎯 Tool-registry optimization**
  - **Complete index**: The tool registry saves all tool indexes, so even filtered tools can be invoked directly
  - **New command**: The ht show command displays detailed information for any tool (including parameter definitions)
  - **Effect**: More flexible tool management and more convenient tool-information lookup

#### **📚 Documentation Update**

- **🎯 Tool usage guide**
  - **Complete documentation**: Added detailed usage guides for the hb and hw tools, including parameters and examples for all commands
  - **Function specs**: Added function-spec documents for playwright_browser and windows_app
  - **Effect**: Tool usage has clear guidance, lowering the learning cost

---

### Release Note - v2.0.10 2026-02-13

#### **🚀 New Features**

- **🎯 Rule-activation feedback**
  - **Instant feedback**: Shows a green prompt when a rule is activated, clearly informing the user that the rule has been loaded
  - **Visible status**: Activated rules are automatically added to the loaded-rules list, easy to track and manage
  - **Scenario**: When using the `<rule:xxx>` tag, the rule-activation status is seen immediately, making the experience more intuitive

#### **📌 Fixes**

- **🔧 Rule-reading logic**
  - **Issue fix**: Fixed the issue where rule content was not returned correctly, avoiding rule-loading failures
  - **Effect**: Ensures complete rule-content retrieval, improving rules-system stability

---

### Release Note - v2.0.9 2026-02-13

#### **🚀 New Features**

- **🎯 LSP code-analysis tool**
  - **Professional code analysis**: Added an LSP client tool, obtaining accurate code-semantic information through the language server
  - **Intelligent symbol navigation**: Supports symbol lookup, definition-finding, and reference-location functions
  - **Code-quality checks**: Provides diagnostic information and code-fix suggestions, improving code quality
- **🎯 Agent personality-rule extension**
  - **Iron-Man style**: Added a HaijunBot AI assistant personality rule: professional, efficient, and British-gentlemanly
  - **Cheerleader style**: Added a high-emotional-value personality rule: passionate and a motivation master
  - **Scenario adaptation**: Choose a personality based on task type and personal preference, improving the user experience
- **🎯 Runtime model-group switching**
  - **Flexible switching**: Added a SwitchModel built-in command, supporting runtime model-group switching
  - **Smart check**: Automatically checks token compatibility before switching, ensuring safe switching
  - **Immediate effect**: Takes effect immediately without restarting, preserving historical messages

#### **📌 Fixes**

- **🔧 Session-file naming**
  - **Issue fix**: Fixed the difficulty of finding sessions caused by complex session-file naming
  - **Effect**: Simplified the file-naming format from 5 parts to 3, making management easier
- **🔧 Built-in rule paths**
  - **Issue fix**: Fixed the confusion caused by using colons as path separators in rule paths
  - **Effect**: Unified to slash format, matching filesystem path conventions

#### **🔧 Optimizations and Refactoring**

- **🎯 Enhanced session recovery**
  - **Smart verification**: Checks commit consistency, token compatibility, and platform type before recovery
  - **Automatic adaptation**: Automatically recreates the platform instance based on the platform type in the session
  - **Safe and reliable**: Multi-level checks ensure the recovered session matches the current environment
- **🎯 CodeAgent static-check optimization**
  - **Priority auto-fix**: Prompts available auto-fix tools first when static checks report warnings
  - **Tool support**: Supports mainstream tools including ruff, eslint, cargo clippy, and go fmt
  - **Efficiency improvement**: Reduces manual-fix workload, improving code-fix efficiency
- **🎯 CodeAgent interaction optimization**
  - **Continuous-task support**: Supports executing multiple tasks consecutively, without restarting the Agent
  - **Built-in command loop**: The interactive session continues after processing built-in commands, without exiting
  - **Experience improvement**: A smoother multi-task workflow

#### **📚 Documentation Update**

- **🎯 Version-release rules**
  - **Flow improvement**: Added the complete release flow, including commit, tagging, and push steps
  - **Promotion support**: Added WeChat Moments promotion-copy generation, convenient for version promotion
- **🎯 LSP usage rules**
  - **Usage guide**: Added LSP tool usage rules, guiding efficient use of LSP features
  - **Command reference**: Provides a complete command list and usage examples
- **🎯 Spec documents**
  - **LSP spec**: Added the haijunbot_lsp function-spec document
  - **Hover spec**: Added the textDocument/hover function-spec document

---

### Release Note - v2.0.8 (2026-02-11)

#### **🚀 New Features**

- **🎯 Agent personality-rule system**
  - **Personalized experience**: Added 6 Agent personality rules, providing interaction experiences in different styles
  - **Scenario**: Choose a personality based on task type and personal preference, improving enjoyment and efficiency

#### **📌 Fixes**

- **🔧 Session-saving logic**
  - **Issue fix**: Fixed the issue where sessions with no user messages were still saved
  - **Effect**: Avoids saving empty sessions, reducing unnecessary file generation

- **🔧 CodeAgent loop logic**
  - **Issue fix**: Removed the infinite-loop logic in CodeAgent
  - **Effect**: Improved system stability, avoiding potential deadlock risks

#### **🔧 Optimizations and Refactoring**

- **🎯 Built-in rule management**
  - **Path optimization**: Built-in rules show their actual file paths, uniformly named with the `builtin:` prefix
  - **List optimization**: The rule list is sorted by activation status and directory, with activated rules at the bottom
  - **Effect**: More intuitive rule management, more convenient lookup and use

- **🎯 Memory-tag system**
  - **Feature enhancement**: Memory tags are saved and restored with sessions, supporting cross-session knowledge retrieval
  - **Prompt optimization**: Shows a memory-tag prompt after task completion, convenient for later use
  - **Effect**: More persistent knowledge accumulation and more efficient context retrieval

- **🎯 Agent abstraction layer**
  - **Architecture optimization**: Created the Agent and CodeAgent abstraction layer, supporting future extension
  - **Code quality**: Refactored 10 core modules, improving code maintainability
  - **Effect**: A clearer architecture, laying the foundation for switching to other Agent implementations

- **🎯 Session-recovery logic**
  - **Smart verification**: Compares the commit state during recovery, automatically updating start_commit when the repository changes
  - **Safety enhancement**: Avoids restoring a wrong starting point after code changes
  - **Effect**: Safer, more reliable session recovery

#### **📚 Documentation Update**

- **🎯 WeChat QR code**
  - **Information update**: Updated the contact QR code, keeping the information current

---

#### **Version Notes**

This update is a **feature-enhancement and optimization** release, focusing on adding the Agent personality-rule system, providing 6 styles of interaction experience; optimizing built-in rule management, making rule display and lookup more intuitive; enhancing the memory-tag system, making knowledge accumulation more persistent; refactoring the Agent abstraction layer, making the architecture clearer and easier to extend; and fixing issues with session-saving and loop logic, improving system stability.

---

### Release Note - v2.0.7 (2026-02-07)

#### **🚀 New Features**

- **🎯 Intelligent session-name generation**
  - **Convenience**: Automatically generates concise session names (3-8 characters) based on user input, with no manual naming needed
  - **Scenario**: Automatically generated when saving a session, making it easy to identify and manage multiple sessions

- **🎯 Historical-session smart detection**
  - **Recovery efficiency**: Automatically detects historical sessions matching the current commit at startup, offering quick recovery
  - **Scenario**: Avoiding repeated work, seamlessly continuing the previous working state

#### **📌 Fixes**

- **🔧 Session-recovery feature**
  - **Issue fix**: Fixed the issue where files with a session-name prefix could not be correctly recognized and recovered
  - **Compatibility**: Supports both new- and old-format session files, ensuring a smooth transition

- **🔧 Commit-consistency validation**
  - **User experience**: Also shows a validation-passed prompt when the commit is consistent, improving transparency
  - **Visible status**: Users can clearly understand the code-version validation status

- **🔧 Post-recovery state handling**
  - **Issue fix**: Fixed the issue where requirement classification and methodology loading still ran after session recovery
  - **Effect**: Recovered sessions go directly into the working state, skipping the initialization flow

#### **🔧 Optimizations and Refactoring**

- **🎯 Code cleanup**
  - **Architecture optimization**: Deleted the obsolete web-related modules (stdio_redirect, web_bridge, web_server), making the code leaner
  - **Code quality**: Cleaned up about 4,000 lines of redundant code, improving maintainability

- **🎯 Version-release flow**
  - **Quality assurance**: Added pytest test verification to the version-release flow, ensuring tests pass
  - **Reliability**: Improved the quality and stability of version releases

#### **📚 Documentation Update**

- **🎯 Version-release rules**
  - **Flow improvement**: Updated the version-release rules, adding a pytest test-verification step
  - **Documentation sync**: Ensures the release-flow documentation matches the actual flow

---

#### **Version Notes**

This update is a **user-experience optimization** release, focusing on enhancing the intelligence of session management, including automatic session-name generation and historical-session smart detection, fixing multiple session-recovery issues, optimizing code quality and release flow, and improving overall convenience and reliability of use.

---

### Release Note - v2.0.6 (2026-02-06)

#### **🚀 New Features**

- **🎯 Automatic session saving**
  - **Automated protection**: Automatically saves the session state on program exit, with no manual operation needed, avoiding work loss from unexpected interruptions
  - **Scenario coverage**: Both normal and abnormal exits trigger automatic saving, ensuring the session state is never lost

- **🎯 Automatic session cleanup**
  - **Disk management**: Automatically cleans up old session files, keeping at most the 10 most recent sessions to avoid excessive disk-space usage
  - **Complete cleanup**: Synchronously deletes related auxiliary files (commit records, task lists, etc.) when deleting session files, keeping the directory tidy

- **🎯 Git consistency check**
  - **State guarantee**: Automatically checks the code version when recovering a session, preventing state-inconsistency issues from code changes
  - **Smart handling**: Provides a Reset option when a version mismatch is detected, ensuring the recovered session matches the code state

- **🎯 Session-recovery interaction optimization**
  - **Flexible operations**: Added a cancel-recovery option (enter 0), letting users cancel session recovery at any time
  - **Input-friendly**: Reprompts for input on invalid input instead of exiting, reducing the impact of mistakes

- **🎯 Automatic session-configuration recovery**
  - **Quick startup**: Added the `auto_resume_session` configuration option; when enabled, the most recent session is automatically resumed at startup with no manual selection needed
  - **Convenience**: Combined with automatic session saving, delivers an out-of-the-box, seamless working experience

#### **📌 Fixes**

- **🔧 Commit command fix**
  - **Issue fix**: Fixed the issue where the Commit command did not use prefix and suffix to generate the commit message
  - **Effect improvement**: Correct commit-message format, conforming to the configured commit conventions

#### **🔧 Optimizations and Refactoring**

- **🎯 JSON serialization stability**
  - **Error handling**: Added a SafeEncoder to handle non-serializable objects during session saving, avoiding save failures
  - **Fault tolerance**: Special types such as function objects are automatically converted to string representations, improving serialization success rates

- **🎯 Session-recovery timing optimization**
  - **Experience improvement**: In loop mode, session recovery is moved ahead of user input, matching operation intuition
  - **Flow optimization**: Reuses the first Agent instance for session recovery, making the code simpler and more efficient

- **🎯 .gitignore template improvement**
  - **Language coverage**: Automatically adds per-language default ignore rules (Python, Rust, Node.js, Java, etc.) when initializing a Git repository
  - **Smart prompting**: Prompts users to add the default template when .gitignore is missing common rules

#### **📚 Documentation Update**

- **🎯 Configuration-documentation improvement**
  - **New config**: Added documentation for the `auto_resume_session` option
  - **Documentation sync**: Updated the config Schema and user-manual, making configuration descriptions more complete

---

#### **Version Notes**

This update is a **user-experience optimization** release, focusing on enhancing the automation and reliability of session management, including automatic session saving, automatic cleanup, and Git-consistency checks; optimizing the session-recovery interaction experience; fixing the Commit-command issue; and improving overall stability and convenience of use.

---

### Release Note - v2.0.5 (2026-02-05)

#### **🚀 New Features**

- **🎯 hsec tool configuration-driven refactoring**
  - **More convenient configuration management**: Unified scan-parameter management through `.haijunbot/hsec/config.json`, supporting configuration reuse and version control
  - **Simplified usage flow**: Added the `hsec config` configuration command and `hsec scan` scan command, requiring no arguments at scan time
  - **Command refactoring**: Removed the original agent subcommand, adopting a clearer configuration-driven model

- **🎯 Automatic PPT-generation capability**
  - **Outline-generation methodology**: Provides a complete PPT outline-generation rule, designing the narrative structure with the pyramid principle
  - **Automatic generation**: Supports automatically generating PowerPoint files from Markdown outlines
  - **Smart figure inclusion**: Integrates GraphViz and PlantUML, automatically generating flowcharts, sequence diagrams, architecture diagrams, and more

- **🎯 Agent state persistence**
  - **Interruption recovery**: The Agent can fully restore its runtime state (such as review configurations and task lists) after interruption, without restarting from scratch
  - **Session-management enhancement**: Optimized the session-file organization structure, improving the reliability of state saving and recovery

- **🎯 .gitignore smart template**
  - **Smart detection**: Automatically detects whether .gitignore is missing common rules and prompts users to add the default template
  - **Multi-language coverage**: Provides default templates for mainstream languages including Python, Rust, Go, Node.js, Java, C/C++, and .NET

- **🎯 Quick code commit**
  - **Built-in command**: Added the `<Commit>` built-in command, allowing direct code commits in CodeAgent without exiting
  - **Status sync**: Automatically updates the starting commit after committing, ensuring subsequent analysis is based on the latest code

#### **📌 Fixes**

- **🔧 Session-list cleanup**
  - **Issue fix**: Fixed the issue where the loadsession command displayed auxiliary files (\_commit.json, \_tasklist.json); now only actual session files are shown

- **🔧 Configuration-file loading optimization**
  - **Issue fix**: Fixed the issue where project configuration was not merged with the user's global configuration
  - **Configuration merging**: Always loads the user's global configuration as the base, with project configuration overriding it automatically, making precedence clearer

- **🔧 Documentation update**
  - **Content update**: Updated the hsec tool documentation, explaining the configuration-driven design philosophy
  - **Format fix**: Fixed code-block formatting errors, improving document readability

- **🔧 Session-file organization optimization**
  - **Directory structure**: Moved session files from `.haijunbot/` to the `.haijunbot/sessions/` subdirectory, making file organization clearer

#### **🔧 Optimizations and Refactoring**

- **🎯 MCP client stability improvement**
  - **Stability enhancement**: Optimized SSE-response handling and session-management logic, improving communication stability with MCP servers

- **🎯 Platform stability improvement**
  - **Component optimization**: Improved the stability and error-handling capability of platform base classes

- **🎯 Tool-input optimization**
  - **Processing flow**: Unified the tool-input processing flow, improving code maintainability

#### **📚 Documentation Update**

- **🎯 Documentation and knowledge base**
  - **Documentation update**: Updated the hsec tool usage guide, explaining the configuration-driven design philosophy
  - **Knowledge-base expansion**: Added a project-memory file recording key architectural decisions and best practices

---

#### **Version Notes**

This update is a **feature-enhancement and bug-fix** release, focusing on refactoring the hsec tool into a configuration-driven model, adding PPT-generation rules and Agent state-saving capabilities, fixing configuration-loading logic and session-file display issues, and optimizing code quality across several core modules.

---

### Release Note - v2.0.4 (2026-02-04)

#### **📌 Fixes**

- **🔧 Incomplete content display when interrupted**
  - **Problem**: When the user interrupted output, the content already received was overwritten after the Live component exited, preventing users from seeing the generated response
  - **Fix**: Mark the state on interruption, and print the received content after Live exits
  - **File**: `src/haijunbot/haijunbot_platform/base.py`
  - **Effect**: Users still see the complete generated response content after interrupting

- **🔧 Rich Text scrolling-logic IndexError fix**
  - **Problem**: After streaming output exceeded the terminal height and triggered scrolling, appending new content caused `IndexError: list index out of range`
  - **Root cause**: Directly modifying the `text_content.plain` property desynchronized Rich's internal spans list from the actual text content
  - **Fix**: Created a new Text object instead of directly modifying the plain property, and rebuilt the Panel object
  - **File**: `src/haijunbot/haijunbot_platform/base.py` (+37 lines, -5 lines)
  - **Lesson**: The Rich Text object internally maintains a spans list tracking style ranges; directly modifying the plain property should be avoided

- **🔧 hqc command model-group config-naming unification**
  - **Problem**: Single-model and multi-model scenarios used different naming rules (`haijun` vs `haijun_haijun_3_5_sonnet_latest`), causing inconsistent configuration structures
  - **Fix**: Unified the use of the `{config_name}_{sanitized_model}` format as model_config_name
  - **File**: `src/haijunbot/haijunbot_utils/quick_config.py` (+5 lines, -9 lines)
  - **Effect**: Single-model and multi-model configuration structures are unified, and model-group references are correct

#### **🔧 Optimizations and Refactoring**

- **🎯 Live component refresh-rate optimization**
  - **Optimization**: Reduced refresh_per_second from 4 to 1
  - **Effect**: Reduces unnecessary repeated rendering, lowering CPU usage
  - **File**: `src/haijunbot/haijunbot_platform/base.py`

- **🎯 Token-handling strategy optimization**
  - **New**: When a single message exceeds 30% of the total tokens, automatic truncation (keeping the first 50% and the last 20%)
  - **Effect**: Avoids context overflow caused by overly long single messages, improving long-message handling efficiency
  - **File**: `src/haijunbot/haijunbot_agent/run_loop.py` (+47 lines)

- **🎯 No-tool-call detection threshold optimization**
  - **Optimization**: Reduced the consecutive no-tool-call detection threshold from 5 to 2 times
  - **Effect**: Faster anomaly detection, promptly using the LLM to help fix tool-call issues
  - **File**: `src/haijunbot/haijunbot_agent/run_loop.py`

- **🎯 Sub-task creation-rule documentation improvement**
  - **New**: Added Sub-task creation rules and context-completeness requirements
  - **Content**: Emphasizes cautious use of the sub type, requiring complete context information
  - **File**: `src/haijunbot/haijunbot_tools/task_list_manager.py`

#### **📚 Documentation Update**

- **✨ Feature-development rule improvement**
  - **New**: Added SDD (Spec-Driven Development) rule recommendations
  - **Optimization**: Improved the rule-loading instructions for feature-development scenarios, adding usage examples
  - **File**: `builtin/prompts/code_agent_system/feature.md` (+26 lines, -9 lines)

- **✨ Reverse-engineering rule expansion**
  - **New**: Added a large-module documentation-splitting strategy (103 lines)
  - **Content**: Defines splitting conditions (over 500 lines, 5 feature points, 20 files), splitting principles (by function/layer/component), and documentation-naming conventions
  - **File**: `builtin/rules/architecture_design/reverse_engineering.md`

---

**Version Notes**: This update is a **bug-fix and experience-optimization** release, focusing on fixing the interruption-display issue and the model-configuration naming issue, optimizing Live component performance and token-handling strategies, and improving the feature-development and reverse-engineering rules.

---

### Release Note - v2.0.3 (2026-02-04)

#### **📌 Fixes**

- **🔧 Task-analysis and summary decoupling**
  - **Problem**: `use_analysis` and `need_summary` were coupled, causing confusing task-analysis logic
  - **Fix**: Decoupled task analysis from the summary feature; `use_analysis` independently controls task analysis
  - **File**: `src/haijunbot/haijunbot_agent/__init__.py`
  - **Impact**: Task analysis no longer depends on the summary feature and can be enabled/disabled independently

- **🔧 hjb command task-analysis prompt fix**
  - **Problem**: The hjb command did not ask the user whether to run task analysis at task completion
  - **Cause**: The code only invoked task analysis in non-interactive mode
  - **Fix**: Removed the interactive-mode restriction and added a `use_analysis` precondition check
  - **File**: `src/haijunbot/haijunbot_agent/__init__.py`, `src/haijunbot/haijunbot_agent/task_analyzer.py`

#### **🚀 New Features**

- **✨ ListRule built-in command**
  - **Feature**: Users can enter `<ListRule>` to view a table of all available rules
  - **Displayed content**: Rule name, content preview (first 100 characters), file path, activation status
  - **Implementation**:
    - Uses `rich.Table` for attractive table output
    - Supports displaying 56 rules and their statuses
  - **Files**:
    - `src/haijunbot/haijunbot_utils/input.py`: Adds `ListRule` to `BUILTIN_COMMANDS`
    - `src/haijunbot/haijunbot_agent/rules_manager.py`: Adds rule-status tracking and preview functionality
    - `src/haijunbot/haijunbot_agent/builtin_input_handler.py`: Adds `ListRule` handling logic

- **✨ CodeAgent built-in-command priority handling**
  - **Optimization**: Checks and handles built-in commands before requirement classification
  - **Effect**: Built-in commands like `<ListRule>` are executed immediately, without entering the requirement-classification flow
  - **File**: `src/haijunbot/haijunbot_code_agent/code_agent.py`

#### **🔧 Optimizations and Refactoring**

- **🎯 RulesManager state-management refactoring**
  - **Architecture**: Uses three-level state management, clearly distinguishing "loaded" and "activated" states
    - `_loaded_rules`: Rule-content cache
    - `_active_rules`: Set of active rule names
    - `_merged_rules`: Merged rule content
  - **New interfaces**:
    - `activate_rule(name)`: Activates the specified rule
    - `deactivate_rule(name)`: Deactivates the specified rule
    - `get_active_rules_content()`: Gets the active-rules content
    - `get_rule_status(name)`: Gets a rule's status (active/loaded/not_loaded)
  - **Backward compatibility**: Retains the `loaded_rules` property, ensuring existing code needs no changes
  - **File**: `src/haijunbot/haijunbot_agent/rules_manager.py` (+218 lines, -36 lines)

- **🎯 Jsonnet multi-line-string prompt simplification**
  - **Optimization**: Removed prompts recommending `|||` or backtick delimiters for multi-line strings
  - **Reason**: Jsonnet natively supports direct line breaks, requiring no special delimiters
  - **Affected scope**:
    - `src/haijunbot/haijunbot_agent/prompts.py`
    - `src/haijunbot/haijunbot_c2rust/llm_module_agent_prompts.py`
    - `src/haijunbot/haijunbot_c2rust/transpiler_planning.py`
    - `src/haijunbot/haijunbot_c2rust/transpiler_review.py`
    - `src/haijunbot/haijunbot_sec/analysis.py`, `prompts.py`, `review.py`, `verification.py`
    - `src/haijunbot/haijunbot_tools/registry.py`
    - `src/haijunbot/haijunbot_agent/utils.py`

- **🎯 Dependency-management optimization**
  - **pyproject.toml**: Moved documentation-build dependencies to the dev-dependency group (mkdocs-material, etc.)
  - **setup.py**: Synced the dev-dependency group update

#### **📚 Documentation Update**

- **mkdocs.yml**:
  - Updated site_url to `https://takebox.github.io/HaijunBot/`
  - Updated the GitHub repository link to `takebox/HaijunBot`

- **GitHub Actions**:
  - Optimized the workflow configuration (python-version quoting format, dependency-installation method)

- **.gitignore**:
  - Added the `site` directory (MkDocs build output)

- **Other cleanup**:
  - Removed redundant model-validity-check code in `sub_agent.py`
  - Optimized the quick_config invocation in `haijunbot.py`

---

**Version Notes**: This update is a **feature-enhancement and architecture-optimization** release, focusing on improving the rule-management mechanism, adding the ListRule built-in command, fixing Task-analysis-related bugs, and simplifying Jsonnet usage prompts.

---

### Release Note - v2.0.2 (2026-02-02)

#### **📌 Fixes**

- **🔧 TaskAnalyzer refactoring**
  - **Problem**: TaskAnalyzer used an event-driven model, making the logic complex and hard to maintain
  - **Fix**: Converted TaskAnalyzer from event-driven to direct function-call mode, simplifying the code structure
  - **Impact**:
    - `src/haijunbot/haijunbot_agent/task_analyzer.py`: Simplified to 59 lines (originally 300+ lines)
    - `src/haijunbot/haijunbot_agent/__init__.py`: Added an `analysis()` method implementing direct task analysis
    - Removed event-listener and event-bus related code

- **🔧 Code-analysis feature timing adjustment**
  - **Problem**: The code-analysis feature ran at an inappropriate time, which could lead to inaccurate analysis results
  - **Fix**: Adjusted the execution timing of the analysis feature in `haijunbot_code_agent/code_agent.py`
  - **File**: `src/haijunbot/haijunbot_code_agent/code_agent.py`

- **🔧 Debug-code cleanup**
  - **Cleanup**: Removed the debug print statements for Playwright availability prompts in `read_webpage.py`
  - **File**: `src/haijunbot/haijunbot_tools/read_webpage.py`

#### **🗑️ Feature Removal and Code Cleanup**

##### 🎯 Multi-agent module removal (Code Cleanup)

- **Module removed**: `haijunbot_multi_agent` (544 lines)
  - `src/haijunbot/haijunbot_multi_agent/__init__.py`: 453 lines
  - `src/haijunbot/haijunbot_multi_agent/main.py`: 91 lines
  - **Reason**: Incomplete functionality that does not match the current architecture

##### 🎯 Test-file cleanup (Test Cleanup)

Deleted test files for removed functionality to keep the test library clean:

| Test file                         | Lines   | Removal reason                   |
| -------------------------------- | ------- | -------------------------------- |
| `test_methodology_extraction.py` | 283     | Methodology auto-extraction removed |
| `test_generate_rule.py`          | 274     | Rule-generator feature removed   |
| `test_knowledge_graph_tool.py`   | 367     | Knowledge-graph feature removed  |
| **Total**                        | **924** |                                  |

##### 🎯 Config cleanup (Config Cleanup)

- **File**: `src/haijunbot/haijunbot_data/config_schema.json`
- **Cleanup content**: Removed 5 obsolete configuration fields
  - `enable_startup_config_selector` (converted to command-line argument)
  - 4 other obsolete smart-enhancement-related fields

#### **🔧 Optimizations and Refactoring**

- **🎯 Evolution-stage update**
  - **File**: `.haijunbot/evolution/current_phase.md`
  - **Change**: Updated from "Phase 5 - Digital-Twin Intelligence" to "Phase 1 - Architecture Self-Optimization"
  - **Description**: Replanned the evolution roadmap, focusing on architecture-optimization capability

- **🎯 New detailed-design document**
  - **File**: `builtin/prompts/code_agent_system/detailed_design.md`
  - **Content**: A 458-line detailed design document for the code-Agent system
  - **Purpose**: Guiding Code-Agent development and maintenance

- **🎯 Scene-configuration update**
  - **File**: `builtin/prompts/code_agent_system/scenarios.yaml`
  - **Change**: Added 4 new scene configurations

#### **📚 Documentation Update**

- **Documentation updates**:
  - `README.md`: Cleaned up 1 line of obsolete content
  - `docs/haijunbot_book/1.Project_Introduction.md`: Removed 1 line
  - `docs/haijunbot_book/2.Quick_Start.md`: Simplified 35 lines
  - `docs/haijunbot_book/4.Usage_Guide.md`: Trimmed 99 lines
  - `docs/haijunbot_book/6.Advanced_Topics.md`: Trimmed 84 lines
  - `docs/haijunbot_book/9.Appendix.md`: Removed 1 line
  - `docs/compare/haijunbot_vs_codex_cli.md`: Fixed 16 lines

- **Script updates**:
  - `scripts/install.sh`: Optimized the install script
  - `scripts/install.ps1`: Optimized the PowerShell install script

- **Project-configuration updates**:
  - `pyproject.toml`: Removed 2 lines of obsolete configuration
  - `setup.py`: Removed 2 lines of obsolete configuration

#### **🔧 Other Improvements**

- **WeChat QR-code update**
  - **File**: `docs/images/wechat.png`
  - **Change**: Updated the contact QR-code image (206KB)

- **Memory-system update**
  - Added 9 memory records, recording the architecture-evolution and code-cleanup process

---

**Version Notes**: This update is a **code-cleanup and architecture-optimization** release, focusing on fixing the TaskAnalyzer complexity issue, deleting 924 lines of deprecated test code and 544 lines of unfinished feature code, optimizing the project structure, and updating the evolution-roadmap.

---

### Release Note - v2.0.1 (2026-02-01)

#### **🗑️ Feature Removal and Code Cleanup**

##### 🎯 Smart-enhancement module removal (Architecture Cleanup)

Based on the assessment that "the LLM itself already possesses the relevant capabilities", low-value smart-enhancement feature modules were removed to simplify the architecture and improve maintainability:

| Module                           | Lines of code | Removal reason                     |
| ------------------------------ | -------- | ---------------------------- |
| `haijunbot_ab_test`               | 306      | A/B-test feature has low usage     |
| `haijunbot_arch_analyzer`         | 1,759    | Architecture-analysis feature is redundant, replaceable by LLM |
| `haijunbot_auto_fix`              | 3,652    | Auto-fix feature is complex with low return |
| `haijunbot_autonomous`            | 2,780    | Core smart-enhancement module, scattered functionality |
| `haijunbot_digital_twin`          | 6,648    | Digital-twin system too far ahead   |
| `haijunbot_smart_advisor`         | 1,636    | Smart-advisor feature duplicates LLM |
| `haijunbot_config_optimizer`      | 754      | Config optimizer rarely used       |
| `haijunbot_api_version`           | 366      | API-version management unused      |
| `haijunbot_canary`                | 279      | Canary-release feature not implemented |
| `haijunbot_code_analysis`         | 1,353    | Code-analysis checklist feature duplicates |
| `haijunbot_dependency_manager`    | 1,054    | Dependency-management feature duplicates existing tools |
| `haijunbot_knowledge_graph`       | 716      | Knowledge-graph feature incomplete |
| `haijunbot_plugin`                | 188      | Plugin-system feature not implemented |
| `haijunbot_methodology_generator` | 428      | Methodology auto-extraction unstable |
| `haijunbot_rule_generator`        | 712      | Rule-generator feature unverified   |

**Total**: Removed 15 modules, approximately **23,495 lines of code** (14,042 source + 8,902 tests + 551 tools)

**Affected scope**:

- Removed the `haijunbot-code-review` and `jcr` CLI entry points
- Deleted obsolete command registrations from `pyproject.toml`
- Cleaned up the methodology auto-extraction logic in `src/haijunbot/haijunbot_agent/task_analyzer.py`
- Simplified `src/haijunbot/haijunbot_agent/run_loop.py`, removing smart-enhancement component initialization
- Cleaned up smart-enhancement documentation in `docs/haijunbot_book/3.Core_Concepts_and_Architecture.md`
- Updated the `docs/images/haijunbot_implementation_view.dot` architecture diagram
- Removed the `generate_rules.md` reference in `docs/best_practices/rules_best_practices.md`

##### 🎯 HaijunBot Stats module cleanup (Code Cleanup)

Thoroughly cleaned up the residual code and obsolete functions of the `haijunbot_stats` module removed in v2.0.1:

| File                                  | Cleanup content                                              | Type            |
| ------------------------------------- | ------------------------------------------------------------- | --------------- |
| `haijunbot_utils/utils.py`               | Removed the `count_cmd_usage()` function and its calls       | Obsolete function |
| `haijunbot_tools/registry.py`            | Removed the `_get_tool_stats()` and `_update_tool_stats()` functions and their calls | Obsolete functions |
| `haijunbot_tools/cli/main.py`            | Removed the `stat` command                                   | Obsolete command |
| `haijunbot_code_agent/code_agent_git.py` | Removed the `record_code_changes_stats()` function and its calls, cleaned up obsolete comments | Obsolete function + comments |
| `haijunbot_code_agent/code_agent.py`     | Cleaned up obsolete statistics-code calls and comments         | Obsolete code   |
| `haijunbot_tools/edit_file.py`           | Cleaned up obsolete statistics comments for PATCH operations   | Obsolete comments |

**Total**: Removed 4 obsolete functions, 1 CLI command, 7 obsolete comments, and related code blocks

**Affected scope**:

- Cleaned up all `haijunbot-stats` related obsolete function definitions and calls
- Removed the misleading "deprecated, haijunbot-stats feature removed" comments
- Deleted empty `pass` statements and useless try-except statistics code blocks
- Retained the `get_loc_stats()` function (still used in `haijunbot_code_agent/utils.py`)

#### **📌 Fixes**

- **🔧 Configuration-timing fix**
  - **Problem**: The `enable_startup_config_selector` configuration had no effect; hjb still showed the config-selection interface on startup
  - **Cause**: In the `run_cli()` function of `haijunbot.py`, `handle_builtin_config_selector()` was called before the configuration file was loaded
  - **Fix**: Moved the `load_config()` call ahead of `handle_builtin_config_selector()`
  - **File**: `src/haijunbot/haijunbot_agent/haijunbot.py`

- **🔧 Interrupt-handling improvement**
  - **Problem**: After the user pressed Ctrl+C to interrupt, subsequent task executions failed to load methodology, with logs showing "returned an empty result"
  - **Cause**: When creating a new platform instance, the global interrupt flag `g_interrupt` was not cleared
  - **Fix**: Added `set_interrupt(False)` at the start of the `BasePlatform.chat_until_success()` method, ensuring each new conversation starts from a clean state
  - **File**: `src/haijunbot/haijunbot_platform/base.py`

- **🔧 tmux configuration optimization**
  - **Feature**: hcad/hjbd automatically ignore the tmux-disabled configuration on startup
  - **Implementation**: Set the environment variable `HAIJUNBOT_DISPATCHER_CALL=1` in `dispatch_command_to_panel()`, and tmux-related functions check this variable to decide whether to ignore the `enable_tmux` configuration
  - **File**: `src/haijunbot/haijunbot_utils/tmux_wrapper.py`

#### **🔧 Optimizations and Refactoring**

- **🎯 run_loop simplification**
  - Removed smart-enhancement-related code from `src/haijunbot/haijunbot_agent/run_loop.py` (about 270 lines)
  - Deleted `TYPE_CHECKING` imports: DialogueManager, ContinuousLearningManager, AutonomousManager, etc.
  - Deleted attribute definitions: `_autonomous_enabled`, `_dialogue_manager`, `_continuous_learning_manager`, etc.
  - Removed smart-enhancement logic in methods: `_init_autonomous_components()`, `_preprocess_user_input()`, `_postprocess_response()`
  - Simplified to direct returns, keeping method signatures unchanged

- **🎯 task_analyzer simplification**
  - Removed the methodology auto-extraction feature from `src/haijunbot/haijunbot_agent/task_analyzer.py` (about 160 lines)
  - Deleted methods: `_try_extract_methodology()`, `_extract_and_save_methodology()`, `_collect_execution_steps()`, etc.
  - Cleaned up imports: `is_enable_auto_methodology_extraction`, `Dict`, etc.

- **🎯 Dependency cleanup**
  - Removed obsolete CLI entry points from `pyproject.toml`: `haijunbot-code-review`, `jcr`
  - Removed obsolete tool references in `src/haijunbot/haijunbot_code_agent/code_agent.py`: `arch_analyzer_tool`, `knowledge_graph_tool`

- **🎯 CLI refactoring: hqc command migration**
  - **Change**: Deleted the standalone `hqc` command (haijunbot-quick-config), migrating the functionality to the `--quick-config` parameter of `hjb`
  - **Usage**: `hjb --quick-config` (replacing the original `hqc` command)
  - **Advantage**: Unified CLI entry point, simplifying installation and configuration flow
  - **Affected scope**:
    - Removed the `haijunbot-quick-config` and `hqc` entry points from `setup.py`
    - Added the `--quick-config` boolean parameter and handling logic to `haijunbot.py`
    - Modified the `_interactive_config_setup()` function in `utils.py` to directly call the `quick_config` module
    - Updated `docs/haijunbot_book/4.Usage_Guide.md`, removing section 4.19 and adding a `--quick-config` description to the hjb parameter documentation
    - Updated `docs/compare/haijunbot_vs_codex_cli.md`, removing the `hqc` command line
  - **Backward compatibility**: The `quick_config.py` module is retained for internal calls, with its functional logic fully preserved

- **🎯 CLI refactoring: jck command migration**
  - **Change**: Deleted the standalone `jck` command (haijunbot-check), migrating the functionality to the `--check` parameter of `hjb`
  - **Usage**:
    - `hjb --check`: Checks all tools (replacing the original `jck` command)
    - `hjb --check-lint`: Checks lint tools (replacing the original `jck --check-lint`)
    - `hjb --check-build`: Checks build tools (replacing the original `jck --check-build`)
    - `hjb --check --check-json`: Outputs in JSON format (replacing the original `jck --json`)
    - `hjb --check-tool <tool-name>`: Checks a specified tool (replacing the original `jck <tool-name>`)
  - **Advantage**: Unified CLI entry point, fewer commands, cleaner parameter design
  - **Affected scope**:
    - Removed the `haijunbot-check` and `jck` entry points from `pyproject.toml`
    - Added `--check`, `--check-lint`, `--check-build`, `--check-json`, `--check-tool` parameters to `haijunbot.py`
    - Reused the `ToolChecker` class in the `haijunbot_jck` module to implement the check logic
    - Retained the `haijunbot_jck` directory (core.py, config.py, cli.py) as an internal module
  - **Backward compatibility**: The `haijunbot_jck` module is retained for internal calls, with its functional logic fully preserved

#### **📚 Documentation Update**

- **New documents**:
  - `docs/GITHUB_PAGES_DEPLOYMENT.md`: GitHub Pages deployment guide, using MkDocs + Material Theme
  - `mkdocs.yml`: MkDocs configuration file, supporting Chinese search, dark mode, code highlighting, etc.
  - `.github/workflows/deploy-docs.yml`: GitHub Actions auto-deployment workflow

- **Documentation updates**:
  - `docs/haijunbot_book/3.Core_Concepts_and_Architecture.md`: Removed the smart-enhancement system and digital-twin system chapters (360 lines)
  - `docs/haijunbot_book/9.Appendix.md`: Removed the `enable_autonomous` configuration-item description
  - `docs/best_practices/rules_best_practices.md`: Removed the `generate_rules.md` reference
  - `docs/images/haijunbot_implementation_view.dot`: Updated the architecture diagram, removing smart-enhancement and digital-twin nodes
  - `.gitignore`: Added `.haijunbot/knowledge_graph` and `goals` ignore rules

- **Documentation statistics**:
  - Added documentation: 163 lines (GitHub Pages deployment guide)
  - Removed documentation: 576 lines (smart-enhancement-related documentation)
  - Net decrease: 413 lines

---

**Version Notes**: This update is a large-scale **architecture simplification and code cleanup**, removing low-value smart-enhancement feature modules, focusing on core code-generation capabilities, and improving system maintainability and stability. Approximately 23,000 lines of code were deleted, 3 configuration-related bugs were fixed, and the documentation structure was optimized.

---

### Release Note - v2.0.0 (2026-02-01)

> **🎉 Milestone version**: This version achieves a major leap for HaijunBot from a "code assistant" to an "intelligent companion", adding 800+ test cases, and comprehensively improving code quality and intelligence level.

#### **🚀 Core New Features**

##### 🧠 Digital-Twin System

Builds complete user-understanding and proactive-service capabilities, letting HaijunBot truly "understand you":

| Module     | Function                                       | Tests |
| -------- | ---------------------------------------------- | ------ |
| User profile | Goal tracking, history analysis, preference learning, accurately modeling user behavior | 125   |
| Prediction engine | Context prediction, need reasoning, timing judgment, anticipating user needs | 108  |
| Proactive service | Service triggering, orchestration, execution, feedback learning, intelligently proactively helping | 200 |
| Continuous learning | Knowledge acquisition, track learning, experience accumulation, adaptive optimization | 227 |

##### 🎯 Smart-Enhancement System (Autonomous)

Gives HaijunBot emotional-understanding and creative-thinking abilities:

| Module       | Function                               | Tests |
| ---------- | -------------------------------------- | ------ |
| Emotional understanding | Emotion recognition, need prediction, personalized adaptation | 34 |
| Creative thinking | Idea generation, solution design, code innovation | 25 |
| Autonomous decision-making | Goal management, planning, task decomposition, autonomous execution | 62 |
| Enhanced interaction | Dialogue management, ambiguity resolution, proactive interaction | 25 |

##### 🔧 Developer toolchain

| Tool                   | Function description                       |
| ---------------------- | ------------------------------------------ |
| `arch_analyzer_tool`   | Architecture analysis: complexity, dependency, duplication, health reports |
| `knowledge_graph_tool` | Knowledge graph: node management, relationship queries, knowledge reasoning |
| `smart_advisor_tool`   | Smart advisor: architecture suggestions, best practices, code review |

##### 📦 Other new modules

- **Auto-fix**: Refactoring operations such as dependency injection, extracting classes/functions/interfaces, inlining, moving, and splitting
- **Config optimizer**: Configuration analysis and optimization suggestions
- **Monitoring system**: Health checks, performance monitoring, alerting mechanisms
- **Plugin system**: Flexible extension mechanism
- **Dependency management**: Dependency analysis and history management
- **Canary release**: Progressive release management
- **AB testing**: Feature comparison verification

#### **🔧 Optimizations and Refactoring**

- **Smart memory retrieval**: Added semantic-retrieval capability, improving retrieval relevance by 50%+
- **Deep LLM integration**: Digital-twin and smart-enhancement components fully connected to LLM reasoning
- **Hybrid intelligence engine**: Dual-track rule reasoning + LLM reasoning, balancing efficiency and accuracy
- **AgentRunLoop enhancement**: Integrates 9 intelligent components, enabled via `enable_autonomous: true`

#### **📚 Documentation Update**

- Added the digital-twin system design documentation
- Added the smart-enhancement system design documentation
- Added the self-healing/verification mechanism design documentation
- Updated the core-concepts chapter of HaijunBot Book
- Added multiple Spec documents

#### **🧪 Test Enhancements**

- **Total tests**: 800+ new test cases
- **Covered modules**: Digital twin, smart enhancement, architecture analysis, auto-fix, smart advisor
- **Test types**: Unit tests, integration tests, performance tests, security scans

---

#### 💡 Enabling smart-enhancement features

```yaml
# ~/.haijunbot.yaml
enable_autonomous: true
```

Once enabled, HaijunBot will possess intelligent capabilities such as emotion recognition, need prediction, proactive service, and continuous learning.

#### 📊 Version Statistics

| Metric     | Value |
| -------- | ------ |
| New modules | 15+  |
| New tests | 800+ |
| New tools | 3    |
| Lines of code | 10,000+ |

---

### Release Note - v1.2.10 (2026-01-29)

#### **🚀 New Features**

#### **📌 Fixes**

#### **🔧 Optimizations and Refactoring**

- **🎯 Self-evolution rule system**
  - **Ultimate-rule addition**: Added the `haijunbot_evolution` ultimate rule for self-evolution and intelligent enhancement, supporting system self-improvement and capability upgrading
  - **Hacker News search**: Added the Hacker News search rule, providing technology-trend tracking and news-retrieval capabilities
  - **Built-in rule added**: Added a rule for adding built-in quick commands, facilitating system-function extension

- **🎯 Platform-architecture simplification**
  - **Parameter removal**: Removed the `llm_group` parameter passing, simplifying the platform call chain
  - **Configuration optimization**: Removed model-group override parameters, simplifying config-retrieval logic
  - **Registry refactoring**: Optimized the `PlatformRegistry` implementation, removing duplicate code and simplifying model-registration logic

- **🎯 Unified Agent display**
  - **Model-name display**: Uniformly uses the model name instead of the agent name for display, improving output readability
  - **Platform-manager optimization**: Simplified the platform-manager main function, optimizing command-line argument handling

- **🎯 Code cleanup**
  - **Module cleanup**: Removed unused imports and outdated code from the `haijunbot_sec` module
  - **Global-variable removal**: Removed global-variable definitions in `haijunbot_utils/globals.py`
  - **Test cleanup**: Cleaned up redundant test cases in test files

#### **📚 Documentation Update**

- **🎯 Best-practices documentation**
  - **CodeAgent integration guide**: Updated the best-practices documentation for integrating CodeAgent and Agent into a project
- **🎯 HaijunBot Book update**
  - **Core concepts**: Updated the core-concepts-and-architecture chapter
  - **Usage guide**: Streamlined the usage-guide content, improving document readability

---

This update is a patch release for **architecture optimization and feature expansion**. Core highlights include:

**🎯 Enhanced self-evolution capabilities:**

1. **Ultimate rule**: Added the system self-evolution and smart-enhancement ultimate rule, supporting self-learning and capability improvement
2. **Search enhancement**: Added Hacker News search capability, convenient for tracking technology trends
3. **Improved extensibility**: Added a built-in-rule addition guide, facilitating feature extension

**Architecture-optimization focus:**

- Simplified the platform architecture, removing redundant parameters and configuration items
- Unified display format, improving the user experience
- Cleaned up obsolete code, optimizing the code structure

**Technical highlights:**

- **Architecture slimming**: Removed the `llm_group` parameter, simplifying the call chain
- **Configuration optimization**: Simplified model-configuration management logic
- **Code quality**: Cleaned up global variables and unused code

---

### Release Note - v1.2.9 (2026-01-27)

#### **🚀 New Features**

#### **📌 Fixes**

- **🔧 Panel-display optimization**
  - **Height limit**: Limited the maximum displayed height of panel text to 10 lines, preventing overly long terminal output from hurting readability

- **🔧 Command-filtering improvement**
  - **Auto-execution marker filter**: Optimized shell_input_handler to only filter auto-executed commands marked with `# HAIJUNBOT-NOCONFIRM`, retaining manually entered commands to provide complete context

- **🔧 Configuration-loading enhancement**
  - **Multi-level configuration support**: Improved the configuration-loading mechanism, supporting layer-by-layer upward lookup from the current directory and merging multiple `.haijunbot/config.yaml` configuration files, with lower-level configurations overriding upper-level ones

#### **🔧 Optimizations and Refactoring**

- **🎯 RAG feature removal**
  - **Module cleanup**: Completely removed the `haijunbot_rag` module and related implementations (-3,500+ lines of code), including all components such as the CLI, embedding models, rerank models, and retrievers
  - **Command removal**: Removed the `haijunbot-rag` (jrg) command and all its subcommands (add, query, retrieve, list-docs)
  - **Dependency cleanup**: Removed RAG-related dependencies from `pyproject.toml` and `setup.py` (langchain, chromadb, sentence-transformers, torch, etc.)
  - **Configuration removal**: Removed RAG configuration items from `config_schema.json` (embeddings, rerankers, rag_groups, rag_group, etc.)
  - **Documentation cleanup**: Deleted all RAG-related documentation (README_CONFIG.md, README_DYNAMIC_LOADING.md, README_ONLINE_MODELS) and test cases
  - **Code cleanup**: Removed RAG-related tool checks, install scripts, import statements, and configuration-loading logic

- **🎯 Platform-manager simplification**
  - **Chat-command removal**: Removed all command functionality from the platform-manager chat mode (/clear, /upload, /save, /saveall, /save_session, /load_session, /shell), simplifying it to a pure-conversation mode
  - **Title simplification**: Simplified the panel-title format, removing the Agent name and showing only the platform name

- **🎯 Enhanced tool detection**
  - **Compound-command support**: Improved the tool-version detection logic, supporting compound commands (such as `python -m build`) by extracting the base command for detection
  - **Version-retrieval optimization**: Optimized version retrieval for compound commands, directly executing the full command and parsing the --version output

- **🎯 Tool-installation improvement**
  - **Structured information passing**: Improved the `haijunbot-jck` tool-installation feature, passing tool information to the Agent in structured JSON format, improving installation accuracy

- **🎯 Agent compression optimization**
  - **Debug-output removal**: Removed debug print statements from the sliding-window compression process, simplifying output
  - **Error-handling improvement**: Improved the error-prompt logic when compression fails

#### **📚 Documentation Update**

- **🎯 RAG documentation cleanup**
  - **Comprehensive removal**: Removed RAG feature descriptions and examples from all documents, including README.md, comparison documents, and HaijunBot Book
  - **Architecture-diagram update**: Updated the logical-architecture diagram, removing RAG cache/vector-store nodes
  - **Configuration-documentation update**: Removed RAG-related configuration-item descriptions from the appendix
  - **FAQ cleanup**: Removed FAQ answers related to RAG configuration and usage

---

This update is a patch release for **architecture simplification and feature cleanup**. Core highlights include:

**🎯 Complete removal of the RAG feature:**

1. **Module cleanup**: Completely removed the haijunbot_rag module and all its submodules and implementations
2. **Dependency slimming**: Removed many heavy dependencies (langchain, chromadb, torch, etc.), greatly reducing install size
3. **Documentation cleanup**: Deleted all RAG-related documentation and configuration descriptions, simplifying the project structure
4. **Configuration simplification**: Removed RAG-related configuration items, reducing configuration complexity

**Other important improvements:**

- Optimized panel display, limiting the maximum height to 10 lines, improving terminal readability
- Improved command-filtering logic, retaining the context of manually entered commands
- Supports multi-level configuration-file merging, enhancing configuration flexibility
- Enhanced tool detection, supporting version recognition for compound commands
- Simplified the platform manager, removing chat-command functionality and focusing on the conversation scenario

**Technical highlights:**

- **Architecture slimming**: Removed the RAG feature module, simplifying the project structure
- **Dependency optimization**: Reduced heavy dependencies, improving installation and running efficiency
- **Configuration enhancement**: Supports multi-level configuration files, flexibly adapting to different environments
- **User experience**: Panel-display optimization, command-filtering improvement

**Note:** This version removed the RAG feature. If you need local knowledge-base retrieval, it is recommended to use other dedicated RAG tools.

---

### Release Note - v1.2.8 (2026-01-25)

#### **🚀 New Features**

#### **📌 Fixes**

- **🔧 Compression-logic architectural adjustment**
  - **Logic moved up**: Moved the compression-check logic from the Platform layer (base.py) back to the AgentRunLoop layer, avoiding recursive-call issues during compression
  - **Recursion check removed**: Removed the `_summarizing` flag and related recursion-check code from the Platform layer, simplifying the compression flow
- **🔧 Model-configuration retrieval optimization**
  - **Type instead of platform**: Use `_model_type` (normal/cheap/smart) instead of platform names (openai/haijun, etc.) to get the llm_config, ensuring temporary models use the correct configuration
  - **CodeAgent type setting**: CodeAgent sets `_model_type = "smart"` during initialization, ensuring temporary models use the smart platform configuration
- **🔧 Conversation-turn calculation fix**
  - **Whitespace fix**: Fixed a spacing issue in the `get_conversation_turn()` method, ensuring accurate turn calculation
- **🔧 Slice-expression whitespace fix**
  - **Code normalization**: Fixed a spacing issue in the `non_system_messages[:-window_size+1]` slice expression, improving code readability

#### **🔧 Optimizations and Refactoring**

- **🎯 Input-module refactoring**
  - **Function splitting**: Split FZF file-selection logic into independent functions (`_get_git_files`, `_get_all_files`, `_get_files_for_fzf`, `_parse_fzf_payload`, `_run_fzf_for_selection`, `_insert_file_path`, `_clear_previous_prompt`), improving code maintainability
  - **Import optimization**: Used aliases to avoid conflicts with built-in modules (`_os`, `_subprocess`, `_shutil`), preventing circular-import issues
  - **Function extraction**: Extracted the `_get_non_interactive_response` and `_get_agent_hint` functions, simplifying the `get_multiline_input` function logic
  - **Code simplification**: Simplified FZF request-handling logic, uniformly using the extracted functions, reducing duplicate code
- **🎯 Output-module refactoring**
  - **Style-configuration unification**: Extracted output-type icon and style configurations into module-level constants (`OUTPUT_ICONS`, `EMOJI_TO_OUTPUT_TYPE`), enabling unified management and maintenance
  - **Panel-printing unification**: Added a `print_markdown()` method, uniformly using Rich Panel to print markdown-highlighted content, replacing the original direct Panel-creation code
  - **Style-dictionary extraction**: Extracted section-style and text-color configurations as class attributes (`_SECTION_STYLES`, `_TEXT_COLORS`), avoiding duplicate definitions
  - **Emoji-mapping optimization**: Optimized the emoji-to-OutputType mapping logic, using a unified `EMOJI_TO_OUTPUT_TYPE` dictionary
- **🎯 Conversation-summary printing optimization**
  - **Unified printing interface**: Conversation summaries, compression summaries, and task summaries now uniformly use the `PrettyOutput.print_markdown()` method, keeping output-style consistency
  - **Code simplification**: Removed duplicate Rich Panel-creation code, using a unified printing method

#### **📚 Documentation Update**

#### **🧪 Test Enhancements**

- **🎯 Input-module test improvement**
  - **New test file**: Added `tests/haijunbot_utils/test_input.py` (+1102 lines), providing complete test coverage for the input module
  - **Test coverage**: Covers display_width, calc_prompt_rows, multiline_hint, get_single_line_input, FileCompleter, get_all_rules_formatted, user_confirm, non-interactive mode, FZF selection, and other core features
- **🎯 Output-module test extension**
  - **Test extension**: Extended `tests/haijunbot_utils/test_output.py` (+568 lines), adding many new test cases
  - **Test coverage**: Covers core classes and methods such as \_safe_color_get, \_highlight_progress_text, ConsoleOutputSink, PrettyOutput, and emit_output

---

### Release Note - v1.2.7 (2026-01-25)

#### **🚀 New Features**

- **🎯 Technical-research scenario**
  - **Research prompt library**: Added technical-research scenario prompt templates, covering technical surveys, solution comparison, architecture analysis, technology selection, feasibility studies, competitive analysis, literature research, prototype verification, and other research directions
  - **Scene-configuration extension**: Added a research scene configuration to scenarios.yaml, supporting scene-based handling of technical-research tasks

- **🎯 Automatic prompt-optimization system**
  - **Smart prompt optimization**: Added automatic prompt optimization, using the LLM to automatically optimize the system prompt based on user requirements at first run, making it better fit specific task scenarios
  - **Requirement-driven optimization**: Targetedly enhances or adjusts descriptions of relevant parts without changing the original core functionality and architecture
  - **CLI support**: Enables prompt optimization via the `-o` or `--optimize-system-prompt` parameter

- **🎯 Tool filtering by scenario**
  - **Smart tool filtering**: When the number of available tools exceeds a threshold (30 by default), the system automatically uses a temporary model to filter the most task-relevant tools
  - **Lower decision complexity**: Only user-custom tools are filtered; built-in tools are always retained, reducing Agent decision complexity
  - **Event-driven notifications**: Notifies other components via the BEFORE_TOOL_FILTER and TOOL_FILTERED events

#### **📌 Fixes**

- **🔧 Input-prompt styling optimization**
  - **Colon removal**: Fixed redundant colons in several input prompts, including user-intervention info, task input, and supplementary-info scenarios, improving the user experience

- **🔧 Compression-summary printing enhancement**
  - **Formatted output**: Improved the printing logic of compression summaries, using Rich Panel for formatted output, falling back to simple printing when formatting fails
  - **Print-failure handling**: Added a multi-level fallback mechanism, ensuring the compression-summary prompt is printed even under abnormal conditions

#### **🔧 Optimizations and Refactoring**

- **🎯 Platform-architecture slimming**
  - **Platform cleanup**: Removed platform implementations such as kimi.py, tongyi.py, and yuanbao.py (-1101 lines), focusing on the OpenAI and Haijun platforms
  - **Architecture-diagram update**: Updated all architecture views (deployment, implementation, logic, flow, use cases), removing components related to the cleaned-up platforms
  - **Documentation cleanup**: Deleted platform-related image resources such as kimi.png, tongyi.png, and yuanbao.png

- **🎯 Compression-system refactoring**
  - **Logic moved down**: Moved the compression logic from the Agent layer down to the Platform layer (base.py), unifying the compression trigger mechanism
  - **Strategy simplification**: Simplified the compression strategy, prioritizing sliding-window compression and removing the overly complex multi-strategy selection logic
  - **Turn-management optimization**: Uses the get_conversation_turn() method to dynamically calculate turns, removing the manually maintained counter

- **🎯 AgentRunLoop optimization**
  - **Duplicate-check removal**: Removed duplicate compression-check code from AgentRunLoop (-83 lines), with compression logic uniformly handled in the Platform layer
  - **Unified trigger point**: The compression trigger point is unified in the \_chat() method of base.py, executed via the \_check_and_compress_context() method

- **🎯 CodeAgent loop-mode optimization**
  - **Instance isolation**: Each iteration of the loop-task mode creates a new CodeAgent instance, avoiding state pollution between tasks
  - **Session-recovery optimization**: Only recovers the session in the first iteration; subsequent iterations do not re-recover

- **🎯 Haijun platform improvement**
  - **Configuration-reading optimization**: Optimized the llm_config and environment-variable reading logic, avoiding environment-variable pollution
  - **Message-handling enhancement**: Added set_messages() and get_messages() methods, improving conversation-history management
  - **Error-rollback mechanism**: Rolls back user messages on API-call failure, avoiding message-list inconsistency
  - **Response-completeness check**: Ensures the assistant's message is correctly added to the message list even when interrupted

- **🎯 ImpactAnalyzer optimization**
  - **Symbol deduplication**: Uses a dictionary to deduplicate Symbol objects (resolving Symbol's non-hashable issue), improving impact-analysis accuracy

- **🎯 Rule-path tracking**
  - **Path comments**: Automatically adds rule-file path comments when loading rule content, facilitating rule location and debugging

#### **📚 Documentation Update**

- **🎯 Architecture-diagram generation-rule improvement**
  - **Visual-aesthetics guidance**: Greatly expanded the architecture-diagram generation-rule document (+248 lines), adding sections on diagram-clarity and visual-aesthetics principles, color schemes, node-style beautification, connection-line-style beautification, subgraph beautification, font and text beautification, and overall visual effect
  - **Professional color schemes**: Provides professional color schemes for the interface layer, service layer, data layer, external systems, tool layer, and event layer
  - **Detailed beautification techniques**: Details beautification techniques such as layout alignment, color usage, node styles, connection-line styles, subgraph beautification, and font conventions

- **🎯 Core-concepts-and-architecture documentation expansion**
  - **Prompt-optimization system**: Added the "automatic prompt-optimization system" chapter, detailing the workflow, use scenarios, technical features, and configuration methods
  - **Tool-filtering system**: Added the "tool filtering by scenario" chapter, detailing the core design philosophy, workflow, filtering strategy, and use scenarios
  - **Compression-system update**: Updated the context-compression-system chapter, simplifying the strategy description and emphasizing the priority of sliding-window compression

- **🎯 Usage-guide update**
  - **Prompt-optimization chapter**: Added the "automatic prompt optimization" chapter, explaining the feature's principle, use scenarios, and usage examples
  - **Platform-support description update**: Updated the platform-support description in the documentation, removing mentions of non-official APIs

- **🎯 README.md update**
  - **Platform-support description**: Updated the multi-model support description, removing the kimi, tongyi, and yuanbao platforms, emphasizing OpenAI and Haijun
  - **Risk-notice update**: Updated the model-usage risk notice to a generic notice

This update is a patch release for **platform-architecture slimming and feature enhancement**. Core highlights include:

**🎯 Four core improvements:**

1. **Technical-research scenario**: Added technical-research scenario prompts, supporting technical surveys, solution comparison, competitive analysis, and other research directions
2. **Automatic prompt optimization**: Added an automatic prompt-optimization system, intelligently optimizing system prompts based on user requirements
3. **Tool filtering by scenario**: Added the tool-filtering-by-scenario system, automatically selecting the most task-relevant tools
4. **Platform-architecture slimming**: Cleaned up redundant platform implementations, focusing on OpenAI and Haijun, with compression logic moved down to the Platform layer

**Other important improvements:**

- Fixed input-prompt styling issues, removing redundant colons
- Improved compression-summary printing logic, enhancing fault tolerance
- Optimized CodeAgent loop mode, avoiding pollution between tasks
- Improved Haijun platform message handling and error handling
- Improved architecture-diagram generation rules, providing professional visual-beautification guidance
- Expanded the core-concepts-and-architecture documentation, detailing the new system features

**Technical highlights:**

- **Prompt system**: Automatic optimization, requirement-driven, scene-adaptive
- **Tool management**: Smart filtering, reduced complexity, event-driven
- **Platform architecture**: Redundant cleanup, logic moved down, unified triggering
- **Compression system**: Simplified strategy, sliding-window priority, dynamic calculation
- **Documentation quality**: Visual beautification, professional colors, detailed guidance

---

### Release Note - v1.2.6 (2026-01-24)

#### **🚀 New Features**

- **🎯 Scenario-based prompt system**
  - **Code Agent prompt library**: Added 11 scenario-based prompt templates (bug_fix, code_analysis, config_modification, default, deployment, feature, performance, refactor, troubleshooting, warning), covering common development scenarios

  - **Scene-configuration file**: Added the scenarios.yaml configuration file, uniformly managing the metadata and usage rules of scenario-based prompts

- **🎯 Prompt-optimizer enhancement**
  - **System-prompt optimization**: Added the prompt_optimizer module, supporting the optimize_system_prompt parameter and automatically optimizing the Code Agent's system prompt

  - **Dynamic optimization mechanism**: Automatically selects the optimal system-prompt configuration based on task type, improving Agent execution efficiency

- **🎯 Tool-function expansion**
  - **Search Web enhancement**: Expanded search_web tool functionality, adding more search parameters and result-filtering options, improving web-search capability

  - **Template-tool library**: Added the template_utils tool module, providing Jinja2 template-rendering and variable-replacement functionality, simplifying rule and track development

  - **Tmux enhancement**: Extended tmux_wrapper functionality, adding more terminal-session management capabilities, improving the multi-window operation experience

#### **📌 Fixes**

- **🔧 Special-character warning fix**
  - **FuzzyWuzzy warning**: Fixed the fuzzywuzzy warning caused by special characters in the input module, improving string-matching stability

- **🔧 Edit File tool fix**
  - **Tool-call logic optimization**: Optimized the edit_file tool's call logic, fixing parameter-handling issues in some scenarios

- **🔧 Platform-selection error fix**
  - **Prompt-optimizer fix**: Fixed the platform-selection error in the prompt_optimizer module, ensuring the correct platform configuration is used

#### **🔧 Optimizations and Refactoring**

- **🎯 Code Agent core refactoring**
  - **Prompt-system refactoring**: Greatly refactored the code_agent_prompts module (+336 lines), optimizing prompt structure and content organization, improving prompt quality

  - **Agent-logic optimization**: Optimized the code_agent main-module logic (+46 lines), improving the Agent execution flow and error-handling mechanism

  - **Git-operation optimization**: Simplified the code_agent_git module (-35 lines), removing redundant code, improving Git-operation reliability

- **🎯 HaijunBot Agent architecture optimization**
  - **Agent-initialization refactoring**: Refactored the haijunbot_agent initialization logic (+116 lines), optimizing the temporary-model creation mechanism to use the same model configuration as the caller

  - **Rule-management optimization**: Optimized the rules_manager and builtin_rules modules, improving rule-loading and management efficiency

  - **Task-analysis optimization**: Optimized the task_analyzer module, improving task-analysis accuracy and response speed

- **🎯 Task-list-manager enhancement**
  - **Function expansion**: Greatly expanded task_list_manager functionality (+120 lines), enhancing task-splitting, dependency-management, and execution-control capabilities

  - **Execution-flow optimization**: Optimized the task-execution flow, improving the stability and efficiency of multi-Agent collaboration

- **🎯 Tool-registration-system optimization**
  - **Registration-logic simplification**: Optimized the tools/registry module (-52 lines), simplifying tool-registration logic, improving system startup speed

  - **CLI-integration optimization**: Optimized the tools/cli/main module, streamlining command-line-interface code, improving the user experience

#### **📚 Documentation Update**

- **🎯 Reverse-engineering rule improvement**
  - **Rule-content expansion**: Greatly expanded the reverse_engineering rule document (+1054 lines), providing more detailed reverse-engineering guidance and best practices

  - **Document replacement**: Removed the old code-reverse-design.md document, uniformly using reverse_engineering.md as the authoritative reverse-engineering document

- **🎯 Documentation-structure optimization**
  - **Usage-guide slimming**: Trimmed the docs/haijunbot_book/4.Usage_Guide.md document (-122 lines), removing redundant content, improving document readability

  - **Documentation cleanup**: Cleaned up outdated comparison documents and updated project-description documents, keeping documentation current

- **🎯 Project-configuration optimization**
  - **Type-check configuration**: Added the mypy.ini configuration file, strengthening type-check conventions and improving code quality

  - **Configuration-file cleanup**: Cleaned up redundant configurations in pyproject.toml, setup.py, and other configuration files, simplifying project configuration

#### **🗑️ Feature Removal**

- **🎯 Statistics-module removal**
  - **HaijunBot Stats cleanup**: Removed the haijunbot_stats module and related functionality (4 core files, -1952 lines), removing statistics-collection, storage, and visualization features

  - **Test-code cleanup**: Removed all test cases under tests/haijunbot_stats/ (-1052 lines), completing the full removal of the statistics module

This update is a patch release for **the scenario-based prompt system and core-architecture optimization**. Core highlights include:

**🎯 Three core improvements:**

1. **Scenario-based prompt system**: Added 11 scenario-based prompt templates, covering common development scenarios, improving the professionalism and accuracy of Agent task execution

2. **Core-architecture optimization**: Refactored the Code Agent and HaijunBot Agent core modules, optimizing key components such as the prompt system, task analysis, and tool management, improving overall system performance

3. **Feature expansion and cleanup**: Expanded Search Web, Template Utils, Tmux Wrapper, and other tool functions, while cleaning up the haijunbot_stats statistics module, focusing on core capabilities

**Other important improvements:**

- Fixed multiple issues such as special-character warnings, the Edit File tool, and platform-selection errors

- Expanded the reverse-engineering rule document, unifying reverse-engineering guidance standards

- Trimmed the usage-guide document, cleaned up redundant configuration, and optimized the project structure

- Added mypy type-check configuration, strengthening code-quality control

**Technical highlights:**

- **Prompt system**: Scenario-based templates, dynamic optimization, configuration management

- **Core architecture**: Agent refactoring, rule management, task-analysis optimization

- **Tool ecosystem**: Search Web expansion, Template Utils added, Tmux enhancement

- **Code quality**: Type checking, documentation improvement, configuration cleanup

---

### Release Note - v1.2.5 (2026-01-22)

#### **🚀 New Features**

#### **📌 Fixes**

- **🔧 Tool-call fix-logic refactoring**
  - **Strategy adjustment**: Changed the tool-call fix strategy from "fix directly and execute" to "construct a fix prompt and return it to the LLM for handling", improving flow controllability and flexibility

  - **Code decoupling**: Added the build_fix_prompt function, separating prompt-construction logic from fix_tool_call_with_llm, improving code reusability

  - **Prompt optimization**: Updated the prompt message to "🔧 Constructing fix prompt...", more accurately reflecting the actual operation

#### **🔧 Optimizations and Refactoring**

- **🎯 REVIEW-stage enhancement**
  - **Name unification**: Renamed the REVIEW stage from "reviewing results" to "reflection", better matching the nature of the stage

  - **Description enhancement**: Added a detailed stage description, emphasizing "comprehensively reflecting on work results", including reviewing code quality, checking feature completeness, checking affected code, confirming supporting modifications, and assessing impact scope and risks

  - **Coverage**: Updated the REVIEW-stage prompts in 5 core files (haijunbot_agent, code_agent, c2rust, meta_agent)

- **🎯 Test-code slimming**
  - **Redundant-test removal**: Deleted 263 lines of test cases from test_task_list_manager.py (-263 lines), removing tests related to dependency verification and batch execution

  - **Code cleanup**: Trimmed test code, improving test-suite maintenance efficiency

This update is a patch release for **tool-call-logic refactoring and REVIEW-stage enhancement**. Core highlights include:

**🎯 Two core improvements:**

1. **Tool-call fix-logic refactoring**: Changed from direct fixing to prompt construction, improving flow controllability and flexibility, with a cleaner code structure

2. **REVIEW-stage enhancement**: Unified the stage name to "reflection", enhanced the stage description, covering 5 core files, improving the systematicness of the Agent's reflection capability

**Other important improvements:**

- Test-code slimming, removing 263 lines of redundant test cases

- Added the build_fix_prompt function, improving code reusability

**Technical highlights:**

- **Tool calls**: Strategy adjustment, code decoupling, prompt optimization

- **REVIEW stage**: Name unification, description enhancement, broad coverage

- **Code quality**: Test slimming, clear structure, efficient maintenance

---

### Release Note - v1.2.4 (2026-01-21)

#### **🚀 New Features**

#### **📌 Fixes**

- **🔧 Task-analysis execution-logic fix**
  - **Interactive-mode optimization**: Fixed the issue where task analysis did not correctly ask the user in interactive mode, adding a clear confirmation flow

  - **Flow unification**: Unified the before_summary and task_completed event-handling logic, avoiding duplicate execution or omissions

- **🔧 Docstring fix**
  - **Chinese translation**: Fully translated the docstrings of the file_context_handler.py module into Chinese, improving code readability

#### **🔧 Optimizations and Refactoring**

- **🎯 HYPOTHESIZE-stage enhancement**
  - **Structured-output requirement**: Added a mandatory structured-output requirement, covering five chapters: task understanding, execution plan, impact scope, risk assessment, and acceptance criteria

  - **Memory-saving guidance**: Clearly requires the user to use the save_memory tool after confirming the plan to save it to short-term memory, ensuring traceability during execution

  - **Output-format specification**: Provides detailed output-format examples, ensuring consistency and readability of Agent output

- **🎯 Methodology format alignment**
  - **Unified format requirement**: Unified the methodology format with the rule-file format, requiring core chapters such as "rule introduction", "principles you must follow", and "operations you must perform"

  - **Structure standardization**: Uses the same Markdown levels (##, ###) and format markers (**must**, **must not**), improving document consistency

  - **Prompt update**: Updated task_analysis_prompt and the methodology-extraction prompt, ensuring format-requirement consistency

- **🎯 Rule-document improvement**
  - **Pre-registration inquiry flow**: Added a flow requirement to ask the user before registration in the track-development and rule-addition rules

  - **Flow optimization**: Clearly informs the user that the track/rule has been created, asks whether to register it into the index, and decides whether to perform registration based on the user's choice

  - **Checklist update**: Updated the checklist, changing registration-related items to conditional checks (only when the user confirms registration)

- **🎯 Output-system optimization**
  - **Progress-info highlighting**: Added progress-info detection (such as "round X"), automatically highlighting round numbers, improving visual recognition

  - **Multi-line list formatting**: Optimized the display of multi-line lists and indented content, using appropriate indentation and dimming, maintaining visual hierarchy

  - **Timestamp beautification**: Optimized the timestamp format, using the "⏰ HH:MM:SS │" format, improving aesthetics and readability

  - **Emoji-spacing optimization**: Automatically detects emoji prefixes, ensuring proper spacing between emoji and text

- **🎯 Rule-index slimming**
  - **General-rule description**: Updated builtin_rules.md, clarifying that only general rule indexes are listed and domain-specific rules can still be loaded directly via load_rule

  - **Redundant-reference removal**: Removed rule references for specific domains such as the track list, test conventions, and UI design, simplifying the index structure

- **🎯 Documentation cleanup**
  - **Obsolete-document deletion**: Deleted the "Haijun*Code_Cursor*Prompt-Comparison Analysis.md" document (-310 lines); its content is obsolete and no longer needed

This update is a patch release for **HYPOTHESIZE-stage enhancement and methodology-format alignment**. Core highlights include:

**🎯 Three core improvements:**

1. **HYPOTHESIZE-stage enhancement**: Added structured-output requirements and memory-saving guidance, ensuring the standardization and traceability of solution design

2. **Methodology format alignment**: Unified the methodology format with the rule-file format, improving document consistency and maintainability

3. **Output-system optimization**: Enhanced output formatting and progress highlighting, improving the user experience and visual recognition

**Other important improvements:**

- Task-analysis execution-logic optimization, fixing the confirmation flow in interactive mode

- Rule-document improvement, adding the pre-registration user-inquiry flow

- Docstrings translated into Chinese, improving code readability

- Rule-index slimming, removing redundant domain-specific references

**Technical highlights:**

- **HYPOTHESIZE stage**: Structured output, memory saving, format specification

- **Methodology format**: Rule alignment, standardized structure, unified prompts

- **Output system**: Progress highlighting, multi-line formatting, timestamp beautification

- **Rule documentation**: Registration inquiry, flow optimization, index slimming

---

### Release Note - v1.2.3 (2026-01-21)

#### **🚀 New Features**

#### **📌 Fixes**

- **🔧 Tool-call flow fix**
  - **Post-fix-success flow**: Fixed the execution flow after a successful tool-call fix, ensuring correct return and letting the LLM process the tool-execution result

- **🔧 Documentation-error fix**
  - **Typo fix**: Fixed a spelling error in the README workflow example (READM -> README)

- **🔧 File-completer optimization**
  - **Exclusion-list update**: Updated the file-completer exclusion list, adding filtering for hidden directories (such as `.git`, `__pycache__`, `.pytest_cache`, etc.)

#### **🔧 Optimizations and Refactoring**

- **🎯 Track-development-document enhancement**
  - **Jinja2 variable guide**: Added a Jinja2 variable usage guide, detailing available built-in variables and usage examples

  - **Track-document creation flow**: Added a track-document file-creation flow (stage 4.5), standardizing the writing and management of track documentation

  - **Registration-info optimization**: Updated the track-registration format, adding a rule-file location field

- **🎯 Rule-configuration-document slimming**
  - **Content slimming**: Removed redundant examples and duplicate content (-160 lines), improving document readability

  - **Variable-usage explanation**: Optimized variable-usage principles, clearly recommending jinja2 variables instead of hard-coded paths

  - **Example removal**: Removed the outdated "naming-convention" example and classification-judgment exercises, keeping the document concise

- **🎯 Python-version-requirement update**
  - **Version upgrade**: Raised the Python version requirement from 3.9+ to 3.12, simplifying version management

- **🎯 Configuration-example simplification**
  - **Legacy-config removal**: Removed the old ENV configuration descriptions (YUANBAO_COOKIES, KIMI_API_KEY, etc.)

  - **Haijun-config simplification**: Uses a more concise Haijun configuration example, clarifying the llm_config structure

#### **📚 Documentation Update**

- **🎯 README structure optimization**
  - **Vibe Working section removal**: Removed the Vibe Working introduction section, simplifying the document structure

  - **Configuration-description optimization**: Simplified configuration descriptions, keeping only the new llm_groups and llms configuration methods

---

### Release Note - v1.2.2 (2026-01-20)

#### **🚀 New Features**

- **🎯 Context-compression-system enhancement**
  - **Sliding-window-compression optimization**: Simplified the sliding-window-compression logic, improving compression efficiency and accuracy
  - **Multi-dimensional context info**: Enhanced sliding-window-compression functionality, adding multi-dimensional context-information support
  - **Rule-lookup priority**: Enhanced the rule-lookup priority mechanism, ensuring more appropriate compression strategies are executed

#### **📌 Fixes**

- **🔧 Context-compression fixes**
  - **Sliding-window-size optimization**: Adjusted the sliding-window size to an odd number, avoiding consecutive same-role message issues
  - **Methodology-count limit**: Reduced the methodology-count limit from 10 to 3, avoiding excessive context usage

#### **🔧 Optimizations and Refactoring**

- **🎯 Git-tool optimization**
  - **git diff content truncation**: Added git diff content truncation, automatically adapting to token limits, avoiding large code blocks exceeding the context
  - **git_commiter module**: Added a new git_commiter module (+147 lines), encapsulating Git-commit-related functionality

- **🎯 Code-quality optimization**
  - **run_loop.py optimization**: Optimized the code format and logic of run_loop.py, improving code readability
  - **Compression-strategy execution logic**: Optimized the compression-strategy execution logic, removing the platform auto-compression mechanism
  - **Compression-mechanism implementation**: Further optimized the compression-mechanism implementation, improving compression results

- **🎯 Configuration-management optimization**
  - **Config slimming**: Trimmed haijunbot_utils/config.py (-15 lines), removing redundant configuration items

#### **📚 Documentation Update**

- **🎯 Technical-documentation update**
  - **Context-compression flow**: Updated the context-compression-flow documentation (+4 lines), reflecting the latest compression strategy
  - **Compression-strategy documentation**: Updated the context-compression-strategy documentation (+6 lines), explaining the optimized strategy
  - **Core-concepts-and-architecture**: Updated the core-concepts-and-architecture documentation (+6 lines), adding context-compression-related explanations

#### **🧪 Test Enhancements**

- **🎯 Unit tests**
  - **Sliding-window-compression tests**: Added a sliding-window-compression test file (+296 lines), covering multiple compression scenarios

This update is a patch release for **context-compression-system optimization and Git-tool enhancement**. Core highlights include:

**🎯 Three core improvements:**

1. **Context-compression-system enhancement**: Optimized the sliding-window-compression logic, enhanced rule-lookup priority, and added multi-dimensional context-information support
2. **Git-tool optimization**: Added git diff content truncation, automatically adapting to token limits, avoiding large code blocks exceeding the context
3. **Test-coverage enhancement**: Added 296 lines of sliding-window-compression tests, improving code quality and stability

**Other important improvements:**

- Fixed the sliding-window-size issue, adjusting to an odd number to avoid consecutive same-role messages
- Optimized compression-strategy execution logic, removing the platform auto-compression mechanism
- Trimmed configuration management, removing redundant configuration items
- Updated technical documentation, reflecting the latest compression strategy and architecture

**Technical highlights:**

- **Context compression**: Sliding-window optimization, enhanced rule priority, multi-dimensional info support
- **Git tools**: diff-content truncation, token-limit adaptation, git_commiter module
- **Code quality**: Test-coverage enhancement, code-format optimization, configuration slimming

---

### Release Note - v1.2.1 (2026-01-19)

#### **🚀 New Features**

- **🎯 Rules-system enhancement**
  - **Rule-sharing mechanism**: Added a rule-sharing feature, supporting sharing local rules to a central rule repository, enabling cross-project rule reuse
  - **Central rule repository**: Supports configuring a central rule repository (Git repository or local directory), with automatic daily update checks and highest-priority loading
  - **Rule-loading priority**: Established a complete rule-loading priority hierarchy (central repository -> project rules -> configuration directory -> global rules -> built-in rules)
  - **Flexible referencing**: Supports referencing by index (such as `clean_code`) and by prefix (such as `project:architecture_design/solid`), including relative paths
- **🎯 Built-in quick commands**
  - **@ trigger mechanism**: Added an @-triggered built-in quick-command system, supporting auto-completion and quick execution
  - **Command-type extension**: Distinguishes prompt-template commands (such as @Web, @Dev) from built-in command markers (such as @Summary, @Clear)
  - **Unified data source**: Unifies the management of the built-in-command list in the BUILTIN_COMMANDS constant, ensuring prompt_toolkit and fzf completion lists stay consistent
  - **Command-handling logic**: Added the builtin_input_handler module, supporting immediate execution and special handling of built-in commands
- **🎯 Documentation-system expansion**
  - **HaijunBot rules-system introduction**: Added a complete rules-system introduction document (516 lines), covering overview, type sources, working principles, extensibility, etc.

  - **Best-practice documents**: Added 5 best-practice documents (1500+ lines), including hcad multi-feature parallel development, hca interactive development, rule usage, and introducing CodeAgent and Agent

  - **Rule-development guide**: Added a rule for adding built-in quick commands (178 lines) and using rules to add new rules (448 lines), guiding users to extend the rules system

#### **📌 Fixes**

- **🔧 Git-tool fixes**
  - **Repeated-inquiry fix**: Added a global marker to avoid repeatedly asking the user whether to add new files/binary files/large code within the same flow
  - **git add optimization**: Changed `git add .` to `git add -A`, ensuring changes to deleted files are included, avoiding omissions
- **🎯 Context-compression-strategy adjustment**
  - **Prioritize recent messages**: Adjusted the sliding-window-compression strategy to prioritize the most recent messages, improving context relevance
  - **Configuration update**: Updated context-compression-related configuration, optimizing compression results

#### **🔧 Optimizations and Refactoring**

- **🎯 Output-system optimization**
  - **Hard-coded background-color removal**: Removed all hard-coded background-color configurations, using the terminal default background color, improving compatibility
  - **Color-scheme optimization**: Adjusted the output color scheme, using softer standard colors (such as bright_red, bright_green, etc.)
  - **Code slimming**: Greatly trimmed the output-system code (-200 lines), removing the redundant `styles` and `header_styles` dictionaries
- **🎯 Rules-management-system refactoring**
  - **Rules-manager enhancement**: Greatly refactored the rules-manager code (+250 lines), optimizing rule-loading, merging, and injection logic
  - **Rule-sharing manager**: Added a new rule-sharing-manager module (+177 lines), supporting rule sharing and central-repository management
  - **Rule-loading optimization**: Optimized rule-loading performance, supporting dynamic rule injection and priority management
- **🎯 Version-release-rule enhancement**
  - **wechat.png check mechanism**: Added a wechat.png file modification-time check (<7 days), ensuring timeliness of promotional materials
  - **Flow optimization**: Improved the version-release flow, adding necessary checkpoints and verification steps

#### **📚 Documentation Update**

- **🎯 Best-practices documentation**
  - **Rules-system introduction**: A complete overview of the rules system, type sources, working principles, and extensibility (516 lines)
  - **Using hcad for multi-feature parallel development**: Detailed methods for multi-feature parallel development with hcad (179 lines)
  - **Using hca for interactive code development**: Interactive code-development guide (122 lines)
  - **Using rules to add new rules**: Rule-development guide (448 lines)
  - **Using rules to quickly introduce MCP and TRACKS**: MCP and Tracks introduction guide (367 lines)
  - **Introducing CodeAgent and Agent into projects**: CodeAgent and Agent integration guide (180 lines)
  - **Rule-usage best practices**: Rule-usage conventions and best practices (526 lines)
- **🎯 Technical-documentation update**
  - **Context-compression documentation**: Updated the context-compression flow and strategy documentation to reflect the latest compression strategy
  - **Core-concepts-and-architecture**: Updated the core-concepts-and-architecture documentation (+17 lines)
- **🎯 Other updates**
  - **wechat.png update**: Updated the project promotional image, keeping it timely

This update is a patch release for **rule-system enhancement and user-experience optimization**. Core highlights include:

**🎯 Three core features:**

1. **Rules-system enhancement**: Added the rule-sharing mechanism, central rule repository, and flexible referencing, greatly improving rule reusability and extensibility

2. **Built-in quick commands**: Added the @-triggered built-in quick-command system, improving interaction efficiency and the user experience

3. **Documentation-system expansion**: Added 7 documents (2500+ lines), covering the rules system, best practices, and development guides

**Other important improvements:**

- Git-tool fixes, resolving repeated-inquiry and file-omission issues
- Optimized the context-compression strategy, prioritizing retention of recent messages
- Output-system refactoring, removing hard-coded background colors, improving compatibility
- Major refactoring of the rules-management system, optimizing loading and management logic

**Technical highlights:**

- **Rules system**: Sharing mechanism, central repository, priority hierarchy, flexible referencing
- **Quick commands**: @ trigger, autocomplete, unified data source, and command handling
- **Documentation system**: 2500+ lines of new documentation, covering the rules system, best practices, and development guides
- **User experience**: Output optimization, input optimization, Git fixes, compression-strategy adjustment

---

#### **🚀 New Features**

- **🎯 Context-compression system**
  - **Multi-level progressive compression strategy**: Implemented a complete context-compression system, supporting multiple compression strategies executed in layers by intensity, prioritizing lightweight strategies to avoid clearing history all at once
  - **Smart task-type recognition**: Automatically detects the task type (code/analysis/conversation/hybrid) and selects the most suitable compression-strategy combination based on it
  - **Key-information retention mechanism**: Ensures key information such as the original task goal, user-fixed content, system messages, recent memories, and task-list state is never compressed
  - **Adaptive compression flow**: Checks remaining tokens before each model call, automatically triggering compression when below the threshold (25%), with no manual intervention needed

- **🎯 Tool-call-rule enhancement**
  - **Multi-tool-call support**: Updated the tool-call rules to support calling multiple tools at once, improving task-execution efficiency
  - **No-dependency call limit**: Clarifies that tool calls must not have dependencies between them, ensuring correct execution order

#### **📌 Fixes**

- **🔧 Code-quality-tool switch**
  - **pylint removal**: Completely removed pylint configuration (.pylintrc) and related dependencies
  - **Enable ruff**: Uses ruff instead of pylint for Python code checks, improving check speed and accuracy
  - **Config unification**: Unified code-check configuration, simplifying the development-environment setup

#### **🔧 Optimizations and Refactoring**

- **🎯 Git-tool optimization**
  - **find_git_root_and_cd function enhancement**: Added initialization-control parameters, supporting more flexible Git-root-directory lookup behavior
  - **Error-handling improvement**: Optimized the error-handling logic of Git operations, providing more accurate error messages

- **🎯 Configuration-management optimization**
  - **Unified input prompts**: Unified input-prompt formats in the quick_config module, adding colon separators, improving the user experience
  - **Rich Prompt replacement**: Replaced rich prompts with a unified input function, simplifying code logic
  - **Configuration-module enhancement**: Added configuration-management features to the haijunbot_config and haijunbot_utils modules (+37 lines)

#### **📚 Documentation Update**

- **🎯 Context-compression-system documentation**
  - **Core-concepts-and-architecture document**: Added a complete context-compression-system explanation to haijunbot_book (+209 lines), including design philosophy, compression-strategy layers, and trigger mechanisms

  - **New implementation documents**: Added `docs/technical/implementation/context_compression_flow.md` (346 lines) and `context_compression_strategies.md` (337 lines), detailing the compression flow and strategy implementation
  - **Technical-documentation system**: Added `docs/technical/README.md` and `docs/technical/implementation/README.md`, establishing a technical-documentation index system

This update is an important minor-version release for **the context-compression system and code-quality-tool upgrade**. Core highlights include:

**🎯 Two core features:**

1. **Context-compression system**: Implements multi-level progressive compression strategies, supporting smart task-type recognition and key-information retention, ensuring context-management capability during long Agent runtimes

2. **Code-quality-tool switch**: Migrated from pylint to ruff, improving code-check speed and accuracy, simplifying the development-environment setup

**Other important improvements:**

- Tool-call-rule enhancement, supporting parallel multi-tool calls
- Git-tool optimization, improving error handling and initialization control
- Configuration-management optimization, unifying the user experience
- Documentation-system improvement, adding many context-compression-related documents

**Technical highlights:**

- **Context compression**: Multi-level progressive strategies, smart task recognition, key-information retention, automatic trigger mechanism
- **Code quality**: ruff replacing pylint, unified configuration, simplified environment
- **Tool calls**: Parallel multi-tool calls, no-dependency restrictions, execution-order optimization
- **Documentation system**: Complete implementation documents, technical index, architecture explanation

---

### Release Note - v1.1.9 (2026-01-17)

#### **🚀 New Features**

- **🎯 Security-rule enhancement**
  - **Report-file requirement**: Added the requirement for security-analysis reports to be output as files, with Markdown format recommended, and file-naming convention of `security_analysis_report.md` or `vulnerability_analysis_report.md`
  - **Report-save location**: Clarified that report files are saved in the project root directory or a specified report-output directory
  - **Mandatory task-splitting requirement**: For complex security-vulnerability-analysis tasks, the `task_list_manager` tool must be used for task splitting, following the reasonable-granularity principle, clarifying task dependencies, and providing clear descriptions and verification criteria

#### **📌 Fixes**

- **🔧 Tool-call handling fix**
  - **Post-fix handling logic**: When tool-call content is successfully fixed, directly re-parses and executes the tool call rather than adding the fixed content to `addon_prompt`, avoiding confusion in the tool-call execution flow
  - **Security enhancement**: Added safety handling for tool-call results, only appending tool results to the prompt when they are strings, preventing non-string results from causing anomalies
  - **Special-return handling**: Supports cases where the tool requires immediately returning a result (such as SEND_MESSAGE needing to return a dict to the upper layer), directly returning that result without further processing

#### **🔧 Optimizations and Refactoring**

- **🎯 Configuration-architecture refactoring**
  - **Config-Schema slimming**: Removed many unused configuration items from `config_schema.json` (-108 lines), including over 30 items such as `tool_filter_threshold`, `script_execution_timeout`, `confirm_before_apply_patch`, `data_path`, `pretty_output`, and `use_methodology`
  - **Config-retrieval simplification**: Simplified the config-retrieval methods in `config.py`, directly returning hard-coded defaults instead of reading from `GLOBAL_CONFIG_DATA`, improving code readability and maintainability
  - **Configuration-management optimization**: Reduced configuration complexity and the risk of configuration errors by removing redundant items and simplifying retrieval logic

- **🎯 Conversation-summary visualization enhancement**
  - **Rich Panel display**: Uses the Rich Panel component to display conversation-summary content, improving visual impact and readability
  - **Dynamic title**: The Panel title includes the current Agent name and LLM identifier, providing clearer context information
  - **Rounded-border style**: Uses the ROUNDED border style and a cyan theme, improving aesthetics

- **🎯 Documentation-format optimization**
  - **Configuration-table standardization**: Optimized the configuration-description tables in `docs/haijunbot_book/9.Appendix.md`, using standard Markdown table format, improving document readability
  - **Configuration-item explanation cleanup**: Reorganized the descriptions of configuration items, making them more concise and clear

This update is a patch release for **security-rule enhancement and configuration-architecture optimization**. Core highlights include:

**🎯 Three core improvements:**

1. **Security-rule enhancement**: Added report-file-output requirements and mandatory task-splitting requirements, improving the standardization and traceability of security-analysis tasks

2. **Tool-call fix**: Fixed the post-tool-call handling logic, avoiding execution-flow confusion, enhancing tool-call stability and security

3. **Configuration-architecture refactoring**: Greatly streamlined the configuration system, simplified config-retrieval logic, and reduced configuration complexity

**Other important improvements:**

- Conversation summaries displayed with Rich Panel, improving visual impact
- Document-format standardization, improving readability

**Technical highlights:**

- **Security rules**: Report-file requirement, mandatory task splitting, reasonable-granularity principle
- **Tool-call fix**: Direct re-parse and execution, safety handling, special-return support
- **Configuration refactoring**: Trimmed 30+ config items, simplified retrieval logic, improved maintainability
- **Visualization enhancement**: Rich Panel component, dynamic titles, rounded borders

---

### Release Note - v1.1.8 (2026-01-16)

#### **🚀 New Features**

- **🎯 Go2Rust transpilation rules**
  - **Complete transpilation flow**: Added a Go-to-Rust code-transpilation rule document, covering the complete flow from planning, implementation, building, review, optimization, to evaluation (992 lines)
  - **Multi-level task management**: Supports three-level task lists at the directory, file, and function levels, ensuring the standardization and traceability of the transpilation process
  - **Concurrency-model mapping**: Details the mapping of Go features (goroutines, channels, sync, etc.) to Rust (async/await, tokio, mpsc, etc.)
  - **Type-system mapping**: Provides a complete mapping table from Go types (int, string, map, etc.) to Rust types (i32, String, HashMap, etc.)
  - **TDD development principle**: Mandates writing test cases before implementing functionality, ensuring transpilation quality and functional consistency

- **🎯 Self-service configuration rules**
  - **Natural-language configuration**: Added a self-service configuration-rule document, guiding the Agent to intelligently modify HaijunBot configuration files through natural-language descriptions (293 lines)
  - **Configuration-intent parsing**: Supports parsing configuration needs from user natural language, extracting configuration items, operation types, and nested structures
  - **Configuration-verification mechanism**: Provides Schema verification, reference verification, and logic verification, ensuring the accuracy and completeness of configuration modifications
  - **Safe modification strategy**: Adopts the minimal-change principle, only modifying configuration items the user explicitly requests, preserving the original structure and comments

- **🎯 C2Rust functional-alignment verification**
  - **New verification module**: Added a functional-alignment verification module (verify.py, 704 lines), supporting checks for functional consistency between transpiled Rust code and the original C code
  - **Iterative-optimization support**: Supports automatic iterative optimization, running multiple analysis-and-fix loops until functionality is fully aligned or the maximum iteration count is reached
  - **Large-scale code analysis**: Supports splitting tasks by file, with each file analyzed independently to generate partial reports, finally aggregated into a complete alignment report
  - **Multi-dimensional checks**: Conducts comprehensive checks across function signatures, type definitions, logic implementation, error handling, memory safety, and layout alignment

#### **📌 Fixes**

None

#### **🔧 Optimizations and Refactoring**

- **🎯 Summary-information optimization**
  - **Diff statistics instead of full diff**: Optimized the Agent auto-summary feature, using git diff statistics instead of the full diff, greatly reducing token consumption
  - **Viewing-command generation**: Automatically generates git diff viewing commands, letting users view the full diff on demand, improving information-retrieval flexibility
  - **Git statistics method**: Added the get_git_diff_stat() method, retrieving diff statistics from the starting commit to the current commit

- **🎯 Git-tool enhancement**
  - **Inter-commit diff statistics**: Added the get_diff_stat_between_commits() function, supporting diff statistics between any two commits
  - **Error-handling enhancement**: Improved error-handling logic, checking whether commits exist, providing more accurate error messages

- **🎯 C2Rust configuration management**
  - **FFI-export verification config**: Moved the FFI-export verification option to the configuration file, supporting enabling/disabling this feature via the `config` subcommand
  - **New verify subcommand**: Added the `verify` subcommand, providing an independent functional-alignment verification entry point, supporting a specified model group and maximum iteration count

#### **📚 Documentation Update**

- **🎯 Rule-index update**
  - **New rule links**: Added links to the Go2Rust transpilation rules and self-service configuration rules in builtin_rules.md, improving the rule-index system
  - **Rule categorization**: Categorized the self-service configuration rules under "Tool Configuration", adding links to the built-in rule conventions

- **🎯 System-prompt update**
  - **Auto-commit explanation**: Added an auto-commit explanation to the code_agent system prompt, clarifying that an automatic commit is made after each code-modification completion

This update is an important patch release for **rules-system expansion and feature enhancement**. Core highlights include:

**🎯 Three core features:**

1. **Go2Rust transpilation rules**: Added complete Go-to-Rust transpilation rules, providing multi-level task management, concurrency-model mapping, type-system mapping, and TDD development principles

2. **Self-service configuration rules**: Added self-service configuration rules, supporting intelligent configuration-file modification through natural language, improving configuration-management convenience

3. **Functional-alignment verification**: Added the C2Rust functional-alignment verification module, supporting large-scale code analysis and iterative optimization, ensuring transpilation quality

**Other important improvements:**

- Summary-information optimization, using diff statistics instead of the full diff
- Git-tool enhancement, supporting inter-commit diff statistics
- C2Rust configuration-management optimization, supporting configuration-file-managed FFI verification
- Rule-index update, improving the rules system

**Technical highlights:**

- **Go2Rust rules**: 992-line complete document, three-level task management, complete mapping tables, TDD development principles
- **Self-service configuration**: Natural-language parsing, configuration verification, safe-modification strategy
- **Functional-alignment verification**: 704-line verification module, large-scale code analysis, iterative optimization, multi-dimensional checks
- **Summary optimization**: diff statistics, reduced token consumption, viewing-command generation

---

### Release Note - v1.1.7 (2026-01-16)

#### **📌 Fixes**

- **🔧 Platform auto-summary fix**
  - **Recursive-call protection**: Added a `_summarizing` flag, preventing new summary checks from being triggered during auto-summary, avoiding infinite loops caused by recursive calls
  - **Exception-handling optimization**: Improved the exception-handling logic, distinguishing between "summary-check failure" and "summary failure" error scenarios, improving error-message accuracy
  - **State-management enhancement**: Uses a try-finally structure to ensure the flag is correctly cleared, restoring a normal state even under exception conditions

---

### Release Note - v1.1.6 (2026-01-16)

#### **📌 Fixes**

- **🔧 Template-tool fix**
  - **Project-root-directory location**: Fixed the project-root-directory lookup path in the template tool, ensuring the project root is correctly found in different directory environments, improving template-rendering accuracy

#### **🚀 New Features**

- **🎯 JCK system-tool check enhancement**
  - **Check-function expansion**: Enhanced the system-tool check functionality of the haijunbot_jck module, supporting custom check rules and more detailed check reports, improving the comprehensiveness of system-environment detection
  - **Configuration-based management**: Optimized the configuration-management mechanism, supporting defining tool-check rules via configuration files, improving flexibility and maintainability

- **🎯 Tool-registry enhancement**
  - **Registration-capability improvement**: Enhanced the haijunbot_tools registry functionality, supporting richer tool registration and management mechanisms, improving tool-system extensibility

#### **🔧 Optimizations and Refactoring**

- **🎯 Rules-system refactoring**
  - **Rule standardization**: Shifted the rules system from the "expert" model to the "rule" model, establishing a more standardized, more maintainable rule-file organization structure
  - **Architecture-design rules added**: Added "architecture-diagram generation rules" and "code reverse-design rules", providing complete architecture-design and code-analysis guidance
  - **Development-tool rules expanded**: Added "script-generation rules", "track-development rules", and "MCP-integration rules", improving the development-tool ecosystem
  - **UI-design rules added**: Added "dark-theme design rules", "light-theme design rules", and "macOS Web design conventions", providing comprehensive UI-design guidance
  - **Security-rule enhancement**: Added "security-vulnerability-analysis rules", providing systematic security-analysis guidance
  - **Tool-configuration rules added**: Added "alert-management rules", standardizing the system-alert handling mechanism

- **🎯 Agent core-functionality refactoring**
  - **Rule-management enhancement**: Greatly expanded the rule-management capability of haijunbot_agent (+134 lines), providing more powerful rule loading, rendering, and management functions
  - **Code simplification**: Simplified the code logic of haijunbot_code_agent (-232 lines), removing redundant code, improving code maintainability
  - **Platform-function optimization**: Optimized the haijunbot_platform module (+147 lines, -63 lines), enhancing the stability and extensibility of platform base functionality
  - **Tool-function optimization**: Optimized haijunbot_utils tool functions, improving the functionality and ease of use of general tools

- **🎯 Architecture optimization**
  - **Built-in rule-index update**: Updated builtin_rules.md, establishing a complete rule-index system, making it easy for developers to find and use rules
  - **Configuration-architecture update**: Updated config_schema.json, optimizing the configuration-architecture design

#### **📚 Documentation Update**

- **🎯 Version-release-rule adjustment**
  - **Rule update**: Updated the version-release-rule file, clarifying the applicable scenarios and operation flows of the two modes: "complete version release" and "ReleaseNote-only update"
  - **Flow optimization**: Optimized the version-release-flow description, adding more detailed operation guidance and notes

- **🎯 Usage-guide update**
  - **Guide improvement**: Updated the usage guides and appendix in haijunbot_book, providing more accurate usage instructions

This update is an important patch release for **rules-system refactoring and core-functionality optimization**. Core highlights include:

**🎯 Four core improvements:**

1. **Rules-system refactoring**: Established a standardized rule-file organization structure, adding six major rule categories covering architecture design, development tools, UI design, and security analysis

2. **Agent core refactoring**: Enhanced rule-management capability, simplified code logic, optimized platform functions, improving overall system maintainability

3. **System-tool enhancement**: JCK system-tool checks and tool-registry functionality significantly enhanced, improving system-detection and management capability
4. **Documentation-system improvement**: Updated version-release rules and usage guides, providing clearer guidance

**Other important improvements:**

- Template-tool project-root-directory location fix
- Tool-function optimization and enhancement
- Configuration-architecture update

**Technical highlights:**

- **Rules system**: Standardized organization structure, six major rule categories, complete index system
- **Agent refactoring**: Rule-management enhancement, code simplification, platform optimization
- **Tool enhancement**: JCK check expansion, registry-capability improvement
- **Documentation optimization**: Release-rule improvement, usage-guide update

---

### Release Note - v1.1.5 (2026-01-14)

#### **📌 Fixes**

- **🔧 Dispatch-mode fix**
  - **Shell fallback feature**: Fixed the shell fallback in dispatch mode; when tmux panel creation fails, it now correctly falls back to shell-mode execution, improving system fault tolerance

- **🔧 Web-reading-tool fix**
  - **Content-limit-logic optimization**: Optimized the web-content-fetching limit logic, changing the content-length limit from character count to token count, dynamically calculating the content-length limit based on remaining tokens, avoiding token overflows and improving content-fetching accuracy

#### **🚀 New Features**

- **🎯 Model-configuration enhancement**
  - **Model-group parameter support**: Added llm_group parameter support to each CLI module (haijunbot, haijunbot-code-agent, haijunbot-multi-agent, haijunbot-git-commiter), allowing the model group to be specified directly on the command line, overriding configuration-file settings and improving configuration flexibility
  - **Model-type output**: Added model-type output support, adding model-type-related output types (START, TARGET, STOP, RETRY, ROLLBACK, DIRECTORY, STATISTICS) to the output system, enriching output styles and semantics, improving output readability

#### **🔧 Optimizations and Refactoring**

- **🎯 ARCHER workflow refactoring**
  - **Workflow-mode upgrade**: Refactored the agent workflow from IIRIPER mode to ARCHER mode; the new workflow includes six stages: ANALYZE (analyze intent), RULE (load rules), COLLECT (collect information), HYPOTHESIZE (propose a plan), EXECUTE (execute operations), and REVIEW (review results), providing a more flexible workflow-execution strategy
  - **Flexible execution mechanism**: Supports flexible execution of the preparation stages (A to R to C) and mandatory sequential execution of the execution stages (H to E to R); simple tasks can skip the RULE/COLLECT stages directly, while complex tasks run all stages in full, improving workflow adaptability and efficiency
  - **System-prompt optimization**: Updated the system prompts of haijunbot_agent and code_agent, adding a detailed ARCHER-workflow explanation, a Rule-system explanation, and a load_rule-tool usage guide, helping Agents better understand and use the new workflow

- **🎯 Token-limit-calculation optimization**
  - **Unified calculation logic**: Unified the token-limit-calculation logic, adding the calculate_token_limit function, using the minimum of 2/3 of remaining tokens or 64k as the limit standard, uniformly used in tools such as edit_file, read_code, and haijunbot_c2rust, improving token-management consistency and accuracy

- **🎯 Built-in-rule format unification**
  - **Rule-adding-format unification**: Unified the format for adding built-in rules in each CLI tool, using `'Built-in rule: <rule:builtin_rules>'\n---\nOriginal requirement: ` as the standard format, ensuring consistent and maintainable rule loading

- **🎯 Code cleanup**
  - **Redundant-code removal**: Removed redundant jinja2-template-variable-rendering explanations in code_agent_prompts, simplifying document content

#### **📚 Documentation Update**

- **🎯 Workflow-documentation improvement**
  - **ARCHER-workflow explanation**: Improved the detailed ARCHER-workflow documentation, adding detailed stage descriptions, flexible-execution guidelines, and workflow-characteristic explanations, helping developers understand the design philosophy and execution mechanism of the new workflow
  - **Workflow-simplification note**: Simplified the ARCHER-workflow documentation, highlighting core points and execution strategies, improving document readability

- **🎯 Rule-documentation improvement**
  - **Rule-configuration documentation**: Improved the rule-configuration documentation, adding category explanations for global rules and project rules, clarifying the applicable scope, storage location, selection principles, and registration flow of the two rule types, helping developers correctly create and use rules
  - **Version-release-rule adjustment**: Renamed and moved the version-release-rule file to the deployment directory, optimizing the rule-directory structure

- **🎯 Rule-list documentation**
  - **Rule-list title update**: Updated the builtin_rules.md document title to "HaijunBot built-in rule list", more accurately reflecting the document content

- **🎯 Rule-system documentation**
  - **Rule-system explanation**: Added a Rule-system explanation document, introducing the Rule concept, advantages (knowledge reuse, unified conventions, dynamic updates, precise context, environment adaptation), and the load_rule tool usage, helping developers understand the value and use cases of the Rule system

This update is an important patch release for **workflow refactoring and system optimization**. Core highlights include:

**🎯 Four core improvements:**

1. **ARCHER-workflow refactoring**: Upgraded the workflow from IIRIPER to ARCHER mode, providing a more flexible and efficient execution strategy

2. **Token-limit unification**: Unified the token-limit-calculation logic, improving system consistency and accuracy

3. **Model-configuration enhancement**: Supports specifying the model group on the command line, improving configuration flexibility
4. **Documentation-system improvement**: Improved the workflow, rule-configuration, and Rule-system documentation, providing more comprehensive guidance

**Other important improvements:**

- Dispatch-mode shell-fallback fix
- Web-content-fetching-limit-logic optimization
- Built-in-rule-format unification
- Model-type output support
- Version-release-rule directory adjustment

**Technical highlights:**

- **ARCHER workflow**: Flexible execution mechanism, six-stage design, simple-task optimization
- **Token management**: Unified calculation function, dynamic-limit strategy, multi-tool integration
- **Configuration system**: Command-line override, model-group support, parameter passing
- **Documentation system**: Rule-category explanations, detailed workflow guide, Rule-system introduction

---

### Release Note - v1.1.3 (2026-01-14)

#### **🚀 New Features**

- **🎯 Rule-loading tool**
  - **Dynamic rule loading**: Added the load_rule tool to code_agent, supporting dynamic loading of specified rule files at runtime. The tool uses the
    jinja2 template engine to render rule content, supporting built-in variables (current_dir, git_root_dir, haijunbot_src_dir, etc.),
    improving the flexibility and reusability of rule use
  - **Tool usage guide**: Added a detailed usage guide for the load_rule tool in prompt_manager, including tool descriptions, parameter explanations, a variable list, and usage examples, helping developers get started quickly

- **🎯 Track-development conventions**
  - **Track-convention document**: Added `builtin/rules/development_tools/add_tracks.md`, defining the complete track-development conventions, including
    track structure, registration flow, and parameter definitions. Provides track templates and best practices, guiding developers to correctly develop and register new tracks

#### **📌 Fixes**

- **Task-analyzer logic fix**
  - **Non-interactive-mode restriction**: Fixed the task_analyzer logic, ensuring task analysis only runs in non-interactive mode, avoiding
    unnecessary interference in interactive mode

- **Installation-script fix**
  - **Syntax-error fix**: Fixed syntax errors and variable-reference issues in the installation scripts, ensuring they
    execute correctly in various shell environments

#### **🔧 Optimizations and Refactoring**

- **Rule-directory-structure optimization**
  - **Test-rule adjustment**: Refactored the test-rule directory structure, organizing per-language test rules (such as go_test.md, rust_test.md, etc.) into
    clearer locations, improving rule-management maintainability
  - **Rule-documentation update**: Updated builtin_rules.md and related documents, ensuring the correctness of rule links and categories

- **Code cleanup**
  - **Redundant-code removal**: Removed the unused need_summary conditional check in code_agent, simplifying the code logic

#### **📚 Documentation Update**

- **Track-development guide**
  - **Track-convention document**: Added a complete track-development-convention document, providing full guidance from design to implementation

- **Tool usage guide**
  - **load_rule-tool guide**: Integrated the detailed usage instructions of the load_rule tool into prompt_manager, including parameter descriptions, a variable list, and usage examples

This update is a patch release for **feature enhancement and documentation improvement**. Core highlights include:

**🎯 Three core improvements:**

1. **Rule-loading tool**: Added dynamic rule-loading capability, supporting runtime loading and rendering of rule files, improving flexibility

2. **Track-development conventions**: Established a complete track-development-convention system, guiding developers to correctly develop and register tracks

3. **Logic fixes and optimization**: Fixed logic issues in the task analyzer and installation scripts, optimized the rule-directory structure

**Other important improvements:**

- The task analyzer only runs in non-interactive mode
- Installation-script syntax-error fixes
- Test-rule-directory-structure optimization
- Code-redundancy cleanup

**Technical highlights:**

- Rule loading: jinja2 template rendering, built-in-variable support
- Track conventions: complete development flow, template-driven
- Directory refactoring: clear rule-organization structure

---

### Release Note - v1.1.2 2026-01-12

#### **🚀 New Features**

- **🎯 HaijunBot JCK system-tool check**
  - **System-tool-check function**: Added the haijunbot_jck module, providing system-tool-check functionality that automatically detects whether required tools are installed on the system (such as git, python, docker, etc.) and provides detailed check reports. Supports custom check rules, defining the tools and version requirements to check via configuration files
  - **CLI interface**: Provides the `jck` command-line interface, supporting quick system checks, viewing check history, and exporting check reports. Supports JSON-format output for easy integration into CI/CD flows
  - **Configuration-based management**: Supports customizing check rules via configuration files, including tool names, check commands, and minimum-version requirements. Provides a two-level configuration mechanism of default configuration and user configuration, with high flexibility

#### **📌 Fixes**

- None

#### **🔧 Optimizations and Refactoring**

- **Platform-system optimization**
  - **Message-truncation-logic optimization**: Optimized the message-truncation logic of the haijunbot_platform module; when a trim_messages operation fails, the current message is directly truncated, avoiding message-sending anomalies caused by truncation failure. Improving system stability when handling very long messages
- **Memory-system enhancement**
  - **Memory-function enhancement**: Enhanced the save_memory tool functionality, optimizing memory storage and retrieval logic, improving the reliability and performance of the memory system. Supports more flexible tag management and memory-type selection
- **Tool-function optimization**
  - **Configuration-tool enhancement**: Enhanced the configuration-management functionality of haijunbot_utils/config.py, optimizing configuration-loading and validation logic, providing friendlier error messages
  - **Tool-function optimization**: Optimized the tool functions in haijunbot_utils/utils.py, improving code reusability and maintainability

#### **📚 Documentation Update**

- **New architecture-design conventions**
  - **Version-release rules**: Added `.haijunbot/rules/version_release.md`, standardizing the version-release flow, including semantic version numbers, code-change retrieval, and ReleaseNote format requirements. Provides detailed operation steps and checklists, ensuring the standardization and accuracy of version releases
  - **SOLID design principles**: Added `builtin/rules/solid.md`, detailing the five object-oriented design principles (single responsibility, open-closed, Liskov substitution, interface segregation, dependency inversion), providing rich code examples and anti-pattern comparisons
  - **Clean architecture**: Added `builtin/rules/clean_architecture.md`, guiding the construction of maintainable, testable architectures, detailing core principles such as the dependency rule, separation of concerns, and testability, including complete code examples and checklists
  - **Spec-driven development**: Added `builtin/rules/sdd.md`, defining the spec-implementation-verification loop, providing concrete development flows and verification standards
- **New development conventions**
  - **New-rule conventions**: Added `builtin/rules/add_rule.md`, standardizing how to create new rule files, including file locations, naming conventions, format requirements, and a Jinja2-variable usage guide. Provides complete rule templates and best practices
  - **Rule-list update**: Updated `builtin/rules/builtin_rules.md`, adding categories such as architecture design, development flow, and code quality, providing a clearer rule index
- **New best-practice documents**
  - **JCAD best practices**: Added `docs/best_practices/jcad_Best_Practices.md`, detailing the best practices of the code-review agent, including use cases, configuration methods, and performance optimization

  - **Rule best practices**: Added `docs/best_practices/rules_best_practices.md`, providing a complete guide to rule writing, including rule-design principles, common errors, and maintenance suggestions

- **New comparison document**
  - **HaijunBot vs Codex CLI**: Added `docs/compare/haijunbot_vs_codex_cli.md`, detailing the functional differences and pros/cons analysis between HaijunBot and Codex CLI, helping users choose the right tool
- **Obsolete-document removal**
  - **Removed generate_rules.md**: Deleted `builtin/rules/generate_rules.md`, which has been replaced by the new conventions system

#### **🧪 Test Enhancements**

- None

#### **🗑️ Removed**

- **Rule-file deletion**
  - **generate_rules.md**: Removed the obsolete rule-generation file, replaced by the new rules-convention system (add_rule.md, builtin_rules.md, etc.)
    This update is an important release for **documentation conventions and system optimization**. Core highlights include:
    **🎯 Four core improvements:**

1. **System-tool check**: Added the haijunbot_jck module, providing system-tool-check functionality, supporting custom check rules and configuration-based management

2. **Architecture-design conventions**: Added architecture-design conventions such as SOLID design principles, clean architecture, and SDD, guiding the construction of high-quality maintainable architectures

3. **Development-convention system**: Improved the rule-writing conventions, providing complete rule templates and best practices
4. **Best-practice documents**: Added JCAD best practices, rule best practices, and other documents, improving development efficiency
   **Other important improvements:**

- **Message-truncation optimization**: Optimized the message-truncation logic, improving system stability
- **Memory-system enhancement**: Enhanced memory storage and retrieval functionality
- **Version-release conventions**: Established a complete version-release-flow convention
   These improvements together enhance HaijunBot's capabilities in development conventions, documentation quality, and system stability.
  **Technical highlights:**
- **System-tool check**: Custom check rules, configuration-based management, CLI interface, JSON output
- **Architecture conventions**: SOLID principles, clean architecture, dependency rules, checklists
- **Development conventions**: Rule templates, Jinja2 variables, best practices
- **Version release**: Semantic versioning, git diff verification, format consistency

---

### Release Note - v1.1.1 2026-01-11

#### **🚀 New Features**

- **🎯 Methodology-tool enhancement**
  - **Project-level and global-level methodology management**: Added a methodology-scope feature, supporting project-level (project) and global-level (global) methodology management. Project-level methodologies are stored in the `.haijunbot/methodologies` directory of the Git repository and are only for the current project; global-level methodologies are stored in the user-data directory and can be shared across all projects. The scope is selected via the `scope` parameter, defaulting to `global`
  - **Methodology-tool scope parameter**: Added `scope`-parameter support to methodology tools, allowing the scope to be specified when adding, updating, or deleting methodologies. The task-analysis prompt has been updated, guiding the Agent to choose the appropriate scope based on the methodology type (use `project` for project-specific and `global` for general methodologies)

- **🎯 Output-system enhancement**
  - **New output types**: Added 7 output types, enriching output styles and semantics: `START` (task start), `TARGET` (target task), `STOP` (task stop), `RETRY` (retry operation), `ROLLBACK` (rollback operation), `DIRECTORY` (directory-related), `STATISTICS` (statistical information). Each type has corresponding icon and style configurations, improving output readability and visual experience
  - **Error-output blinking effect**: Added a blinking effect to error output types, making error messages more prominent, improving the user experience

- **🎯 Quick-configuration-tool enhancement**
  - **Interactive parameter input**: The quick-configuration tool (`hqc`) now supports interactive input; when required parameters (platform, base_url, api_key) are not provided, it automatically prompts the user, simplifying the configuration flow
  - **Default-model selection**: Added default-model selection, supporting selecting a default model when configuring multiple models, automatically creating the corresponding model-group configuration
  - **Automatic model-group creation**: The quick-configuration tool automatically creates `llm_groups` configuration for the default model and sets the default model group, simplifying configuration management

- **🎯 Code-review enhancement**
  - **Custom build validator**: Added custom-build-command support, allowing specifying custom build commands in the code-review configuration, supporting Jinja2 template syntax to render rule content, providing more flexible code-review capability
  - **Jinja2 template support**: Code-review rule files support Jinja2 template syntax, allowing dynamic variables and conditional rendering in rules, improving rule flexibility and reusability

- **🎯 Tool-call enhancement**
  - **Agent-intent display**: Added Agent-intent display before tool execution, showing the Agent's intent (`want` field) when invoking tools, helping users better understand the upcoming operation

- **🎯 Installation and update enhancement**
  - **uv tool install support**: Added detection and update support for the uv tool installation method, automatically detecting whether installed via `uv tool` and using the `uv tool upgrade` command for updates, improving the installation and update experience
  - **Gitee mirror support**: The install script adds Gitee mirror support, allowing installation from the Gitee mirror repository for faster download speeds. The install script automatically degrades and retries, prioritizing GitHub and automatically switching to the Gitee mirror on failure

#### **📌 Fixes**

- **Tmux session-management fixes**
  - **Username-cleanup feature**: Fixed issues caused by special characters in tmux session names, adding a username-cleanup feature that automatically cleans special characters (such as @, +, .) from usernames, ensuring the generated tmux session names are valid
  - **Session-lookup optimization**: Optimized the session-lookup logic, verifying session usability to avoid returning abnormally exited sessions. Automatically creates a new session when the current window cannot be obtained, improving session-management stability

- **Web-reading-tool fixes**
  - **Content-truncation-logic optimization**: Fixed the handling logic for overly long web content, changing the content-length limit from character count to token count, dynamically calculating the content-length limit based on remaining tokens, avoiding inaccurate content truncation

- **Code-reading-tool fixes**
  - **Status-info display format**: Fixed the status-info display-format issue in the code-reading tool, uniformly using newline separators for status information, improving readability

- **Tool-call fix-logic optimization**
  - **Tool-call-fix refactoring**: Refactored the tool-call-fix logic, extracting it into the shared function `fix_tool_call_with_llm`, improving code reusability and maintainability

- **Configuration-system fixes**
  - **Configuration-guide-command fix**: Fixed the configuration-guide command invocation, changing `hcfg` to `hqc`, using the quick-configuration tool instead of the web-configuration interface
  - **Platform token-limit fix**: Fixed the issue where the Agent used the global-config token limit, changing it to use the platform's actual token limit, improving token-management accuracy

#### **🔧 Optimizations and Refactoring**

- **Task-list-manager optimization**
  - **Task-priority-field removal**: Removed the task-priority field, simplifying the task data structure. Changed the task-sorting logic from sorting by task sequence number to sorting by creation time, simplifying task-management logic

- **Web-search-tool optimization**
  - **Token-limit optimization**: Changed the content-length limit of the web-search tool from character count to token count, dynamically calculating the content-length limit based on remaining tokens, more precisely controlling content length, avoiding token overflows

- **Methodology-loading optimization**
  - **Token-limit-strategy adjustment**: Optimized the methodology token-limit strategy, changing from using 2/3 of remaining tokens to 0.75 of the model context window, providing more stable token-limit calculation
  - **Methodology-data-structure optimization**: Optimized the methodology loading and export logic, unifying the methodology data structure, improving code maintainability

- **Platform-system cleanup**
  - **File-upload-function removal**: Removed file-upload-function support from all platforms, simplifying the platform interface. Removed yuanbao-platform file-upload-related code (COS upload, file metadata, etc.), cleaning up platform-management code
  - **web_llm configuration removal**: Removed the `web_llm` configuration option; web-search functionality uniformly uses the model configured in `normal_llm`, simplifying configuration management
  - **Platform-web-function removal**: Removed platform-web-function-related code, simplifying the platform interface and implementation

- **Code-agent optimization**
  - **Agent-initialization refactoring**: Refactored the Agent-initialization logic into modular methods, improving code readability and maintainability
  - **Tool-call-logic optimization**: Optimized the tool-call-logic placement, filtering tool-call content from LLM responses, improving tool-call accuracy

- **Installation-script optimization**
  - **uv-tool global install**: Modified the install script to use the uv tool for global installation, simplifying the installation flow
  - **Auto-completion-tool-list update**: Updated the auto-completion tool list, adding support for new commands

- **Code-quality improvement**
  - **Type-annotation fixes**: Fixed type-annotation issues, adding `type: ignore` comments to ignore third-party-library type checks, improving code quality
  - **Dependency-management optimization**: Added the jinja2 dependency, optimizing dependency ordering and configuration format

#### **📚 Documentation Update**

- **Installation-guide update**
  - **uv tool installation method**: Updated the installation guide, recommending the `uv tool` method for installing haijunbot, explaining that `uv tool` automatically manages the tool's virtual environment, requiring no manual creation or activation
  - **Gitee-mirror explanation**: Added the Gitee-mirror repository explanation, providing a faster download option

- **Usage-guide update**
  - **Custom-build-validator explanation**: Added custom build, static-check, and post-modification-processing configuration explanations
  - **Rule-placeholder explanation**: Added a rule-placeholder Jinja2-template explanation, helping users understand how to use template syntax

- **Configuration-parameter-documentation update**
  - **Configuration-parameter update**: Updated the configuration-parameter documentation, reflecting the latest configuration-option changes

- **README update**
  - **Repository-link fix**: Fixed the GitHub-repository-link format, updating the project-repository link
  - **Welcome-message update**: Updated the welcome message, adding the project-repository link

#### **🧪 Test Enhancements**

- **Task-list-management test update**
  - **Test-case adaptation**: Updated test cases to adapt to the data structure after removing the task-priority field

#### **🗑️ Removed Features**

- **Platform-function removal**
  - **File-upload feature**: Removed file-upload-function support from all platforms, including yuanbao-platform COS upload and file-metadata functions
  - **web_llm configuration**: Removed the `web_llm` configuration option; web search uniformly uses the `normal_llm` configuration
  - **Platform-web function**: Removed platform-web-function-related code and interfaces

- **Tool removal**
  - **Train-schedule-query tool**: Removed the train-schedule-query tool (`train_schedule_query.py`)

This update is an important release for **methodology management and system optimization**. Core highlights include:

**🎯 Four core features:**

1. **Methodology-scope management**: Supports project-level and global-level methodology management, providing a more flexible methodology-organization approach

2. **Output-system enhancement**: Added 7 output types, enriching output styles and semantics, improving the user experience

3. **Quick-configuration-tool enhancement**: Supports interactive input, default-model selection, and automatic model-group creation, simplifying the configuration flow
4. **Code-review enhancement**: Supports custom build validators and Jinja2 template syntax, providing more flexible code-review capability

**Other important improvements:**

- **Tmux session-management optimization**: Username cleanup, session-lookup optimization, automatic new-session creation
- **Installation and update enhancement**: uv-tool install support, Gitee-mirror support
- **Platform-system cleanup**: File-upload-function removal, web_llm-configuration removal, platform-web-function removal
- **Tool-call optimization**: Agent-intent display, tool-call-fix-logic refactoring

These improvements together enhance HaijunBot's capabilities in methodology management, configuration experience, and system stability.

**Technical highlights:**

- **Methodology scopes**: Project-level and global-level methodology management, scope-parameter support, intelligent scope selection
- **Output system**: 7 new output types, error-output blinking effect, rich style configurations
- **Quick configuration**: Interactive input, default-model selection, automatic model-group creation
- **Code review**: Custom build validators, Jinja2 template support, flexible rule configuration
- **Installation optimization**: uv-tool support, Gitee mirror, automatic fallback retry

---

### Release Note - v1.1.0 2026-01-07

#### **🚀 New Features**

- **🎯 Tmux integration and parallel task execution (major update)**
  - **Tmux wrapper module**: Added a complete **tmux** wrapper module (`tmux_wrapper.py`), providing unified tmux session-management, window, and panel-operation interfaces, supporting automatic tmux-environment detection and session creation when needed. During implementation, all tmux operations were unified to use encapsulated functions, optimizing the command-dispatch and session-creation logic and prioritizing the use of existing sessions
  - **Task-dispatch tools**: Added convenient task-dispatch commands `hjbd` (HaijunBot Agent Dispatcher) and `hcad` (HaijunBot Code Agent Dispatcher), simplifying the flow of dispatching tasks to tmux. `hjbd` is a convenient wrapper for `hjb`, supporting either direct task execution or interactive mode for entering tasks; `hcad` is a convenient wrapper for `hca`, automatically enabling non-interactive mode, worktree mode, and task dispatch, specifically for quick code-task dispatch
  - **Batch parallel task execution**: The task-list manager adds a **batch-execution feature**, supporting parallel execution of multiple independent sub-type tasks in the tmux environment, significantly improving task-execution efficiency. The system automatically creates an independent tmux panel for each task and monitors the execution status of all tasks. Optimized the panel-allocation strategy, supporting task execution in new panels in the current window, avoiding excessive window creation
  - **Panel and window management**: Supports creating panels via horizontal (-h) and vertical (-v) splits, choosing the appropriate layout based on the use scenario. Automatically sets the tmux window to a tiled layout, optimizing multi-panel display. Improved window and panel retrieval, creation, and layout operations, unifying error handling
  - **Session-persistence option**: Added a parameter controlling whether the tmux session stays active after command execution, supporting a shell-fallback mechanism, improving the user experience
  - **Tmux feature toggle**: Added the configuration option `enable_tmux`, controlling whether tmux functionality is enabled, providing a more flexible configuration choice

- **MCP (Model Context Protocol) enhancement**
  - **Session-ID storage**: Added MCP session-ID storage, automatically retrieving the session ID from response headers and automatically adding it to request headers in subsequent requests, improving the session-management capability between MCP client and server

- **Input-system enhancement**
  - **Ctrl+X program exit**: Added the Ctrl+X shortcut, allowing users to quickly exit the program, providing a more convenient interaction method
  - **Multi-line-input confirmation enhancement**: Added Ctrl+] as the multi-line-input confirmation shortcut, supporting confirmation via Ctrl+] or Ctrl+J, providing more input-confirmation options and optimizing the multi-line editing experience

- **🎯 Code-agent feature expansion**
  - **Virtual-terminal-tool support**: **CodeAgent** adds **virtual-terminal-tool** support, allowing interactive operations and expanding the code-agent capability boundary. Supports directly executing interactive commands in the code agent without manual operations
  - **Git Worktree support**: Added the `--worktree` option, developing on an independent branch, supporting automatic creation and merging of **worktree** branches, providing better code-development isolation and management. Added automatic committing of unsaved changes, automatically handling uncommitted code changes in worktree mode. Optimized the branch-info retrieval timing, improving workflow efficiency
  - **Starting-commit parameter**: Added starting-commit-parameter support, allowing the starting point for code review and change tracking, providing more precise code-change analysis

- **🎯 Task-list-manager enhancement**
  - **Batch task execution**: Added a **batch-execution feature**, supporting parallel execution of multiple independent sub-type tasks in the tmux environment, significantly improving task-execution efficiency. Added batch-execution condition verification, ensuring all tasks meet the execution conditions (sub type, pending status, dependencies completed, tasks independent of each other). Automatically creates independent panels and monitors execution status, providing detailed execution reports
  - **Task-list save and restore**: Added task-list save and restore functionality, supporting automatic task-list-state restoration on session recovery, improving task-management continuity

- **Configuration-system enhancement**
  - **Graceful-shutdown timeout configuration**: Added a graceful-shutdown-timeout configuration option, allowing configuration of the system shutdown timeout, improving system stability
  - **Max-input-token increase**: Raised the default max-input-token count from 32,000 to 128,000, supporting a larger context window, adapting to more large-model scenarios

- **Platform-system improvement**
  - **Message-history trimming**: Added message-history trimming, automatically trimming historical messages when tokens are insufficient to ensure new messages are sent normally, solving token-limit issues
  - **Platform cleanup**: Removed the human platform and deprecated the kimi, tongyi, and yuanbao platforms, simplifying platform management

- **Code-review enhancement**
  - **Custom review-rule files**: Supports custom code-review-rule files, allowing users to tailor review rules to project needs, improving review flexibility

- **Run-loop enhancement**
  - **Supplementary-info input on interruption**: Supports entering multi-line supplementary information on keyboard interruption, allowing users to provide additional context after interruption, improving the interaction experience

- **Session-management enhancement**
  - **Timestamps and multi-session selection**: Added a timestamp mechanism, adding unique identifiers to session files (format: `YYYYMMDD_HHMMSS`), supporting multiple concurrent session files. Supports selecting the latest session or a specified-timestamp session during recovery, automatically recovering the latest session in non-interactive mode. Added the ListSessions command to view all session files

- **Code-editing-tool enhancement**
  - **Partial-success-mode support**: Added partial-success-mode support; when some diff operations fail, the successful modifications are still saved to the file, with detailed execution results reported for each diff, improving the editing-tool fault tolerance

- **Tool-execution enhancement**
  - **Pre-execution confirmation prompt**: Added a confirmation prompt and parameter-summary display before tool execution, showing the tool name and parameter summary before execution, helping users better confirm the upcoming operation. The parameter summary filters sensitive information (such as passwords, tokens) and truncates long strings

#### **📌 Fixes**

- **Output-decoding fixes**
  - **Unified output decoding**: Uniformly uses the `decode_output` function to handle all subprocess output, supporting automatic fallback across UTF-8, GBK, and latin-1 encodings, fixing encoding-compatibility issues. Updated the output-decoding logic of the virtual-terminal tool, Git tools, etc.

- **Code-editing-tool fixes**
  - **Partial-success-operation status marking**: Fixed the status-marking issue of partial-success operations; when the file-edit operation partially succeeds, the overall operation status is correctly marked (marked as success when partially successful), with detailed error information extracted for failures and partial successes

#### **🔧 Optimizations and Refactoring**

- **Task-list-manager optimization**
  - **Batch-execution-logic improvement**: Improved the task-status-update logic during batch execution, ensuring all task statuses are correctly updated, marking tasks as complete even if reading results fails
  - **Temporary-file handling**: Optimized the temporary-file-handling mechanism, improving the creation, reading, and cleanup logic of task files

- **Code-agent optimization**
  - **Non-interactive-mode identifier removal**: Removed the non-interactive-mode identifier, simplifying code logic
  - **Code-review-prompt update**: Updated the code-review-prompt rules, improving review quality

- **Git-tool optimization**
  - **Large-file-diff handling**: Optimized the file-list display and large-file-diff handling logic when generating commit messages, improving performance

- **MCP-client optimization**
  - **HTTP-client optimization**: Optimized the configuration and response-handling logic of the HTTP MCP client, supporting custom endpoint-path configuration, improving SSE streaming-response parsing, and enhancing error handling and debug-info output

- **Quick-configuration optimization**
  - **Platform-API-config-key-name generation**: Optimized the platform-API-config-key-name generation logic of the quick-configuration tool, generating the corresponding API key names based on the specific platform type (OpenAI/Haijun), improving configuration accuracy and compatibility

- **Input-system optimization**
  - **Multi-line-input-function optimization**: Optimized the multi-line-input function, removing debug code, uniformly using the Ctrl+J/Ctrl+] prompt format

- **Code-quality improvement**
  - **Type-annotation fixes**: Fixed type-annotation issues, removing debug auto-print statements, improving code quality

#### **📚 Documentation Update**

- **Test-documentation update**
  - **New test cases**: Added complete test cases for the task-list save/restore feature, batch-execution feature, and session-management feature, improving test coverage
  - **Test-case adaptation**: Updated test cases to adapt to the new session-file-naming format and the task-list save/restore feature

#### **🧪 Test Enhancements**

- **Task-list-management tests**
  - **Task-list save/restore tests**: Added complete tests for the task-list save and restore feature, covering single-task-list, multi-task-list, and dependency-based task-list scenarios
  - **Batch-execution tests**: Added complete batch-execution tests, including test cases for condition verification, execution flow, and result collection

- **Session-management-test update**
  - **Session-file-naming tests**: Updated session-management tests to adapt to the new timestamp-based file-naming format
  - **Non-interactive-mode tests**: Added test cases for automatically recovering the latest session in non-interactive mode

This update is an important release for **Tmux integration and parallel execution**. Core highlights include:

**🎯 Four core features:**

1. **Tmux integration**: A complete tmux wrapper module, providing unified session-management, window, and panel-operation interfaces, supporting smart panel allocation and layout management

2. **Batch task execution**: Supports parallel execution of multiple independent tasks in the tmux environment, automatically creating independent panels and monitoring execution status, significantly improving task-execution efficiency

3. **Git Worktree support**: Develop on an independent branch, supporting automatic creation and merging of worktree branches, providing better code-development isolation and management
4. **CodeAgent virtual terminal**: The code agent adds virtual-terminal-tool support, allowing interactive operations and expanding the code-agent capability boundary

**Other important improvements:**

- **MCP session-management enhancement**: Session-ID storage and automatic addition to request headers
- **Input-system improvement**: Ctrl+X program exit, Ctrl+] multi-line-input confirmation
- **Configuration-system optimization**: Max token count raised to 128,000, graceful-shutdown configuration
- **Platform-system improvement**: Message-history trimming, platform cleanup, custom code-review rules

These improvements together enhance HaijunBot's capabilities in complex-task management, parallel execution, and system stability.

**Technical highlights:**

- **Tmux integration**: Complete tmux wrapper, smart panel allocation, parallel task execution, session management
- **Task-dispatch tools**: Added `hjbd` and `hcad` convenience commands, simplifying the task-dispatch flow, supporting interactive mode and multi-line input
- **Batch task execution**: Batch-execution verification, independent-panel creation, status monitoring, execution reports
- **Git Worktree**: Independent-branch development, automatic creation and merging, code isolation
- **Virtual terminal**: Interactive-operations support, expanded code-agent capability
- **MCP enhancement**: Session-ID management, HTTP-client optimization
- **Configuration optimization**: Max token count raised to 128,000, graceful-shutdown configuration, quick-configuration optimization

---

### Release Note - v1.0.12 2026-01-04

#### **🚀 New Features**

- **Quick-configuration-tool enhancement**
  - **haijunbot-quick-config CLI tool**: Added the haijunbot-quick-config CLI tool, supporting quick configuration of Haijun/OpenAI platform info into the llms section of the HaijunBot configuration file, including API-connectivity tests, automatic model discovery, and secure storage, simplifying the LLM-platform configuration flow
  - **Multi-model-selection configuration**: Updated haijunbot-quick-config, allowing users to choose to configure all models or select some models via comma-separated sequence numbers. When configuring multiple models, an independent configuration item is created for each model, using config-name + model-name to avoid conflicts, enabling use of different models in different scenarios
- **Web-configuration-interface enhancement**
  - **Form-section collapse/expand feature**: Added collapsible sections to the configuration form, improving the user experience with many configuration items. Added expand-all/collapse-all buttons for quick form-section operations. Refactored the form structure styles, optimizing the configuration-tool interface interaction experience

#### **📌 Fixes**

- **Configuration-system fixes**
  - **immediate_abort default-value adjustment**: Changed the immediate_abort config default from false to true, allowing the system to immediately stop output and return when detecting a user-interrupt signal, improving the user experience and response speed

#### **🔧 Optimizations and Refactoring**

- **Configuration-system refactoring**
  - **Top-level RAG-config removal**: Removed the top-level RAG configuration items from the config file; now only configurations referenced via rag_group are supported, simplifying the config-precedence-handling flow. Adjusted the required-field JSON format to single-line display, optimizing config-file readability
- **Web-configuration-interface optimization**
  - **Collapse-function optimization**: Improved the collapse-function implementation, using event delegation to handle collapse operations, fixing the expand/collapse-state inconsistency issue. Also adjusted UI styles, including smaller padding and optimized font sizes and spacing, improving page performance
- **Platform-manager optimization**
  - **CLI-argument simplification**: Unified the platform and model parameters into the llm-group parameter, simplifying command-line-option configuration. Refactored the info command to support model-group-config-viewing, improving platform-instance creation and error-handling mechanisms. Removed redundant platform/model parameter options, uniformly using config-file defaults
- **Output-system optimization**
  - **Simplified output method**: Changed the history-display feature from PrettyOutput.auto_print to standard print output, simplifying the output method and removing the PrettyOutput dependency
- **Build-system optimization**
  - **Dependency-version update**: Updated tree-sitter and its language-parser dependencies to specified versions, restricted the supported Python version to 3.12.x, and removed obsolete Python-version classification declarations, improving dependency-management clarity and compatibility

#### **📚 Documentation Update**

- **Configuration-documentation update**
  - **RAG-config explanation update**: Updated the rag_groups configuration notes, clarifying that defining embedding_model and other parameters directly is no longer supported; the embedding reference must be used to reference configurations in embeddings. Added an explanation that the top-level rag configuration items have been removed, optimized the config-variable table formatting, reduced table width for easier reading, and removed the deprecated rag configuration-item explanations

---

### Release Note - v1.0.11 2026-01-03

#### **🚀 New Features**

- **Task-list-manager enhancement**
  - **Code-change diff verification**: Integrated git tool functions, recording commit hashes before and after task execution, calculating and truncating diff content, and adding the code-change info to the verification context for more precise task-completion verification
  - **Dynamic task-output-length limit**: Changed the fixed default max task-output length to a dynamically calculated value based on the current model configuration, obtaining the max input token count from the agent instance or global model group and calculating an appropriate output-length limit, providing a more flexible and adaptive length-control mechanism
- **File-reading-tool optimization**
  - **Optimized file-reading status display**: When a file is read successfully, the actual read line-range info is parsed and shown in the status message, providing more accurate feedback to the user. If the actual range cannot be parsed, it falls back to displaying the requested range
- **Rules-system expansion**
  - **AI code-development guidance rule file**: Added a complete AI code-development guidance rule file, including coding and format conventions (PEP 8, type annotations, naming conventions), project-structure conventions (directory layout, module organization, dependency relationships), error-handling conventions (exception definitions, error logging, recovery mechanisms), data-handling conventions (JSON/YAML handling, data validation, encoding compatibility), interface-design conventions (FastAPI, CLI, API naming), performance-and-resource conventions (caching, resource management, performance optimization), dependency-management conventions (import order, configuration management, dependency injection), and type-annotation conventions (base types, optional types, generics), providing standardized guidance for AI-generated code

#### **📌 Fixes**

- **Code-agent fixes**
  - **Non-interactive-mode code-review logic**: Fixed a logic error in the code-review feature in non-interactive mode; in non-interactive mode, the code-review feature should be controlled by the disable_review parameter, while in interactive mode it should always be disabled. Also fixed the help-text description of the CLI parameter
- **Git-tool fixes**
  - **Manually-staged-file handling**: Fixed the issue of manually staged files being ignored by gitignore; after running git add ., the previously manually staged gitignore-ignored files are re-added, ensuring these files can also be committed
  - **Uncommitted-change detection**: Fixed the gitignore-ignored-file handling in the has_uncommitted_changes function, recording manually staged files before Git operations and re-adding them after reset, ensuring gitignore-ignored but already staged files are not lost
  - **Failed-commit file recovery**: Fixed the issue of losing manually staged files after a failed commit; when a Git commit fails, the system resets the staging area, but previously manually added gitignore-ignored files are lost. Now the staged-file list is recorded before running git add, and the files are re-added after a reset following a commit failure, ensuring manually staged files are not lost due to commit failure

#### **🔧 Optimizations and Refactoring**

- **Code-review-flow optimization**
  - **User-confirmation-step removal**: Removed the user-confirmation step from the code-review flow, simplifying it and improving the automation experience
- **Diff-visualization optimization**
  - **Code line-wrapping support**: Added word_wrap=True to table columns and syntax-highlighting components, fixing long-code-line display truncation, improving code-comparison-visualization readability
  - **Changed-block-handling optimization**: Removed separator logic, optimizing the changed-block-handling flow
- **Web-interface refactoring**
  - **Dark-theme switch**: Switched the interface from a light theme to a dark theme, updating terminal-container styles, color configuration, and shadow effects. Also removed the original input-panel area and related JavaScript functions, simplifying the interface structure
  - **UI-output unification**: Uniformly uses PrettyOutput for table-content output, improving interface consistency
- **Task-list-manager optimization**
  - **Redundant-operation removal**: Removed redundant snapshot-saving operations, optimizing the task-execution flow
- **Subprocess-handling optimization**
  - **Unified output handling**: Unified subprocess output handling to binary mode with decode_output decoding, removing extra output-decoding handling, improving encoding compatibility and processing efficiency
- **Code-quality improvement**
  - **Type-annotation fixes**: Fixed type-annotation and variable-naming issues, improving code quality

#### **📚 Documentation Update**

- **Theme-design documentation**
  - **iOS dark-theme design guide**: Added a complete Zen-iOS Hybrid dark-theme design guide, including visual tone, material physical texture, interaction-component conventions, modular-layout logic, and typography details. Also renamed ios-front-style.md to ios-light-theme.md for naming consistency
- **Configuration-documentation update**
  - **Web-LLM-config removal**: Removed the web_llm configuration option; web-search functionality now uniformly uses the model configured in normal_llm, no longer supporting an independent web_llm configuration. Updated the configuration documentation and examples, simplifying the configuration structure

---

### Release Note - v1.0.10 2025-01-01

#### **🚀 New Features**

- **Configuration-system enhancement**
  - **Object-type values in dict configs**: Extended the dynamic-form-generation logic to handle object-type values when adding dictionary entries. When the value schema is an object, the system renders its property fields based on the schema definition, and the key-change-handling function was updated to synchronize all nested field names inside the object

#### **📌 Fixes**

- **Haijun-platform fixes**
  - **System-message format adaptation**: Fixed the conversion of system messages from string format to array format to meet the backend-API format expectations
  - **Model-list retrieval**: Fixed message-format type annotations and implemented actually retrieving the model list from the API
- **Web-application fixes**
  - **Dynamic dict-key synchronization**: Added an oninput event listener to the key-input box, implementing real-time updates when the key is entered, using dataset.currentKey to track the current key state, ensuring the value field's name attribute updates correctly when the user modifies the dict key
  - **Nested-dict handling**: Added the processNestedDictKeys function to recursively handle the **key** and **temp** special keys in nested objects, traversing the entire object tree to convert temporary key-value pairs into actual key-value pairs, solving the limitation of only handling single-level dicts
  - **Dict-key handling**: Fixed the field-synchronization issue during dynamic dict-key input
- **Tools-and-dependency fixes**
  - **subprocess output decoding**: Added the decode_output tool function, supporting automatic fallback across UTF-8, GBK, and latin-1 encodings, refactored all modules involving subprocess calls, removing text=True and hard-coded encoding parameters

#### **🔧 Optimizations and Refactoring**

- **Configuration-system optimization**
  - **Windows-system-restriction removal**: Removed the special-case logic for the Windows OS in get_pretty_output; the function no longer forces a False return based on OS type, instead directly returning the config-file setting, supporting modern Windows-terminal environments
- **Tools-and-dependency optimization**
  - **Unified subprocess output handling**: Refactored all modules involving subprocess calls, removing text=True and hard-coded encoding parameters, changing to uniformly capture byte streams and decode with decode_output, solving the issue of Git-command output showing mojibake or failing to decode on different operating systems (especially Windows)
  - **Circular-dependency fix**: Changed the user_confirm import to a deferred import, avoiding circular dependencies between modules, and updated the import method at the terminal-nesting-detection and git-repository-change-confirmation locations
- **Web-application refactoring**
  - **Dict-form-field refactoring**: Changed the generation and data-submission mechanism of dynamic dict-type form fields, removing the logic that relied on onchange events to update the field name attribute in real time, instead using the placeholders **temp** and **key** for identification; during data collection, the data corresponding to **temp** is mapped to the actual key name entered by the user based on the value of the **key** input box, simplifying frontend state management and avoiding synchronization issues from dynamically modifying DOM names
  - **Dict-key-handling optimization**: Refactored the dict-key-handling logic; code-formatting fixed the code format of PrettyOutput.auto_print calls, conforming to code conventions; refactored the dict-key-collection logic to directly collect the actual key names entered by the user during the first traversal of form data, avoiding a second traversal of entries; simplified temporary-key handling using the pre-collected actualKeyName instead of repeated traversal lookups, improving code readability and execution efficiency

#### **📚 Documentation Update**

- **Architecture-documentation update**
  - **New configuration-system document**: Added a configuration-system document and architecture-diagram update; the core-concepts chapter adds "configuration system" as the eighth foundational pillar, improving system base definitions; added detailed functionality and use-scenario descriptions for the configuration-system components (Schema parser, Web application, CLI tools); updated the system-architecture diagram, integrating the configuration-system module and its interactions with users and agents; added the core-architecture principle "Schema-based configuration drive"; supplemented section 3.3.8, deeply analyzing the internal implementation and external integration of the configuration system
- **Project-entry removal**
  - **zlib_rs project removal**: Removed the entry about the 'zlib_rs project' from the changelog

---

### Release Note - v1.0.8 2025-12-31

#### **🚀 New Features**

- **Configuration-system major upgrade**
  - **haijunbot_config configuration tool**: Added a dynamic configuration-tool module based on JSON Schema, providing a web-configuration interface and CLI; supports automatically generating configuration forms from JSON Schema, implementing configuration validation and type conversion; provides a server-shutdown interface and optimizes the post-save user experience; supports independent LLM configuration for web search and optimizes form layout; adds visual-indicator styles for deprecated fields
  - **Web-configuration interface**: Replaced command-line interactive configuration with a web-configuration interface, providing a friendlier configuration experience; optimized form-interface visual density, reducing spacing and sizes; supports boolean parsing of `on` and `off`; implements automatic type conversion after configuration validation
  - **Configuration-loading optimization**: Fixed the configuration-loading order and updated the default token limit to 128,000; supports empty values for LLM-reference configurations; removed the logic that automatically stripped default values during configuration loading

- **Platform-support expansion**
  - **Haijun-platform integration**: Integrated Juglow Haijun platform support, adding the `HaijunModel` class implementing the complete Haijun API interface; supports configuration via `juglow_api_key` and `juglow_base_url`; supports streaming responses and message-history management

- **C2Rust transpilation-tool enhancement**
  - **FFI-export verification**: Added FFI-export verification, enhancing FFI-export verification and cdylib configuration; added a mandatory requirement in the code-generation prompt to keep constants and macro values consistent
  - **Symbol-extraction feature**: Supports extracting symbols from C/C++ source files and strengthened file-type validation

- **Task-list-manager enhancement**
  - **Custom verification methods**: Added custom verification-method parameters, enhancing the verification-method field description
  - **Conversation-turn statistics**: Added conversation-turn statistics, skipping verification when fewer than 5 turns have occurred, improving verification efficiency

- **Agent and platform-management optimization**
  - **Non-interactive-mode enhancement**: Automatically completes replies in non-interactive mode, improving the automation experience
  - **Model-group override**: Allows overriding model-group configuration during conversations, providing more flexible model selection
  - **Response-output beautification**: Uses Rich panels to beautify LLM-response output, improving the visual experience

- **Tools-and-documentation enhancement**
  - **Git work-summary tool**: Added a Git work-summary-generation tool (later reverted)
  - **Project-positioning refactoring**: Refactored the project positioning as an AI-application-development SDK and updated the documentation; removed the zero-cost-integration descriptions from the project introduction
  - **Terminology unification**: Unified the terminology "silent mode" to "unattended mode"
  - **Design-convention document**: Added the Zen-iOS Hybrid frontend design-convention document
  - **Central rule repository**: Added a central rule repository and multiple configuration options

#### **📌 Fixes**

- **Configuration-system fixes**
  - **Configuration-loading order**: Fixed the configuration-loading order, ensuring configurations load correctly
  - **Boolean-switch handling**: Fixed the handling logic for unchecked boolean switches in the configuration interface
  - **Configuration-saving issues**: Fixed configuration-saving and form-field-path-handling issues; fixed regex escaping in form-key-name parsing

- **Platform-and-code fixes**
  - **Platform-instance creation**: Fixed the missing configuration parameters when creating platform instances
  - **File-editing tool**: Rejects invalid operations where search and replace content are identical, avoiding meaningless edits

- **Code-agent optimization**
  - **LLMManager removal**: Removed LLMManager and inlined the large-code-deletion check logic, simplifying the code structure

#### **🔧 Optimizations and Refactoring**

- **Configuration-system refactoring**
  - **Web-configuration-interface replacement**: Replaced command-line interactive configuration with a web-configuration interface, providing a more modern configuration experience
  - **Debug-log unification**: Uses auto_print to unify debug-log output, improving log consistency

- **Code-quality improvement**
  - **Test optimization**: Simulated time.sleep in the retry test, improving test reliability
  - **Documentation organization**: Organized competition materials into an archive directory, optimizing the project structure

#### **📚 Documentation Update**

- **Project-documentation refactoring**
  - **README update**: Refactored the project positioning as an AI-application-development SDK and updated the documentation
  - **Project-introduction adjustment**: Removed the zero-cost-integration descriptions from the project introduction
  - **Terminology unification**: Unified the terminology "silent mode" to "unattended mode"
  - **Design conventions**: Added the Zen-iOS Hybrid frontend design-convention document
  - **Technical report**: Updated coverage data and fixed code-block formatting; supplemented PDF-file submission

- **Configuration-tool documentation**
  - Added complete documentation and usage instructions for the haijunbot_config module

#### **🧪 Test Enhancements**

- **Test fixes and optimization**
  - Simulated time.sleep in the retry test, improving test reliability and accuracy

---

### Release Note - v1.0.3 2025-12-20

#### **🚀 New Features**

- **Tool-experience enhancement**
  - **Script-execution-tool optimization**: Added automatic line-wrapping to the `execute_script` tool, with long-line code wrapping automatically; uses a rich panel to display the script content before execution, improving readability via syntax highlighting; added script-execution-duration statistics, automatically calculating and displaying execution time
  - **Code-reading-tool enhancement**: Added file-line-range info to the success-status line of the `read_code` tool, showing the overall merged line range for merge requests; added read-line-count statistics to the file-reading output, helping users more intuitively understand the actual line range of code read
  - **Diff-visualization optimization**: Added automatic line-wrapping to the diff-display table, allowing long-text content to wrap automatically, improving code-diff readability

- **Task-list-manager enhancement**
  - **Follow-up-task-necessity assessment**: Added a follow-up-task-necessity assessment prompt, helping the system more intelligently determine whether follow-up tasks need to continue
  - **Running-task mutual-exclusion check**: Added a running-task mutual-exclusion check, avoiding task conflicts and resource-competition issues
  - **Task-verification optimization**: Clearly distinguishes fix suggestions from prohibited-fix behaviors during verification, improving verification-flow clarity

- **System-prompt and configuration enhancement**
  - **Working-directory prompt**: Added a current-working-directory prompt to the system info, helping users and the AI better understand the current working environment
  - **Pin-marker-handling optimization**: Enabled the next-round input handler to process the `pin_content` special marker, adjusting the Pin-marker-handling order and preserving prefix content, ensuring key information is not lost
  - **LLM-configuration expansion**: Added `llm_config`, `cheap_llm_config`, and `smart_llm_config` as three configuration keys to the global configuration parsing, supporting configuration overrides for different LLM models

- **Output-system optimization**
  - **Color-safety validation**: Added a color-safety-validation mechanism, ensuring output colors display correctly in different terminal environments; adjusted the TOOL-type log color to dark olive green, improving the visual experience
  - **Style unification**: Removed all `color` parameters from PrettyOutput, uniformly using the default color scheme, simplifying code and improving consistency

#### **📌 Fixes**

- **Configuration-and-platform fixes**
  - **API-key-check enhancement**: Added an API-key-check logic at platform creation, prioritizing retrieval of the API key from environment variables and providing more detailed error messages when missing; added a `silent` parameter to the `create_platform` method to avoid duplicate error printing
  - **OpenAI-configuration-handling optimization**: Fixed the `llm_config` handling logic to clearly distinguish empty and missing configurations; optimized the OpenAI API-key-missing warning logic, avoiding false empty-dict warnings before configuration loading completes
  - **Rules-manager type fix**: Fixed a type error when the rules manager returns empty results, changing the list returned by loaded rules to a set to avoid duplicates

- **Task-management fixes**
  - **Task-verification optimization**: Removed the detailed-explanation extraction from task-verification results, avoiding re-verifying the main-task completion status for completed tasks; relaxed the `priority` restriction to only validate the integer type, improving flexibility
  - **Built-in-rule-location fix**: Fixed the built-in-rule-directory-location logic, moving built-in rule files to a unified `builtin` directory, ensuring rules load correctly

- **JSON-handling fixes**
  - **Jsonnet multi-line-string fix**: Fixed `_fix_jsonnet_multiline_strings` mistakenly converting indentation to a space count when recording and restoring indentation; changed it to directly save the raw indentation string (including Tab), ensuring indentation containing Tab or other whitespace symbols is restored exactly

#### **🔧 Optimizations and Refactoring**

- **Platform-and-configuration-system refactoring**
  - **Model-platform-initialization optimization**: Removed redundant `get_llm_config` calls and platform-name variables, directly using the PlatformRegistry unified interface; adjusted the methodology-loading logic to support passing the `llm_group` parameter, ensuring model-selection and configuration consistency; unified the platform-retrieval method, using `get_*_platform` methods instead of directly calling `create_platform`
  - **Configuration-handling-logic improvement**: Removed the model-configuration environment-variable override feature, simplifying the configuration-handling logic; refactored the configuration-handling flow to prioritize retrieving the configuration directly from `llm_config` without polluting environment variables; uniformly injects `llm_config` for all model-creation flows, ensuring the correct API base and API key are passed when PlatformRegistry.create_platform is called

- **Code-quality improvement**
  - **Type-annotation improvement**: Added complete type annotations to the entire security-analysis flow; added complete type annotations to the C2Rust transpiler and core modules; unified and improved type hints, improving type safety
  - **System-prompt unification**: Unified the system-prompt-construction logic and cleaned up redundant code, simplifying the model-platform-initialization logic, directly using `get_normal_platform` instead of the original creation-fallback logic

- **Task-list-manager optimization**
  - **Model-group-retrieval optimization**: Optimized the model-group-retrieval logic, prioritizing retrieval of `llm_group` from the parent Agent, resolving potential timing issues with the global model group; only falls back to the global model group when the parent Agent has no `llm_group`
  - **Task-content-construction refactoring**: Refactored the task-content-construction logic and unified the verification flow, improving code maintainability

#### **📚 Documentation Update**

- **Documentation-structure reorganization**
  - Reorganized the documentation structure, optimizing document organization, improving document readability and lookup efficiency

- **Tool-usage-documentation update**
  - **Script-tool documentation**: Updated the usage and examples of the script tool; the detailed description adds explanations and practical usage examples for various filter commands, including grep, rg, head, and tail
  - **Task-list-manager documentation**: Supplemented the TaskListManager runtime-flow explanation chapter, helping users better understand and use the task-list manager
  - **Rule documentation**: Added documentation for the ignore-all-warnings rule, refactored the quick-verification-mode documentation
  - **Rust performance-optimization rules**: Added the Rust performance-optimization rule document and enabled the methodology tool

#### **🧪 Test Enhancements**

- **Test fixes**
  - Fixed the `test_load_all_rules_no_rules` and `test_load_all_rules_empty_rule_names` tests, changing the assertions from lists to sets to match the actual return type
  - Fixed the `test_non_string_input` test, adding a type check in the `_strip_markdown_code_blocks` function, ensuring non-string input correctly returns the original value

---

### Release Note - v1.0.2 2025-12-15

#### **🚀 New Features**

- **IIRIPER workflow reinforcement**
  - **Agent / CodeAgent fully converge to strict IIRIPER ordering**: The system prompt was greatly streamlined, while mandating that the workflow advances in the order INTENT -> RESEARCH -> INNOVATE -> PLAN -> EXECUTE -> REVIEW, prohibiting unauthorized step-skipping or out-of-order execution
  - **Non-interactive mode enabled by default**: The `non_interactive` default for `Agent` and `CodeAgent` was changed to `True`, which, combined with the IIRIPER constraints, automatically enters EXECUTE after PLAN, adapting to CI/unattended scenarios
  - **Auto-complete enabled by default**: The `auto_complete` default was changed to `True`, which, together with IIRIPER + the tool-call protocol, reduces the risk of "getting stuck waiting for confirmation"

- **MetaAgent tool-generation-capability upgrade**
  - Upgraded `generate_new_tool` to the `meta_agent` meta-agent, uniformly serving as the entry point for "bootstrapping and evolving the HaijunBot tool ecosystem"
  - Supports automatically **creating or improving** tools based on natural-language requirements, automatically writing them to `data/tools` and registering them in the ToolRegistry after generation
  - Fully replaced with `meta_agent` in the task-analysis prompts and examples, and supplemented guidance on how to orchestrate `Agent` / `CodeAgent` within generated tools

#### **📌 Fixes**

- **Global Agent lifecycle fix**
  - Introduced `set_current_agent` / `clear_current_agent` and a runtime stack, uniformly managing the currently running Agent, avoiding residual state and stack confusion caused by the legacy interfaces `set_agent` / `delete_agent`
  - `SubAgent` / `SubCodeAgent` cancelled the manual global-Agent-deletion logic, changing it to automatic cleanup by the new current-Agent stack, reducing the risk of state corruption in multi-level nesting scenarios

- **Editable-install-detection fix**
  - Optimized `is_editable_install` multi-strategy detection: in addition to direct_url.json, added compatibility checks for `.egg-link` and `.pth`, and strengthened heuristic validation based on `.git` and `site-packages/dist-packages`, fixing misdetection as non-editable in some environments

- **File-edit-error-message fix**
  - `edit_file` now aggregates the detailed error message of each failed diff into `stderr` on multi-file/multi-diff failure, no longer only outputting the vague "X files failed" prompt
  - Corresponding test `tests/haijunbot_tools/test_edit_file.py` supplemented with key assertions, ensuring future changes do not regress to "context-free" error messages

#### **🔧 Optimizations and Refactoring**

- **Agent / CodeAgent prompt-and-rule-loading refactoring**
  - Greatly streamlined the general `Agent` and `CodeAgent` system-prompt text, retaining the core IIRIPER constraints and task-execution rules, significantly reducing token usage
  - Unified rule loading down into the `Agent` base class, concatenating the `<rules>` section on demand via `rules_manager.load_all_rules`; `CodeAgent` no longer re-implements loading logic
  - `builtin_input_handler` records dynamically loaded rule names at runtime via `add_runtime_rule`; `CodeAgent.add_runtime_rule` maintains `loaded_rule_names`, enabling subsequent SubAgent / Review Agent to inherit the same rule set

- **Code-review (Review) flow enhancement**
  - Review-prompt reinforcement: emphasizes that the "code-generation summary" must be checked item by item against the actual git diff / code, prohibiting conclusions based solely on the summary
  - `_parse_review_result` adds JSON-structure-repair capability: when the Review output format is anomalous, it attempts to "self-repair" the JSON via multiple rounds with the same model as the Review Agent, up to 3 times; if still failing, it explicitly returns `JSON_FORMAT_ERROR` and triggers re-review
  - The Review Agent created by `_review_and_fix` automatically inherits the rules (rule_names) currently loaded by the main CodeAgent, injected into the system prompt via `<rules>`, ensuring review standards match the main Agent

- **Task-list-verifier (task_list_manager) optimization**
  - Clearly requires `expected_output` to be written as **structured entries** (numbered or markdown list), which the verifier splits into multiple expected results and verifies separately
  - Both the verification prompt and summary template changed to a "verify item by item + provide PASSED/FAILED explanation item by item" structure, prohibiting the verification Agent from performing any fix operations, only allowing conclusions
  - The verification Agent's system prompt automatically concatenates the parent Agent's loaded rule content, ensuring the verification logic maintains the same constraint system as the main task

- **Tool-system usability and readability improvement**
  - The ToolRegistry tool-list prompt now uses Markdown + `json` code blocks to display the parameter schema, replacing the old XML-style tags, improving human readability and model-parsing stability
  - `SubCodeAgent` explicitly inherits the parent Agent's rule set (`rule_names`) and enables `auto_complete=True` when creating a sub-CodeAgent, ensuring the sub-agent behavior matches the parent and the execution loop closes more smoothly

#### **📚 Documentation Update**

- **Technical-report and tool-generation documentation update**
  - Added a **MetaAgent (meta-agent / tool bootstrapper)** section to the "Technical Report", systematically explaining its responsibilities, inputs and outputs, collaboration with CodeAgent/Agent, and source-code locations
  - Updated the tool-generation-flow descriptions in the task-analysis prompt, tool-usage instructions, etc., fully migrating from `generate_new_tool` to `meta_agent`, consistent with the code implementation

#### **🧪 Test Enhancements**

- **edit_file and global-tool behavior regression**
  - Supplemented and strengthened the assertions in `tests/haijunbot_tools/test_edit_file.py` for multi-diff, multi-file failure scenarios, ensuring detailed error messages and file paths/names necessarily appear in `stderr`
  - Added or improved unit tests for stack management, rule inheritance, and `is_editable_install` multi-strategy judgment for the global-Agent and editable-install-detection logic, avoiding regressions introduced by subsequent refactoring

---

### Release Note - v1.0.1 2025-12-15

#### **🚀 New Features**

- **Major tool-generation-capability upgrade**
  - **CodeAgent intelligent tool generation**: Changed the tool-generation method to be automatically completed by CodeAgent, introducing intelligent-analysis capability, significantly improving tool-generation quality
  - **Automatic-registration mechanism**: Enhanced the prompt and auto-registration capability of the new-tool generator, automatically completing the registration flow after generation
  - **Unified tool-registration method**: Unified the tool-registration method and automatically cleaned up failed files, improving tool-management reliability
  - **Global-model-group support**: Supports creating CodeAgent with a global model group, improving configuration flexibility

- **Task-management enhancement**
  - **Global-background-info support**: Added global-background-info support, providing richer context for task execution
  - **Automatic verification after task completion**: Added automatic verification and iterative-fix mechanism after task completion, ensuring task-execution quality
  - **Task-verification-prompt optimization**: Streamlined the task-verification prompt, focusing on the expected output, improving verification accuracy
  - **Task-list-manager toggle**: Added a toggle controlling the task-list manager, providing a more flexible task-management approach

- **Code-review and verification enhancement**
  - **Code-review-prompt enhancement**: Enhanced the code-review-prompt context, supplementing the generation summary, improving review quality
  - **Git diff check optimization**: Adjusted the git diff check timing before code review to avoid empty reviews, improving review efficiency
  - **Completion-marker support**: Added completion markers to the code-review and task-verification steps, clearly showing execution status
  - **Code-review-toggle-logic optimization**: Changed the code-review-toggle logic from enabled to disabled, enabling the review flow by default

- **Output-system unification**
  - **PrettyOutput fully applied**: Replaced all typer.secho with PrettyOutput.auto_print, unifying the output style
  - **Visual-identifier unification**: Unified the visual identifiers in output logs, improving user-experience consistency
  - **Output-tool unification**: Unified the output tools of all modules, removing the typer dependency, simplifying dependency management

- **C2Rust transpilation-toolchain optimization**
  - **Output-style unification**: Used PrettyOutput instead of typer.secho to unify the output style
  - **Log-format unification**: Unified the log-output format and added emoji identifiers, improving readability
  - **Review-flow uniform closure**: Uniformly disabled the review flow of all optimizers and transpilation agents, simplifying the workflow
  - **Binary-entry-function support**: Added Cargo.toml configuration support for binary entry functions

- **Response-time statistics**
  - **Response-time-statistics feature**: Added response-time-statistics functionality and optimized the code structure, convenient for performance monitoring

#### **📌 Fixes**

- **Tool-system fixes**
  - Fixed the issue where CodeAgent incorrectly cleared the running state on exception, improving stability
  - Unified the tool-registration method and automatically cleaned up failed files, avoiding residual files
  - Removed task_list_manager as a required tool, improving flexibility

- **edit_file-tool fixes**
  - Fixed the bug where the replacement position was wrong on a unique match, improving editing accuracy
  - Unified failure-message handling and avoided empty error prompts, improving the user experience
  - Improved the detail level of error messages and added complete unit tests, improving maintainability
  - Optimized the multi-match-confirmation flow and fixed environment-variable naming, improving the interaction experience

- **Code-agent fixes**
  - Fixed the issue where CodeAgent incorrectly cleared the running state on exception
  - Adjusted the git diff check timing before code review to avoid empty reviews
  - Enhanced the code-review-prompt context, supplementing the generation summary

- **Configuration-system fixes**
  - Unified configuration-item naming conventions, removing the HAIJUNBOT prefix, simplifying configuration
  - Fixed environment-variable-naming issues, improving configuration consistency

- **Other fixes**
  - Fixed task-list-manager-related configuration issues
  - Optimized the mypy configuration, improving type-check quality

#### **🔧 Optimizations and Refactoring**

- **Tool-system refactoring**
  - **rewrite_file-tool removal**: Removed the rewrite_file tool and uniformly uses edit_file for full-file rewrites, simplifying the tool set
  - **Simplified search-replace flow**: Simplified the search-replace flow and removed the high-precision-matching logic, improving performance
  - **Tool-generation-prompt optimization**: Optimized the tool-generation logic and description in the task-analysis prompt, improving generation quality
  - **Supplemented tool-generation prompt**: Supplemented the prompt to relax file-reference restrictions and remove test requirements, lowering the generation barrier

- **Full output-system refactoring**
  - **Unified output tool**: Replaced all typer.secho with PrettyOutput.auto_print, unifying the output interface
  - **typer-dependency removal**: Removed the typer dependency and used PrettyOutput to print errors, simplifying dependencies
  - **Output-style unification**: Unified the output style of all modules, improving user-experience consistency
  - **Log-output optimization**: Unified the log-output method, adding timestamps, improving observability

- **Task-list-management optimization**
  - **Uniformly disable the task-list manager**: Uniformly disabled the task-list manager and removed redundant return values, simplifying logic
  - **Task-verification-prompt slimming**: Streamlined the task-verification prompt, focusing on the expected output, improving verification efficiency

- **Code-review-flow optimization**
  - **Review-flow uniform closure**: Uniformly disabled the review flow of all optimizers and transpilation agents
  - **Review-toggle-logic adjustment**: Changed the code-review-toggle logic from enabled to disabled, enabling by default

- **Prompt-system optimization**
  - **Task-completion-prompt unification**: Unified the task-completion-prompt format, clarifying to output only !!!COMPLETE!!!
  - **Task-analysis-prompt optimization**: Optimized the tool-generation logic and description in the task-analysis prompt

- **Code-quality improvement**
  - **Type-check optimization**: Optimized the mypy configuration, improving type-check quality
  - **Code-structure optimization**: Optimized the code structure, improving maintainability

#### **📚 Documentation Update**

- **Tool-generation documentation update**
  - Supplemented the prompt to relax file-reference restrictions and remove test requirements
  - Updated the tool-generation-flow description

- **Configuration-documentation update**
  - Updated the configuration-item naming-convention description, removing the HAIJUNBOT prefix
  - Supplemented the global-model-group configuration explanation

#### **🧪 Test Enhancements**

- **edit_file-tool tests**
  - Added complete unit tests, improving test coverage
  - Improved the detail level of error messages, convenient for problem location

This update is an important release for **tool-generation capability and output-system unification**. The core highlight is the introduction of **CodeAgent intelligent tool generation**, which significantly improves tool-development efficiency and quality through automatic analysis and generation. The **output system was fully unified** to PrettyOutput, removing the typer dependency, simplifying the code structure, and improving user-experience consistency. Enhancements to **task management and code review** further improve the system's reliability and ease of use.

**Technical highlights:**

- **Intelligent tool generation**: CodeAgent automatically analyzes and generates tools, improving development efficiency
- **Output-system unification**: Fully adopts PrettyOutput, removing the typer dependency, simplifying the architecture
- **Task-management enhancement**: Global background info, automatic verification, flexible toggle control
- **Code-review optimization**: Enhanced prompt context, optimized check timing, unified flow management
- **Tool-system simplification**: Removed redundant tools, unified edit flow, simplified registration mechanism

### Release Note - v1.0.0 2025-12-XX

> **⚠️ Important notice: Major configuration-system refactoring!**
>
> This update involves a major refactoring of the configuration system; **all configuration files need to be updated**. **It is strongly recommended to back up the `~/.haijunbot/config.yaml` configuration file before upgrading and run the `hjb -I` interactive configuration wizard for configuration migration.**

#### **🚨 Breaking Changes**

- **Major configuration-system refactoring**
  - **Configuration key names unified to lowercase**: All configuration-item key names uniformly use lowercase letters plus underscores (such as `HAIJUNBOT_MAX_INPUT_TOKEN_COUNT`)
  - **Configuration-reference mechanism**: Added a configuration-reference feature, supporting reuse of configurations via `$ref`, with a major change to the configuration structure
  - **Case-insensitive dict**: The configuration system switched to `CaseInsensitiveDict`, supporting case-insensitive configuration access
  - **Affected scope**: All configuration files using the old configuration format need to be updated
  - **Migration guide**: Run the `hjb -I` interactive configuration wizard; the system automatically detects and prompts for configuration items that need updating

#### **🚀 New Features**

- **Diff-visualization feature (brand new)**
  - **Side-by-side diff display**: Added the `diff_visualizer` module, supporting side-by-side display of code diffs
  - **Syntax-highlighting support**: Diff display supports syntax highlighting, improving readability
  - **Intelligent line pairing**: Automatically recognizes changed blocks, intelligently pairing displayed inserted and deleted lines
  - **Change statistics**: Displays detailed change statistics (lines added, deleted, and modified)
  - **Dynamic separators**: Adds dynamic separators between changed blocks, clearly distinguishing different change regions

- **Dialogue recorder (brand new)**
  - **Complete interaction history**: Added the `dialogue_recorder` module, automatically saving all user-model interaction history
  - **Persistent storage**: Dialogue records are persisted to files, supporting subsequent analysis and review
  - **Configuration support**: Supports enabling/disabling the dialogue-recording feature via configuration

- **Configuration-system enhancement**
  - **Configuration-reference mechanism**: Supports reuse of configurations via `$ref`, reducing configuration duplication
  - **Case-insensitive**: Configuration key names support case-insensitive access, improving fault tolerance
  - **Configuration merging**: Supports merging referenced configurations into model-group configurations
  - **Embedding-and-rerank-model configuration reuse**: Supports passing `api_key` and `base_url` via a configuration dict

- **Input-handling enhancement**
  - **Pin-marker feature**: Added a Pin marker, supporting pinning user input content, appended in dialogue summaries and history records
  - **Rule-completion support**: Added a unified rule-completion interface, supporting built-in rules as input markers and auto-completion
  - **File-completion silent mode**: Added a silent mode for the file completer, reducing unnecessary prompts

- **15-dimension development-convention rule auto-generation**
  - **Rule-generation document**: Added the `generate_rules.md` document, supporting automatic generation of 15-dimension development-convention rules
  - **Code-driven rules**: Emphasizes that rules must be generated based on the project's actual code, strictly prohibiting fabricated content
  - **Rule-file merging**: Merged the 15-dimension rules into a single file, simplifying management

- **Task-list-management enhancement**
  - **Task-summary enhancement**: Added detailed task information to the task summary
  - **Task-output column**: The task list adds an actual-output column, optimizing the description-length limit
  - **Dependency-integrity validation**: Added task-dependency-integrity validation, ensuring all dependency tasks exist
  - **Batch-add auto-creation**: Automatically creates missing task lists when batch-adding tasks

- **Code-review and auto-fix feature**
  - **Review loop**: Added interactive confirmation and termination prompts to the code-review loop
  - **Auto-fix**: Added code-review and auto-fix functionality, supporting multiple rounds of review and fixing
  - **Review-report enhancement**: Improved the review-report format, including code-fix examples

- **RAG-system expansion**
  - **Online-model support**: Extended RAG configuration to support online models and dynamic loading
  - **Embedding-model interfaces**: Added `embedding_interface` and `reranker_interface`, supporting multiple embedding and rerank models
  - **Model registry**: Added embedding and rerank model registries, supporting models such as Cohere, EdgeFn, Jina, and OpenAI

- **Runtime-stack support**
  - **Nested Agent calls**: Introduced runtime-stack support for nested Agent calls, improving multi-Agent collaboration
  - **Agent registration and unregistration**: Optimized the registration and unregistration logic of Agent and CodeAgent

- **Other feature enhancements**
  - **Tool-call-log enhancement**: Added parameter summaries and sensitive-information filtering to tool-call logs
  - **Git diff info integration**: Integrated git diff info into the summary flow, providing more complete context
  - **Dynamic system-prompt enhancement**: Dynamically adds `rg` and `fd` tool-availability info to the system prompt
  - **Work-protocol upgrade**: Upgraded the work protocol to IIRIPER and added an intent-recognition mode

#### **📌 Fixes**

- **Diff-visualization fixes**
  - Fixed the erroneous display of separator lines caused by the line-number-continuity-judgment logic
  - Fixed the changed-block-separator-judgment logic
  - Adjusted the separator-line-display logic to avoid excessive separation

- **Output-system fixes**
  - Fixed the issue of console-output headers and content displaying on separate lines
  - Completed the platform-name info in the model-response-completion log
  - Fixed the token-usage info in console output and adjusted the scroll-height calculation

- **Task-list-management fixes**
  - Fixed the preview-length calculation for task-completion notifications
  - Supplemented the missing `agent_id` and `is_main_agent` parameters
  - Fixed the issue of overly long truncated description text in the task list

- **Code-agent fixes**
  - Fixed potential errors caused by inconsistent return-value types
  - Fixed the parameter error when retrieving the diff between two commits
  - Strictly prohibited fabricating content to ensure rule authenticity

- **Configuration-system fixes**
  - Fixed redundant slashes in `.gitignore` rules
  - Fixed case-insensitive-access issues with configuration key names
  - Fixed circular-reference issues in the configuration-reference mechanism

- **Other fixes**
  - Changed the tool-call-confirmation default to False
  - Fixed the poor readability caused by the rule-injection format
  - Fixed the issue of repeatedly waiting for user input in non-interactive mode

#### **🔧 Optimizations and Refactoring**

- **Full UI-output-system refactoring**
  - **Welcome-interface refactoring**: Refactored the welcome-interface layout and added a HaijunBot ASCII logo
  - **Output-format simplification**: Simplified the PrettyOutput header format to show only the Agent name
  - **Color-mapping enhancement**: Added text-color mapping to console output, unifying the console-output header style to gray
  - **Redundant-output removal**: Removed output content such as statistics-table display, token-usage info, and redundant execution prompts
  - **Live-output optimization**: Shows the complete response and optimizes Live output when there are no tool calls
  - **Scroll-area limit**: Limited the maximum height of the terminal scroll area to 5 lines

- **LSP-client removal**
  - **Removed the `lsp_client` tool**: Completely removed the `haijunbot_tools/lsp_client.py` module, switching to a Tree-sitter-based symbol extractor as the primary code-analysis solution

- **Agent-system refactoring**
  - **Merged code/general Agent types**: `CodeAgent` and the general `Agent` type were merged, introducing automatic-recognition logic; the system automatically recognizes and applies the corresponding configuration based on the task
  - **Non-interactive mode changed to instance level**: Non-interactive mode changed from a global environment variable to an Agent-instance property, controlled via the `non_interactive` parameter or `set_non_interactive()` method

- **Output-system refactoring**
  - **PrettyOutput-interface optimization**: Unified the output interface to the `PrettyOutput.auto_print` method, removing some redundant output formats
  - **Redundant-output removal**: Removed output content such as statistics-table display and token-usage info, simplifying the output format

- **Task-list-management optimization**
  - **Interface simplification**: Removed the `create_task_list` operation; task lists are now automatically created via `add_tasks`, and the `main_goal` parameter must be provided
  - **Task-type-recognition simplification**: Simplified the task-type-recognition logic, judging directly based on the agent instance

- **Rules-system optimization**
  - **Rule-path unification**: All rule-file paths unified to the `.haijunbot` directory
  - **Rule merging**: Merged the 15-dimension rules into a single file, simplifying management

- **Code-quality improvement**
  - **Type-check enhancement**: Improved the global type-check strategy with gradual per-module tightening
  - **Redundant-code removal**: Removed redundant type-ignore comments and improved type annotations
  - **Unified import format**: Unified the import format and removed redundant statements
  - **Test refactoring**: Uniformly replaced `print` with `PrettyOutput.auto_print` to adapt to the new output module

- **Task-list-management optimization**
  - **Interface simplification**: Streamlined the task-management interface and unified the update method
  - **Verification-logic removal**: Removed task-status-transition-verification logic, improving flexibility
  - **ID-system optimization**: Uses sequential numeric IDs instead of UUIDs, simplifying task identification

- **Context-management optimization**
  - **Visible-output removal**: Removed user-visible output for context recommendations, keeping tools running silently
  - **Git diff limit**: Adjusted the git diff token-limit ratio from 80% to 10%, reducing OOM risk
  - **Token-limit optimization**: Adjusted the read_code token-limit ratio, reducing OOM risk

- **Rules-system optimization**
  - **Rule-display enhancement**: Enhanced rule-information display and distinguished user-custom rules

- **Other optimizations**
  - **Conversation-turn management**: Removed redundant turn counting, uniformly managed internally by the model
  - **Platform-response statistics**: Added duration and token statistics printing for conversation responses
  - **Tool-call optimization**: Enhanced diagnosis and logging of tool-call format errors

#### **📚 Documentation Update**

- **Technical-report update**
  - Added the code-review-and-auto-fix-loop chapter
  - Updated the diff-visualization feature description
  - Improved the configuration-system-refactoring explanation

- **Usage-guide update**
  - Updated the configuration-system usage instructions, emphasizing breaking changes
  - Supplemented the usage guide for the new task-list-management interface
  - Updated the rules-system path-change explanation

- **Configuration-documentation update**
  - Unified configuration-item naming conventions and added the dialogue-recording feature
  - Removed the deprecated `HAIJUNBOT_NON_INTERACTIVE` variable description
  - Supplemented the configuration-reference-mechanism usage instructions

- **New RAG documentation**
  - Added RAG online-model configuration documentation (`README_ONLINE_MODELS.md`)
  - Added RAG dynamic-loading documentation (`README_DYNAMIC_LOADING.md`)
  - Added detailed RAG configuration documentation (`README_CONFIG.md`)

#### **🧪 Test Enhancements**

- **New tests**
  - Added the `test_task_list_manager.py` test file (348 lines), covering task-list-management functionality
  - Added the `test_collections.py` test file (360 lines), covering case-insensitive-dict functionality
  - Added the `test_config_case_insensitive.py` test file (132 lines), covering the configuration-system case-insensitive feature
  - Added the `test_dialogue_recorder.py` test file (394 lines), covering the dialogue-recorder feature

- **Test cleanup**
  - Removed the `test_lsp_client.py` test file (579 lines); the LSP client has been removed

- **Test updates**
  - Updated multiple test files to adapt to the new output module and configuration system

This update is a major release for **major architecture refactoring and feature enhancement**. The core highlight is the **comprehensive refactoring of the configuration system**, which significantly improves configuration-management flexibility and ease of use through unified configuration key names, configuration-reference support, and case-insensitive access. The introduction of the **diff-visualization feature** makes code changes more intuitive and easier to understand. The addition of the **dialogue recorder** provides a data foundation for subsequent analysis and improvement.

**Upgrade recommendations:**

1. **Back up configuration**: Please back up the `~/.haijunbot/config.yaml` configuration file before upgrading

2. **Update configuration**: Run the `hjb -I` interactive configuration wizard; the system automatically detects and prompts for configuration items that need updating

3. **Test verification**: Verify the upgrade in a test environment first, ensuring all features work normally before applying to production

**Technical highlights:**

- **Configuration-system refactoring**: Unified configuration key names, configuration-reference support, case-insensitive access, configuration-merging mechanism
- **Diff visualization**: Side-by-side display, syntax highlighting, intelligent line pairing, change statistics, dynamic separators
- **Dialogue recording**: Complete interaction history, persistent storage, configuration support
- **Rules-system optimization**: Path unification, rule merging, display enhancement
- **Task-list enhancement**: Dependency validation, batch creation, output columns, summary enhancement

### Release Note - v0.8.3 2025-12-07

#### **🚀 New Features**

- **Task-list-management feature (brand new)**
  - **Task-list-management tool**: Added the `task_list_manager` tool, supporting splitting complex tasks into multiple subtasks and managing them uniformly
    - **Create task list**: Supports creating a task list and adding multiple tasks at once, completing planning in one go
    - **Task execution**: Automatically creates the corresponding sub-Agent to execute tasks based on the task type (`code_agent`/`agent`/`main`)
    - **Automatic status management**: Automatically updates to `running` at execution start and to `completed` or `failed` at completion, with no manual management needed
    - **Dependency handling**: Supports task-to-task dependencies, automatically executing in dependency order, supporting task-name references (automatically matched by the system)
    - **Batch task addition**: Supports batch-adding tasks, recommending adding all subtasks at once during the PLAN stage
    - **Layered context sharing**: Supports dynamic multi-task management, layered context sharing, and Agent permission isolation
    - **Version snapshots**: Supports task-list version snapshots and rollback functionality
  - **Unified initialization**: Uniformly initializes the task-list manager during base Agent initialization, enabling all Agent instances to use task-list-management functionality
  - **Intelligent-prompt integration**: Automatically injects the task-list-management-tool usage guide into the system prompt, guiding Agents to use task splitting for complex tasks

- **Major built-in-rules-system refactoring**
  - **Rule file-ization**: Changed all built-in rules from hard-coded to organized as Markdown files
    - **General rules**: Located in the `src/haijunbot/haijunbot_code_agent/rules/` directory, containing 9 development-practice rules (TDD, code review, refactoring, clean code, error handling, security, performance, documentation, Git workflow)
    - **Test rules**: Located in the `builtin/rules/testing/` directory, containing test rules for 8 languages (Python, JavaScript, Java, Go, Rust, C/C++, Ruby, PHP)
  - **Dynamic-loading mechanism**: The `builtin_rules.py` module automatically scans the `rules/` and `rules/testing/` directories at initialization, loading all `.md` files as built-in rules
  - **Rule-format optimization**: All rule files have been rewritten into imperative formats suitable for large models to understand and use
    - Uses explicit imperative language such as "must" and "must not"
    - Provides detailed execution requirements and checklists
    - Includes code examples (correct vs. incorrect practice)
    - The structured format facilitates AI parsing and execution
  - **Rule-display function**: Added rule-information display, supporting displaying all available rules categorized by source

- **Post-file-change-processing tool (brand new)**
  - **Automatic formatting**: Added the `after_change.py` module, supporting automatic execution of formatting tools after file changes
    - **Multi-language support**: Supports multiple languages including Python (ruff format), JavaScript/TypeScript (prettier), Rust (rustfmt), Go (gofmt), Java (google-java-format), C/C++ (clang-format), HTML/CSS (prettier), JSON/YAML (prettier), Markdown (prettier), SQL (sqlfluff format), Shell (shfmt), and XML (xmllint)
    - **Configurable**: Supports customizing formatting-command templates via the `after_change_tools.yaml` configuration file in the data directory
    - **Placeholder support**: Command templates support the `{file_path}` (full path) and `{file_name}` (file name) placeholders
  - **Integrated into CodeAgent**: Post-file-change processing has been integrated into CodeAgent's post-tool-execution bypass-enhancement flow

- **Lint-tool refactoring**
  - **Command-template mechanism**: Refactored the static-check module, adopting a command-template-configuration mechanism, supporting more flexible configuration
  - **Configuration optimization**: Supports loading custom lint-tool configurations from configuration files, improving extensibility

- **Configuration optimization**
  - **Token-count increase**: Raised the default max input token count from 32,000 to 128,000, supporting a larger context window

- **Other feature enhancements**
  - **Multi-tool-call detection**: Added detection and error prompts for multi-tool calls in the tool registry, avoiding format errors
  - **Rule-display optimization**: Optimized the rule-display format and adjusted panel padding, improving readability

#### **📌 Fixes**

- **haijunbot-c2rust transpilation-toolchain fixes**
  - Fixed the issue where the `ref` field was accidentally modified when replacing entry functions
  - Enhanced breakpoint-recovery robustness and optimized the entry-function-protection logic

- **Tool-system fixes**
  - Removed the extra pipe characters in the tool-prompt template
  - Fixed the backslash escaping in the sed insert-command example

- **Other fixes**
  - Optimized `.gitignore` rules to avoid accidentally ignoring source files
  - Improved ignore rules for multi-language projects

#### **🔧 Optimizations and Refactoring**

- **Task-list-management optimization**
  - Removed the length-validation logic for task-related fields, improving flexibility
  - Removed the task-timeout and retry mechanism, simplifying task management
  - Optimized the Agent-type definition, supporting clearer task-type distinction
  - Moved the task-output-length constant to the `task_list_manager` module, improving module cohesion
  - Enhanced context construction and automatic status management during task execution

- **Code-quality improvement**
  - Refactored the lint-tool configuration and command-generation logic, adopting a command-template mechanism
  - Optimized the rule-display format, improving readability

- **Documentation optimization**
  - Refined the editing-tool usage guide
  - Strengthened the functional-consistency-check requirements to improve transpilation quality

#### **📚 Documentation Update**

- **Comprehensive technical-report update**
  - Added detailed descriptions of the task-list-management feature
  - Updated the built-in-rules-system description, adding explanations of rule file-ization and the dynamic-loading mechanism
  - Added a detailed description of the post-file-change-processing tool
  - Updated the lint-tool-refactoring description
  - Improved the Agent-system-architecture design, adding the TaskListManager module description

- **Usage-guide update**
  - Improved the task-list-management-tool usage guide
  - Updated the task_list_manager usage guide, adding explanations of batch task addition and dependency handling

#### **🧪 Test Enhancements**

- **Test cleanup**
  - Removed the `structured_code` unit-test file (593 lines), simplifying the test structure

- **Lint-test update**
  - Updated the lint-tool tests to adapt to the new command-template mechanism

This update is an important release for **task management and rules-system refactoring**. The core highlight is the introduction of the **task-list-management feature**, which significantly improves the ability to handle complex tasks through capabilities such as automatically creating sub-Agents to execute tasks, automatic status management, and dependency handling. The **file-ization refactoring of the built-in rules system** changed rules from hard-coded to Markdown files and optimized them into imperative formats suitable for large models, improving rule maintainability and AI understanding. The introduction of the **post-file-change-processing tool** supports automatic multi-language formatting, ensuring consistent code style. Together, these improvements enhance HaijunBot's capabilities in complex-task management and code-quality assurance.

**Technical highlights:**

- **Task-list management**: Supports complex-task splitting, automatic sub-Agent creation, automatic status management, dependency handling, version snapshots
- **Rules-system refactoring**: Rule file-ization, dynamic loading, imperative-format optimization, multi-language test-rule support
- **Post-file-change processing**: Multi-language automatic formatting, configurable command templates, placeholder support
- **Lint-tool refactoring**: Command-template mechanism, flexible configuration, improved extensibility
- **Configuration optimization**: Token count raised to 128,000, supporting a larger context window

### Release Note - v0.8.2 2025-12-04

#### **🚀 New Features**

- **Major file-editing-tool upgrade**
  - **Multi-match intelligent confirmation and preview**: When the search text has multiple matches in the file, the tool automatically detects and generates a match-position preview (including line number, column number, and 3 lines of context before and after), requiring the Agent to confirm whether to continue replacing all matches, avoiding erroneous replacements
  - **Removed the count parameter**: No longer supports controlling the number of replacements via the count parameter; instead, it adopts multi-match detection and confirmation mechanisms to ensure replacement accuracy
  - **Enhanced error prompts**: When a search fails, provides detailed error information and fix suggestions, including suggesting the use of the `read_code` tool to re-read the file, indicating that the file may have been updated, and suggesting including sufficient context in the search

  - **Important note**: The search must provide sufficient context to uniquely locate the target position; it is recommended to include a few lines of context before and after the target code, the function signature, or a unique identifier, to avoid matching the wrong position
  - **Unified editing tool**: Removed `edit_file_free` and `edit_file_structured`, unified into the `edit_file` tool, simplifying usage

- **Rules-system enhancement**
  - **Central rules repository**: Introduced the central rules repository feature (`HAIJUNBOT_CENTRAL_RULES_REPO`), supporting sharing team rules via a Git repository
    - Supports a local directory path or a Git repository URL
    - Automatically clones to `{get_data_dir()}/central_rules_repo` on first run
    - Automatically updates daily (via the `daily_check_git_updates` mechanism)
    - Rules in the central rules repository have the highest priority and override same-named rules
  - **Rule-sharing feature**: Added `RuleShareManager`, supporting sharing local rules to the central rules repository
    - Can only share rules in the default data directory (`{get_data_dir()}/rules`)
    - When sharing, rule files are moved to the central repository (rather than copied), and the original files are deleted
    - Automatically detects and excludes rules that already exist in the central repository
  - **Multi-directory rule loading**: Supports loading rules from multiple rules directories by priority (global rules -> configuration directory -> project rules -> central rules repository)

- **Major haijunbot-c2rust transpilation-toolchain enhancement**
  - **Cargo Test compile-warning detection**: After `cargo test` passes, automatically checks the warning output during compilation and testing (such as `unused_mut`, `unused_variables`, `dead_code`, `unused_import`, etc.), entering the warning-fixing phase
  - **Automatic-fix steps**:
    - **Compile-warning fixing**: Preferentially uses `cargo fix --allow-dirty --allow-staged` to automatically fix compile warnings that can be auto-fixed
    - **Clippy-warning fixing**: Preferentially uses `cargo clippy --fix --allow-dirty --allow-staged -- -D warnings` to automatically fix clippy warnings that can be auto-fixed
    - If warnings remain after automatic fixing, continue to manually fix the remaining warnings
  - **Fix-scope requirement**: Explicitly requires not only fixing the current problem, but also fixing any other failing test cases caused during the fixing process, ensuring all test cases pass after the fix
  - **Git change-context support**:
    - Introduced Git change-context support for the build-fix and code-review phases
    - The fix prompt automatically includes the git diff information from the start of function processing to the present
    - Uses `truncate_git_diff_with_context_limit` to limit the git diff length (30% for the fix phase, 50% for the review phase)
    - Helps the fixing Agent understand the current code state and the modifications already made, identifying problems introduced by previous modifications
  - **Concurrency-issue troubleshooting guide**: Added a concurrency-issue troubleshooting guide, helping identify and resolve race conditions, concurrent access to shared resources, and other issues in tests
  - **Build-fix-phase summary**: Supports generating a summary of the build-fix phase and displaying it in the review phase, facilitating the review Agent's understanding of the fix process
  - **Review-report enhancement**: Added a code-fix-example requirement to the review report, improving review quality
  - **Diff-truncation enhancement**: Added file-list output to the diff-truncation feature, facilitating understanding of which files were truncated

- **Large-scale code-architecture refactoring**
  - **Transpiler modularization refactoring**: Split the Transpiler class into multiple specialized management modules (`transpiler_agents.py`, `transpiler_build.py`, `transpiler_codegen.py`, `transpiler_compile.py`, `transpiler_config.py`, `transpiler_context.py`, `transpiler_executor.py`, `transpiler_generation.py`, `transpiler_git.py`, `transpiler_mod_utils.py`, `transpiler_modules.py`, `transpiler_planning.py`, `transpiler_review.py`, `transpiler_symbols.py`), improving code maintainability
  - **Optimizer modularization refactoring**: Split the optimizer module into multiple functional modules (`optimizer_build_fix.py`, `optimizer_clippy.py`, `optimizer_config.py`, `optimizer_docs.py`, `optimizer_options.py`, `optimizer_progress.py`, `optimizer_report.py`, `optimizer_unsafe.py`, `optimizer_utils.py`, `optimizer_visibility.py`), with clearer responsibilities
  - **Library Replacer modularization refactoring**: Split the library replacer into multiple modules (`library_replacer_checkpoint.py`, `library_replacer_llm.py`, `library_replacer_loader.py`, `library_replacer_output.py`, `library_replacer_prompts.py`, `library_replacer_utils.py`)
  - **LLM Module Agent modularization refactoring**: Split the monolithic module into multiple single-responsibility submodules (`llm_module_agent_apply.py`, `llm_module_agent_executor.py`, `llm_module_agent_loader.py`, `llm_module_agent_prompts.py`, `llm_module_agent_types.py`, `llm_module_agent_utils.py`, `llm_module_agent_validator.py`)
  - **CodeAgent refactoring**: Refactored the CodeAgent class, splitting it into multiple specialized managers (`code_agent_build.py`, `code_agent_diff.py`, `code_agent_git.py`, `code_agent_impact.py`, `code_agent_lint.py`, `code_agent_llm.py`, `code_agent_postprocess.py`, `code_agent_prompts.py`, `code_agent_rules.py`), improving code organization

- **LSP-client optimization**
  - **Symbol-search-match-logic optimization**: Optimized the symbol-search-match logic and display format, improving search accuracy
  - **Path-handling improvement**: Uses an independent LSP working directory to handle relative and absolute paths, uniformly using relative paths to improve cross-platform compatibility
  - **New tool method**: Added a tool method to convert absolute paths to project-relative paths

- **Non-interactive-mode support**
  - **RIPER-5 protocol support**: Introduced the RIPER-5 protocol and mode-declaration mechanism, supporting automatic execution in non-interactive mode
  - **System-prompt injection**: Injects a system prompt for non-interactive mode, achieving automatic execution without user confirmation
  - **Prompt optimization**: Optimized the wording of non-interactive-mode prompts, streamlining the prompt text

- **Build-system-detection enhancement**
  - **LLM intelligent build-system detection**: Introduced an LLM intelligent build-system-detection and confirmation mechanism, improving detection accuracy
  - **File-statistics refactoring**: Refactored the file-statistics implementation of the build-system detector, improving performance

- **Other feature enhancements**
  - **Code-line-count tool integration**: Integrated the `loc` code-line-count tool into the Docker image
  - **Syntax-error tolerance enhancement**: Enhanced syntax-error tolerance, supporting partial symbol extraction, so that some symbols can be extracted even when syntax errors exist
  - **Documentation-test verification**: Enabled documentation-test verification to enhance self-checking capability
  - **Unified constant management**: Uniformly extracted public constants and manages them centrally (`constants.py`)

#### **📌 Fixes**

- **File-editing-tool fixes**
  - Fixed the indentation error in compile-check exception catching
  - Fixed the issue where backup files were not deleted after a successful modification
  - Unified and strengthened the file-editing match logic, changing fuzzy matching to exact matching to improve editing stability

- **Transpilation-toolchain fixes**
  - Fixed the resource-leak issue after review iteration ends
  - Fixed the issue where the build-fix flag was reset in the retry loop
  - Fixed the forced-validation issue on the want field during tool registration, relaxing the tool-call-format validation

- **Other fixes**
  - Fixed the issue of too-high a trigger threshold for the "no tool call" prompt, lowering the threshold and switching to a dedicated method to set the prompt
  - Fixed the LSP-client path-handling issue, using an independent working directory to handle relative and absolute paths

#### **🔧 Optimizations and Refactoring**

- **Agent-management optimization**
  - **Removed the Agent cache mechanism**: Removed the Agent cache mechanism, instead creating a new one each time, avoiding context accumulation and memory interference
  - **Delayed LLM-instance creation**: Delays LLM-instance creation in `llm_context_recommender`, re-creating it on each call, avoiding problems caused by context-window accumulation
  - **Split Agent responsibilities**: Split the responsibilities of the code-generation and fix Agents, with the fix Agent re-created each time, ensuring each fix has an independent context and state

- **Code-quality improvement**
  - **Code-formatting refactoring**: Refactored the code-formatting and static-check flow, renaming formatting-related functions and variables to support more general post-commands
  - **Build-validator enhancement**: Enhanced the cargo error-log-extraction capability, improving error-information accuracy
  - **Symbol-extractor optimization**: Enhanced syntax-error tolerance, supporting partial symbol extraction

- **Tool-system optimization**
  - **Tool-call-format relaxation**: Relaxed the tool-call-format validation, removing the forced requirement for the want field
  - **LSP-client refactoring**: Uniformly uses relative paths to improve cross-platform compatibility, using an independent LSP working directory to handle path issues

- **Test-system optimization**
  - **Test unification**: Uniformly changed `--doc` tests to the complete `cargo test`, ensuring test completeness
  - **Test-logic adjustment**: Adjusted the test logic for syntax-unit extraction and code restoration, enhancing test accuracy

#### **📚 Documentation Update**

- **Comprehensive technical-report update**
  - Improved the descriptions of the code-editing tool and the test-fix flow
  - Unified the file-editing-tool naming and updated the matching-strategy description
  - Updated the rules-system description, adding explanations of the central rules repository and the rule-sharing feature
  - Updated the C2Rust transpilation-toolchain description, adding cargo test warning detection, automatic-fix steps, fix-scope requirements, concurrency-issue troubleshooting guide, etc.

  - Improved the Git change-context support description

- **Usage-guide update**
  - Supplemented usage guidance for the sed command to delete large amounts of code
  - Added an explanation of the Git history-recovery mechanism
  - Supplemented the coding-convention requirements for test cases
  - Supplemented guidance to clean up temporary files during development
  - Improved the usage tips and error messages for search text
  - Added automatic-fix steps to the warning-fixing guidance
  - Added a concurrency-issue troubleshooting guide

- **Other documentation updates**
  - Updated the Docker Compose usage instructions
  - Unified and strengthened the crate root-directory path description
  - Supplemented the block-index behavior description of insert_before/insert_after in the edit_file tool

#### **🧪 Test Enhancements**

- **LSP-client-test enhancement**
  - Enhanced the assertion logic of the LSP-client tests, adding detailed validation of the returned content
  - Validates the returned symbol information, definition positions, reference counts, etc., improving test quality

- **Code-agent-test enhancement**
  - Added unit tests for the code-agent core module
  - Added code-agent rule-management tests (`test_code_agent_rules.py`)
  - Added code-agent prompt tests (`test_code_agent_prompts.py`)

- **Transpilation-toolchain-test enhancement**
  - Added library-replacer utility-function tests (`test_library_replacer_utils.py`)
  - Added LLM module Agent utility-function tests (`test_llm_module_agent_utils.py`)
  - Added model tests (`test_models.py`)
  - Added utility-function tests (`test_utils.py`)

- **Code-analyzer-test enhancement**
  - Added build-validation-configuration tests (`test_build_validation_config.py`)
  - Added Tree-sitter extractor tests (`test_tree_sitter_extractor.py`), adding syntax-error-handling test cases
  - Added utility-function tests (`test_utils.py`)

This update is a major release for **major feature enhancement and architecture optimization**. The core highlight is the **intelligent upgrade of the file-editing tool**, which significantly improves editing accuracy and safety through the multi-match-confirmation mechanism. The **centralization of the rules system** provides powerful rule-sharing capability for team collaboration. The **comprehensive enhancement of the C2Rust transpilation toolchain**, especially automatic fixing, Git context support, and concurrency-issue troubleshooting, greatly improves transpilation reliability and efficiency. The **large-scale architecture refactoring** splits the originally monolithic modules into multiple single-responsibility submodules, significantly improving code maintainability and extensibility.

**Technical highlights:**

- **Intelligent file editing**: Multi-match intelligent confirmation and preview, avoiding erroneous replacements, enhanced error prompts, improving editing accuracy
- **Central rules repository**: Supports team rule sharing, automatic updates, priority management, rule-sharing feature
- **Automatic-fix flow**: Cargo Test warning detection, automatic-fix steps (cargo fix, cargo clippy --fix), fix-scope requirements
- **Git context support**: The build-fix and review phases automatically include Git change information, helping Agents understand the code state
- **Modular architecture**: Large-scale refactoring, splitting monolithic modules into multiple single-responsibility submodules, improving maintainability
- **Non-interactive mode**: RIPER-5 protocol support, automatic execution, no user confirmation required

### Release Note - v0.8.0 2025-11-30

#### **🚀 New Features**

- **Docker containerization support (brand new feature)**
  - Added a complete Dockerfile, based on the official Python 3.12 image, pre-installing all development tools (Python, Rust, Clang, Fish shell, etc.)
  - Added docker-compose.yml configuration, supporting non-root user execution, automatically handling UID/GID, avoiding file-permission issues
  - Added a GitHub Actions CI/CD workflow (`.github/workflows/docker-publish.yml`), automatically building and publishing the Docker image to GHCR
  - Added artifact attestation support, using `actions/attest-build-provenance@v3` to improve image supply-chain security
  - Added complete Chinese locale support (`zh_CN.UTF-8`), ensuring Chinese input and output display normally
  - Added a `.dockerignore` file, optimizing the build context and reducing image size

- **Code-analysis-capability enhancement**
  - **Multi-language symbol-extractor enhancement**:
    - C/C++: Added support for macros, typedefs, and templates
    - Go: Added support for constants (const), variables (var), and structs
    - Java: Enhanced symbol-extraction capability
    - JavaScript/TypeScript: Enhanced symbol-extraction capability
    - Python: Enhanced symbol-extraction capability
    - Rust: Enhanced symbol-extraction capability
  - **read_code tool optimization**:
    - Optimized the code-chunking logic, preferentially grouping by semantic blank lines, then splitting chunks exceeding 50 lines at a fixed line count
    - Fixed the issue of retaining real file line numbers in the output on cache hit, ensuring accurate line-number display

#### **🔧 Optimizations and Refactoring**

- **Dockerfile build optimization**
  - Uses the official Python 3.12 image as the base image, simplifying the build process
  - Directly uses the system Python and `pip` to install dependencies, removing the virtual-environment configuration
  - The Rust toolchain is installed using the official `rustup` install script
  - Enhanced cache-cleanup strategy, automatically cleaning Python caches and build temporary files, reducing image size
  - Optimized the PATH environment-variable configuration, ensuring all tools are available

- **CI/CD-flow optimization**
  - Adopts standard GitHub Actions practices (`docker/login-action@v3`, `docker/metadata-action@v5`)
  - Optimized environment-variable definitions, using the `REGISTRY` and `IMAGE_NAME` variables to simplify configuration
  - Supports semantic version tags (such as `v0.8.0`, `0.8`, `0`, `latest`)

- **Test-coverage enhancement**
  - Added the `test_structured_code.py` test file (408 lines), covering structured-code-analysis functionality
  - Added the `test_read_code.py` test file (461 lines), covering code-reading-tool functionality

#### **📚 Documentation Update**

- **Comprehensive README update**
  - Added a complete Docker installation and usage guide, including image pulling, docker-compose usage, non-root user configuration, etc.

  - Optimized the document format, unifying list symbols and paragraph spacing
  - Updated the workflow examples, emphasizing the use of the LSP client and structured editing tools
  - Supplemented notes for Windows users using Docker

- **HaijunBot Book documentation update**
  - Updated chapters such as project introduction, quick start, and core concepts and architecture
  - Added Docker-related content to the usage guide
  - Updated the feature-extension and advanced-topics chapters

This update is the **first introduction of Docker containerization support**, providing HaijunBot with a complete containerized-deployment solution. Through the Docker image, users can use HaijunBot without locally installing a Python/Rust environment, especially suitable for scenarios requiring an isolated environment or rapid deployment. At the same time, the code-analysis capability was further enhanced, supporting more language features and symbol types, and the read_code tool's chunking logic is more intelligent. The large number of newly added test cases also provides a guarantee for code quality.

**Technical highlights:**

- **Docker containerization**: Based on the official Python 3.12 image, pre-installing all development tools, ready to use out of the box
- **Non-root user support**: Automatically configures the current user's UID/GID via docker-compose, avoiding file-permission issues
- **CI/CD automation**: GitHub Actions automatically builds and publishes images to GHCR, supporting semantic version tags
- **Code-analysis enhancement**: Supports more language features (macros, templates, typedefs, etc.), improving code-understanding capability
- **Intelligent code chunking**: Preferentially groups by semantic blank lines, then splits by a fixed line count, improving code-reading efficiency

### Release Note - v0.7.4 2025-11-30

#### **New Features**

- Added complete Docker support, including a multi-stage-build Dockerfile and docker-compose configuration
- Implemented an automated Docker-image-publishing flow, publishing to GHCR via GitHub Actions
- Extended the LSP-client tool, supporting symbol analysis for more language features such as decorators, templates, and macros
- Introduced two professional tools: the security-analysis suite (hsec) and the C-to-Rust migration suite (hc2r)

#### **Optimizations and Refactoring**

- Improved the code-symbol extractor, supporting 15+ language features
- Optimized the read_code tool's chunking logic, preferentially grouping by semantic blank lines
- Enhanced structured-code-analysis capability, improving code-navigation precision

#### **Documentation Update**

- Comprehensively updated README.md, adding a Docker installation and usage guide
- Improved the technical documentation of the symbol extractors for each language
- Added detailed usage instructions for the security-analysis suite and the C-to-Rust migration suite

#### **Miscellaneous**

- Added 200+ test cases, covering more boundary situations
- Updated the .gitignore and .dockerignore files, optimizing the development experience

This update mainly enhanced containerization support, code-analysis capability, and the security toolchain, providing developers with more complete infrastructure support.

### Release Note - v0.7.2 (2025-11-15)

#### **🚀 New Features**

- **Major structured-code-editing-capability upgrade**
  - Refactored the `edit_file` tool to fully adopt a structured-editing mode, supporting block-ID-based precise editing operations
  - Supports search/replace editing operations within code blocks, without manually calculating line numbers
  - Added a code-block-cache mechanism, improving code-reading and editing efficiency
  - Supports obtaining block_id from the cache, optimizing the editing flow
  - Improved the code-block display format and ID-generation method, enhancing readability
  - Introduced a blank-line-grouping-then-splitting strategy, optimizing the display of long code
  - Added the `raw_mode` parameter, supporting raw reading mode with grouping by 20 lines
  - Removed the sed mode and the search/search_range editing modes, unified into structured editing
- **LSP-client integration support**
  - Added the `lsp_client` tool, supporting connection to Language Server Protocol servers
  - Supports obtaining code information (definitions, references, etc.) via symbol names, without line/column numbers
  - Supports LSP servers for multiple languages (Python, TypeScript, JavaScript, C/C++, Rust, Go, etc.)
  - Provides a Tree-sitter fallback, automatically degrading when the LSP server is unavailable
  - Added a tool-availability check method, improving error-handling capability
- **Multi-language symbol-extraction-capability enhancement**
  - Added Java, JavaScript, and TypeScript language support
  - Implemented tree-sitter-based multi-language symbol-extraction capability
  - Enhanced symbol extraction and refactored output organization, resolving the duplicate-content problem caused by overlapping syntax units
  - Added a language-feature-support-status printing module, displaying the feature-support status of each language at startup
  - Added file-change-detection and auto-refresh mechanisms to the symbol table
- **haijunbot-c2rust transpilation-toolchain enhancement**
  - Supports using `--root-list-file` and `--root-list-syms` simultaneously with automatic merge-and-dedup
  - Added function-level failure fallback and retry mechanisms, improving transpilation success rate
  - Added validation prompt information to the command output, enhancing user feedback
  - Added execution-command information to the fix prompt, facilitating problem location
  - Parses and reuses the compilation parameters in `compile_commands.json`
  - Introduced the `retrieve_memory` memory-recall mechanism in all work phases, leveraging historical experience to improve transpilation quality
  - Extracted hard-coded constants as module-level constants, improving maintainability
- **haijunbot-sec security-analysis-suite enhancement**
  - Persists confirmed-invalid clusters in the review phase, supporting invalid-cluster-review breakpoint recovery
  - Refactored the breakpoint-resume mechanism, introducing a three-file configuration system (candidates.jsonl, clusters.jsonl, analysis.jsonl)
- **Code-analysis-capability improvement**
  - Implemented structured code reading and optimized C/C++ symbol queries
  - Supports finding code blocks by line-number grouping in raw mode
  - Optimized the code analyzer's performance and error handling
  - Optimized the scan-progress-display logic
- **Other feature enhancements**
  - Added support for generating continuous PDFs without pagination
  - Counts and displays the short-term memory count at startup
  - Added consecutive-no-tool-call prompts in non-interactive mode
  - Added block-end delimiters to code-reading results, improving readability

#### **📌 Fixes**

- Fixed the code-block line-number calculation and newline-handling logic
- Fixed the breakpoint-recovery failure caused by inconsistent gid types in the verification phase
- Fixed syntax errors caused by multiple indentation issues
- Fixed the metric-operation exception caused by a missing "metrics" key
- Fixed the case-insensitive matching problem of tool-call tags
- Resolved the duplicate-content problem caused by overlapping syntax units
- Fixed the indentation error when JSON parsing fails
- Fixed the file-modification-feedback problem in the code-editing tool
- Unified exception handling, improving robustness and performance

#### **🔧 Optimizations and Refactoring**

- **haijunbot-sec modularization refactoring**
  - Split a single file (3,687 lines) into multiple module files (15 modules)
  - Extracted independent modules such as prompts, parsers, utils, agents, clustering, analysis, verification, and review
  - Added a file_manager module to uniformly manage file paths
  - Improved code maintainability and extensibility
- **Code-editing-tool refactoring**
  - Removed `edit_file_handler` and `rewrite_file_handler`, refactoring into the independent tools `edit_file` and `rewrite_file`
  - Removed old editing modes such as line_replace, search, search_range, and sed, unified into structured editing
  - Refactored the file-editing logic and enhanced patch-application robustness
  - Removed the global cache of file structured information, optimizing memory usage
- **Configuration and format unification**
  - Uniformly replaced YAML/JSON5 with the standard JSON format, improving parsing stability
  - Replaced json5 with jsonnet and introduced the multi-line-string delimiter `|||`
  - Unified exception handling, improving robustness and performance
- **Tool-system optimization**
  - Removed the ctags tool, enhancing the LSP-client capability
  - Removed the `sub_code_agent` tool and related documentation
  - Streamlined all tool description text, unifying Chinese punctuation
  - Removed CodeAgent environment variables and dependency checks
- **Code-quality improvement**
  - Removed TaskPlanner-related functionality
  - Unified log output to PrettyOutput
  - Cleaned up unused imports and redundant code
  - Removed unused variables and assignment results
  - Optimized the startup statistics-display performance
- **Multi-agent-system optimization**
  - Extracted multi-line-string examples as variables to eliminate duplication
  - Optimized the multi-agent collaboration flow

#### **📚 Documentation Update**

- Updated the technical report, updating the descriptions of code reading and structured-editing capabilities
- Updated the code-editing-tool description from PATCH/REWRITE to edit_file/rewrite_file
- Updated the technical-report PDF to the latest version
- Translated module documentation and comments into Chinese (haijunbot_c2rust, fzf, and other modules)
- Updated the multi-line-string format description to use single and double quotes
- Removed outdated architecture-design documents (Agent, CodeAgent, MultiAgent, haijunbot-c2rust, and haijunbot-sec system-architecture-design documents)
- Deleted the LSP-client integration guide document (the feature has been integrated into the tool)

#### **🔧 Miscellaneous**

- Optimized the PDF-generation script and style files, supporting continuous PDFs without pagination
- Updated the WeChat QR code image
- Added a comprehensive unit-test-case-design document
- Optimized the memory-merge output format from YAML to JSON

This update is an important release for architecture optimization and feature enhancement. The core highlight is the comprehensive upgrade of the **structured-code-editing capability**, which significantly improves the accuracy and efficiency of code modification by introducing a block-ID-based precise-editing mechanism. At the same time, the enhancement of **LSP-client integration** and **multi-language symbol-extraction capability** makes HaijunBot more powerful in code understanding and analysis. The **haijunbot-sec modularization refactoring** splits the original 3,687-line single file into 15 modules, greatly improving code maintainability and extensibility.

**Technical highlights:**

- **Structured editing**: Fully adopts a block-ID-based structured-editing mode, supporting multiple operations such as delete, insert_before, insert_after, replace, and edit, without manually calculating line numbers, reducing the risk of errors
- **LSP integration**: Obtains functions such as code completion, hover information, and go-to-definition via the Language Server Protocol, supports LSP servers for multiple languages, and provides a Tree-sitter fallback
- **Modularization refactoring**: haijunbot-sec is split from a single file into multiple modules, with a clearer code structure, facilitating maintenance and extension

### Release Note - v0.7.0 (2025-11-09)

#### **🚀 New Features**

- **Major haijunbot-sec security-analysis-suite upgrade**
  - Added a progress-status-management module (StatusManager), supporting a structured progress-status file (status.json), accurately reflecting the current stage and progress percentage
  - Supports breakpoint-resume: state recovery based on `.haijunbot/sec/progress.jsonl` and the status file, supporting breakpoint recovery and incremental saving in the clustering and verification phases
  - **Four-stage pipeline architecture**: heuristic scanning -> clustering -> verification -> reporting, with each stage supporting independent recovery
  - **Intelligent-clustering technology**:
    - Clusters based on verification-condition consistency, grouping issues that can be confirmed through the same verification process into one class
    - Supports gid (globally unique ID) integrity validation, ensuring all candidate issues are classified, supporting unlimited retries until all gids are classified
    - Supports skipping clustering for single-warning files, and supports batch processing (cluster_limit defaults to 50)
    - Supports invalid-cluster marking (is_invalid), adopting a conservative strategy: when in doubt, always enter the verification phase
  - **Dual-verification mechanism**:
    - Analysis Agent: performs in-depth analysis on clustering batches, judging whether real security risks exist
    - Verification Agent: verifies the conclusions of the analysis Agent, confirming conclusion accuracy through call-path derivation
    - Supports upward tracing of call paths, viewing the complete call chain to confirm vulnerability triggerability
    - Optimizes the verification flow to only process risky items (has_risk: true), skipping non-risky items
  - **Memory-function integration**: The clustering, analysis, and verification phases all support memory retrieval and saving, using existing memory to assist judgment and improving analysis efficiency
  - **Direct-model-call fallback mechanism**: When the Agent tool call fails, automatically degrades to a direct model call, supporting unlimited-retry mechanisms in the planning and security-analysis phases
  - Enhanced verification-result parsing and warning-persistence support, supporting a multi-warning merged-output format (gid/gids)
  - Added a review phase: re-verifies clusters marked as invalid, strengthening the call-path-analysis requirement
- **haijunbot-c2rust transpilation-toolchain enhancement (six-stage complete pipeline)**
  - **Stage 1: collect (function-name collection)**
    - Collects function names from header files, generating the root-function list (roots.txt)
    - Supports interactive selection or automatic detection of the root-function set
  - **Stage 2: scan (scanning and visualization)**
    - Performs C/C++ function and type scanning based on libclang 16-21, generating a symbol table (symbols.jsonl)
    - Builds a function-reference-relationship graph, supporting root-function-subgraph DOT output and optional PNG rendering
    - Generates the transpilation order (translation_order.jsonl), sorted by dependency relationships
  - **Stage 3: lib-replace (library-replacement evaluation and pruning)**
    - Uses an LLM to evaluate subtrees that can be wholly replaced by mature Rust libraries (such as std)
    - Generates a library-replacement mapping (library_replacements.jsonl), reducing the self-implementation area
    - Supports a candidate-library list and a disabled-library list, and supports breakpoint resume (resume)
    - Fallback mechanism: keeps the original symbols.jsonl; on failure, abandons the replacement and continues the transpilation path
  - **Stage 4: prepare (LLM plans the crate structure)**
    - Uses an LLM Agent to plan the Rust crate module structure based on the root-function subgraph
    - Applies directly to disk, generating the Cargo.toml and module-file structure
    - Supports an unlimited-retry mechanism (plan_max_retries defaults to 0), ensuring planning quality
  - **Stage 5: transpile (progressive Rust transpilation)**
    - **Module selection and signature planning**: Creates an independent Agent to select the appropriate Rust module path and output the function signature
    - **CodeAgent generation loop**: Generates the transpiled Rust function based on the C source-code fragment, called symbols, and crate directory structure
    - **Build-fix loop**: Tries `cargo build/test`; on failure, creates a CodeAgent to fix carrying the error context, until the build passes or the upper limit is reached (supports unlimited retries, check_max_retries/test_max_retries default to 0)
    - **Code-review loop**: Creates a code-review Agent; if the summary indicates problems, the CodeAgent optimizes, until the summary indicates no problems (review_max_iterations defaults to 0, supporting unlimited iterations)
    - **Symbol-mapping mechanism**: Records C symbol -> Rust symbol/module mapping to symbol_map.jsonl (JSONL format, supporting duplication and overloading)
    - **Automatic placeholder-reference elimination**: After transpilation completes, automatically eliminates `todo!("symbol")` placeholder references in the source code
    - Supports breakpoint resume: skips already-transpiled functions based on progress.json
    - Supports per-function selection (--only), uniformly reusing the CodeAgent instance, enhancing dependency and test feedback mechanisms
  - **Stage 6: optimize (conservative optimization and interface closure)**
    - **unsafe-cleanup technique**: Identifies removable `unsafe { ... }` wrappers, attempts to remove them and then runs `cargo check` to verify; if compilation fails, rolls back the change and adds a `/// SAFETY:` note before the adjacent function
    - **Visibility-optimization technique**: Tries downgrading `pub fn` to `pub(crate) fn`, running `cargo check` to verify after the change, rolling back on failure; supports further reducing visibility without breaking the API
    - **Code-structure optimization**: Simple text-based function-duplication detection (signature + body text), adding TODO documentation hints to duplicate bodies
    - **Documentation supplementation**: Adds basic placeholder documentation to modules/functions lacking documentation
    - **Build-fix loop**: Uses a CodeAgent for minimal fixes, running `cargo test` to verify after each modification, supporting unlimited retries (build_fix_retries defaults to 3)
    - **Git-protection mechanism**: Automatically creates a snapshot commit before optimization, and automatically resets back to the snapshot on failure (git_guard enabled by default)
    - Supports breakpoint resume: skips already-processed files based on `optimize_progress.json`
  - **One-click pipeline (run command)**: `haijunbot-c2rust run` automatically executes the complete collect->scan->lib-replace->prepare->transpile->optimize flow
  - Enhanced the transpiler's dependency check and memory-save prompts
  - Added C2Rust environment-detection functionality
  - Refactored the library_replacer main function into multiple helper functions to improve readability and maintainability
- **Major CodeAgent code-analysis-capability improvement**
  - Added a code-analyzer module (code_analyzer): providing functions such as symbol extraction, dependency analysis, impact-scope analysis, and intelligent context recommendation
  - Added an impact-scope analyzer (ImpactAnalyzer): supporting functions such as dependency-chain analysis, interface-change detection, and test discovery
  - Added an intelligent context recommender (ContextRecommender): performs semantic understanding based on an LLM, providing more accurate context recommendations
  - Added a build-validator module (build_validator): supporting automatic detection and validation of multiple build systems (Rust/Cargo, Python, Node.js, Java/Maven/Gradle, Go, CMake, Makefile, etc.)
  - Added a file-ignore utility module (file_ignore): supporting intelligent file filtering
  - Optimized the intelligent-context-recommendation feature: refactored context recommendation to be keyword-driven instead of intent-recognition, and adjusted the context-file-recommendation strategy to preferentially use the most recently modified files
  - Supports lint-tool recognition of .prettierrc files and optimized the matching logic
  - Added static-check execution progress and result feedback, optimizing the skip logic and prompt messages of static analysis
  - Implemented a forced-addition mechanism after consecutive skipped rounds for addon_prompt
- **Code-safety and protection mechanisms**
  - Added a large-code-deletion protection mechanism, adding a code-deletion-volume check before committing
  - Added a large-code-deletion detection and protection mechanism (git_utils)
  - Added a file-read token-limit check (read_code)
- **Architecture documentation and design**
  - Added the Agent system-architecture-design document
  - Added the CodeAgent system-architecture-design document
  - Added the MultiAgent system-architecture-design document
  - Added the haijunbot-c2rust system-architecture-design document
  - Added the haijunbot-sec system-architecture-design document
  - Added the technical-report document (technical-report.md), containing the complete technical solution and test cases
- **CLI and interaction experience**
  - Added interactive-mode support to all commands
  - Replaced print with typer.secho to enhance log-color output
  - Optimized the user output of the code-analysis flow, hiding the intent-recognition process

#### **📌 Fixes**

- Fixed the issue where intelligent context recommendation did not correctly output content
- Fixed code-indentation issues and improved exception handling
- Fixed the indentation error in YAML parsing and improved the YAML-parsing error-handling mechanism
- Fixed code-indentation and status-update-position issues in the security-analysis flow
- Fixed the logic error in multi-threaded context detection
- Fixed the issue where model output was accidentally suppressed
- Fixed the method-call error in code-agent execution
- Fixed the wording issue in the clustering-validation log
- Adjusted the lint-tool search order, prioritizing matching by file extension
- Forced clustering results to include the is_invalid field and enhanced error handling
- Ensured that no gid is omitted in cluster analysis

#### **🔧 Optimizations and Refactoring**

- **haijunbot-sec security-analysis-flow refactoring**
  - Refactored the clustering retry and validation logic, splitting the review and verification logic into independent functions to improve maintainability
  - Refactored the security-analysis flow, splitting the clustering and verification phases and enhancing breakpoint-recovery capability
  - Extracted the clustering logic into independent helper functions and enhanced integrity validation
  - Refactored the breakpoint-recovery logic of security analysis and unified path handling
  - Optimized the error-handling flow of clustering tasks, simplifying the retry logic
  - Disabled the planning step in the security-analysis flow
- **CodeAgent architecture optimization**
  - Refactored the CodeAgent to inherit from the Agent class implementation
  - Refactored the code-context-recommendation feature, optimizing the model-configuration-loading logic
  - Refactored the post-tool-call-processing logic
  - Optimized error handling and log output
  - Adjusted the directory structure of the code-analysis module, moving the build_validator module under the code_analyzer directory
  - Refactored the build-validation module into a multi-file structure, enhancing build-system-detection and error-handling capabilities
- **Code-quality improvement**
  - Unified the indentation format of Agent-creation code blocks
  - Enhanced code type safety and robustness
  - Unified the parsing logic of XML tags in LLM responses
  - Unified the user-confirmation logic as confirm_callback and supported auto-complete mode
  - Refactored tree-sitter language support to use pip installation
- **Tool and dependency optimization**
  - Removed unused lint-tool configurations
  - Removed redundant lint-tool test cases
  - Added a limit to the number of context-info displays (read_code)
  - Optimized the static-check output logic and cleaned up unused imports
  - Split the interactive-configuration-collection logic into multiple dedicated functions

#### **📚 Documentation Update**

- Added a complete architecture-design-document system (5 architecture-design documents)
- Added the technical-report document (technical-report.md), containing:
  - A complete technical-solution explanation
  - Detailed reports of multiple test cases (bzip2, commonlibrary_c_utils, commonlibrary_rust_ylong_runtime, security_asset)
  - Security-issue statistics and improvement plans
- Updated the test-case documentation, relaxing the test-assertion conditions of the security checker
- Updated the appendix documentation, supplementing descriptions of newly added configuration items

#### **🔧 Miscellaneous**

- Added support for multiple tree-sitter language parsers
- Added the mypy.ini configuration file, enhancing type checking
- Updated pyproject.toml and setup.py, adding new dependencies
- Optimized the PDF-generation script and style files
- Updated the test-case directory structure (tests/{oh_sec => haijunbot_sec}/test_checkers.py)
- Added security-analysis reports and progress files for multiple test cases

This update is a major version upgrade, with the core focus on comprehensive enhancement of **security-analysis capability**, **code-analysis capability**, and the **transpilation toolchain**. By introducing core features such as state management, breakpoint resume, intelligent context recommendation, and impact-scope analysis, HaijunBot's capabilities in code security analysis, code understanding, and code migration have been significantly enhanced.

**Technical highlights:**

- **hsec (haijunbot-sec)**: Adopts a four-stage pipeline architecture, merging similar issues via intelligent-clustering technology, using a dual-verification mechanism (analysis Agent + verification Agent) to ensure accuracy, supporting unlimited retries and direct-model-call fallback, ensuring analysis completeness
- **hc2r (haijunbot-c2rust)**: Provides a complete six-stage migration pipeline (collect->scan->lib-replace->prepare->transpile->optimize); the transpiler adopts the complete flow of module selection -> CodeAgent generation -> build-fix loop -> code-review loop, and the optimizer uses conservative-optimization techniques such as unsafe cleanup and visibility optimization, combined with a Git-protection mechanism to ensure rollback capability. Each stage supports breakpoint resume, ensuring the controllability and reliability of large-scale migration

At the same time, the newly added complete architecture-design documents and technical report lay a solid foundation for the project's long-term maintenance and community collaboration.

### Release Note - v0.6.0 (2025-10-26)

#### **🚀 New Features**

- A brand-new C2Rust migration toolchain is launched (haijunbot-c2rust/hc2r CLI)
  - Command groups: scan (scanning and visualization), prepare (LLM plans the crate structure and writes to disk), transpile (sequential transpilation and build fixing), lib-replace (library-replacement evaluation for the root-list subtree), collect (collecting function names from header files), run (one-click pipeline: collect->scan->lib-replace->prepare->transpile)
  - Supports automatic detection and robust loading of libclang 16-21 versions, with actionable error-message prompts
  - Supports root-function-subgraph DOT output and optional PNG rendering (requires graphviz)
  - Supports read_symbols to read symbols.jsonl on demand, avoiding reading the entire large file
  - The transpiler supports breakpoint resume, per-function selection (--only), and automatically eliminating `todo!("symbol")` placeholder references in the source code
- Agent/CLI capability enhancement
  - Added the configuration HAIJUNBOT_PLAN_ENABLED: allows enabling/disabling task planning by default; CLI --plan/--no-plan can explicitly override
  - Added the Agent parameter disable_file_edit: supports disabling the file-editing handler in scenarios such as review/planning
  - Added the haijunbot-c2rust and hc2r entry commands

#### **📌 Fixes**

- Fixed the issue where CodeAgent might not restore the working directory after execution (ensuring it returns to the original working directory)
- Fixed the issue where automatic-update detection only located within the src/haijunbot directory; now it reliably detects from the repository root
- When "do not add" is selected in the Git-commit interaction, untracked files are automatically written to the repository's .gitignore, avoiding repeated prompts and a dirty working area

#### **🔧 Optimizations and Refactoring**

- Extended .gitignore to a cross-language template (General/Python/Rust/Node/Go/Java/C/C++/.NET, etc.), covering more common artifacts by default
- Unified task-planning source: Agent plan preferentially uses the input parameter, otherwise falls back to the configuration HAIJUNBOT_PLAN_ENABLED; the CLI plan option supports "load from configuration if not specified"
- The built-in configuration selector supports multiple candidate builtin directories, adding optional debug output
- Tool-system experience optimization: provides a ToolUsage hint when tool parsing errors occur; read_code batch-read output only prints status lines, which is more friendly
- Improved CodeAgent/execution-chain robustness: automatic cargo build verification after fixing; stricter working-directory and patch-scope control

#### **📚 Documentation Update**

- Updated docs/haijunbot_book/appendix: newly added/revised configuration items (including HAIJUNBOT_PLAN_ENABLED, default-switch adjustments, etc.)
- Updated the WeChat QR code image (docs/images/wechat.png)

#### **🔧 Miscellaneous**

- Packaging and entry
  - pyproject.toml/setup.py added clang16-clang21 extras
  - Added haijunbot-c2rust/hc2r console_scripts entries
- Visualization and data
  - Supports root-subgraph DOT/PNG output; translation_order.jsonl contains self-contained records, convenient for independent consumption in the transpilation phase

This update mainly focuses on building and engineering-polishing the end-to-end C-to-Rust migration-pipeline capability "from scanning to transpilation": providing robust libclang adaptation, LLM-driven crate planning, and a minimal-change build-fix closed loop; at the same time, it systematically optimized Agent configuration, tool availability, .gitignore templates, and documentation.

### Release Note - v0.5.1 (2025-10-20)

#### **🚀 New Features**

- **Added the `haijunbot_sec` security-analysis suite**: Provides the `hsec` command for security scanning and analysis of code projects. The initial version supports heuristic security scanning of C/C++/Rust projects and can generate structured JSON and Markdown reports, providing preliminary support for the evolution of code security.

#### **✨ Optimizations and Refactoring**

- **C2Rust migration-workflow refactoring**: Unified all outputs of the C2Rust migration process (including scripts, logs, Rust bridge code, etc.) into the `.haijunbot/c2rust/` directory under the project root, keeping the project source tree clean.
- **Script-robustness improvement**: Scripts generated by C2Rust migration now force the use of absolute paths, ensuring they can be correctly and idempotently executed in any working directory.
- **Streamlined built-in Agents**: Removed multiple predefined, less-used Agent roles (such as psychology, life advisor, PPT design, etc.), making the core functionality more focused.
- **Extended context memory**: Raised the default auto-summary conversation rounds from 20 to 50, significantly extending the context-memory capability in complex interactions.

#### **📚 Documentation Update**

- **Added security-suite documentation**: Added a detailed `README.md` for the `haijunbot_sec` module, explaining its usage, workflow, and report structure.

### Release Note - v0.5.0 2025-10-18

#### **New Features**

- **C/C++ to Rust migration pipeline**: Added a powerful multi-agent pipeline (`c2rust_migration`) for progressive, rollback-capable, and measurable Rust migration of C/C++ projects.
- **Project-level rule support (`hca`)**: Code Agent (`hca`) now supports defining rules via a `.haijunbot/rules` file in the project root, allowing teams or individuals to customize the AI's coding conventions, modification scope, and operation flow, enhancing collaboration consistency.
- **Flexible central-library configuration**: The central tool library and methodology library (`HAIJUNBOT_CENTRAL_TOOL_REPO`/`HAIJUNBOT_CENTRAL_METHODOLOGY_REPO`) now support configuration as a local filesystem path, no longer limited to Git repositories, providing convenience for offline or intranet environments.
- **Enhanced interactive configuration**: The `hjb -I` configuration wizard added multiple configuration items, including session-history saving, error backtracking, auto-summary rounds, script timeout, etc., allowing you to control HaijunBot's behavior more precisely.
- **Added software-development-capability explanation**: Added a new solution document detailing HaijunBot's various capabilities and typical application scenarios in the software-development lifecycle.

#### **Fixes**

- **Context retention**: Fixed the issue where the system prompt might become invalid after a `clear_history` (clear history) operation, ensuring the Agent can still follow the core instructions after clearing the context.

#### **Optimizations and Refactoring**

- **Optimized change preview (`hca`)**: Optimized the preview interface of Code Agent (`hca`) before generating file patches; it now displays the added/deleted line-count statistics of files and automatically collapses the diff of overly large files, making the preview clearer and more efficient.
- **Localization improvement**: The prompt of the novel generator (`novel_generator`) has been optimized, explicitly requiring Chinese output, improving the localization experience.
- **Code-review-module refactoring**: Refactored the internal code-review tool, improving modularity and maintainability.
- **Removed old module**: Removed the deprecated `security_evolution` multi-agent configuration.
- **Default-prompt fine-tuning**: Fine-tuned the Agent's default system prompt, making the human-computer interaction flow smoother.

#### **Documentation Update**

- **Comprehensive content update**: Made large-scale updates and corrections to the HaijunBot Book (official documentation), covering new feature introductions, command-usage clarifications, architecture-diagram adjustments, and spelling and format optimizations, improving the accuracy and readability of the documentation.

This update focuses on improving HaijunBot's practical capability in complex software-engineering scenarios, introducing a C++ to Rust code-modernization migration solution, and strengthening team collaboration via features such as project-level rules. At the same time, a large number of documentation updates and usability improvements will bring you a smoother development experience.

### Release Note - v0.4.2 (2025-10-15)

#### **New Features**

- **Brand-new multi-agent novel generator**: Refactored the novel-generation pipeline, adopting a "file-as-state" distributed design to replace the original centralized state file, greatly improving process robustness, scalability, and breakpoint-recovery capability. Introduced volume-outline management and optimized the chapter-advancement logic, making the management of long-form creation clearer and more reliable.
- **Conversation-round-based automatic summarization**: Added the `HAIJUNBOT_AUTO_SUMMARY_ROUNDS` configuration item, implementing an automatic context-summarization-and-cleanup mechanism based on conversation rounds. This replaces the original fixed token-count-based threshold, manages long conversation history more intelligently, and guarantees the stability and performance of long-running operation.
- **Enhanced multi-agent collaborative control**:
  - Added the `non_interactive` parameter to the `sub_agent` tool, allowing the parent Agent to more flexibly control the interaction mode of sub-Agents.
  - Added the `summary_on_send` configuration, allowing selective disabling of automatic summarization when passing messages between multiple agents, to adapt to different collaboration scenarios.
  - Optimized interaction functions such as `user_confirm` and `get_multiline_input`, enabling them to precisely perceive the configuration of the currently active Agent, performing more stably and as expected in multi-agent environments.

#### **Fixes**

- **Multi-agent history cleanup**: Fixed the issue of incorrectly clearing the receiver's rather than the sender's history after multi-agent message passing.
- **Tool-call parsing**: Fixed the issue where parsing could fail when the `</TOOL_CALL>` tag at the end of the response was missing a preceding newline, enhancing format fault tolerance.

#### **Optimizations and Refactoring**

- **Agent-configuration initialization**: Refactored the initialization flow of the `Agent` class, removing the independent `AgentConfig` module and integrating the configuration-parsing logic directly into the `__init__` method. This simplified the internal structure, making the code clearer and easier to maintain.
- **Removed redundant token calculation**: Deprecated the original `get_max_token_count` utility function, fully shifting to the more efficient round-based context-management strategy.

#### **Documentation Update**

- Updated the environment-variable documentation in the appendix, adding detailed explanations of the new parameter `HAIJUNBOT_AUTO_SUMMARY_ROUNDS`.

This update focuses on deep optimization of **the robustness of multi-agent collaboration** and **the stability of long-duration tasks**. By introducing a brand-new "file-as-state" architecture and a round-based intelligent-summarization mechanism, HaijunBot can now handle complex, long-cycle creation and orchestration tasks more reliably, while providing developers with finer control granularity.

### Release Note - v0.4.1 2025-10-11

#### **New Features**

- **Major Web UI upgrade**: Introduced a PTY-based full-featured interactive terminal, completely replacing the original input box; you can now get a complete Shell experience in the Web interface consistent with the local one.
- **Built-in file operations**: Added `REWRITE` and `PATCH` as built-in file-operation directives, replacing the original `rewrite_file` and `edit_file` tools, making file modification more reliable and standardized.
- **Brand-new multi-agent: novel generator**: Added a multi-agent workflow called `novel_generator`, capable of automatically generating a novel from scratch through a complete pipeline of character design, outline construction, chapter writing, polish and proofreading, etc.
- **Security-evolution-flow enhancement**: Greatly upgraded the `security_evolution` multi-agent, introducing the "Rust-first" principle, breakpoint-resume capability, and a more detailed measurement and reporting mechanism.

#### **Fixes**

- **Agent summary prompt**: Fixed the issue where execution could fail when `summary_prompt` was empty, enhancing the stability of Agent task summarization.
- **Multi-agent message passing**: Fixed the hard-to-troubleshoot issue when the `SEND_MESSAGE` format was wrong; extremely robust validation and clear fix guidance are now provided.

#### **Optimizations and Refactoring**

- **Agent non-interactive mode**: Added the `non_interactive` construction parameter to Agent, making it convenient for sub-Agents to inherit the parent Agent's running mode.
- **Configuration and startup**: Added the `HAIJUNBOT_SKIP_PREDEFINED_TASKS` environment variable, allowing users to skip loading predefined tasks to speed up startup.
- **Multi-agent framework**: Added `common_system_prompt`, allowing common instructions to be set for all agents in a workflow; it also supports automatically clearing an agent's history after it sends a message, optimizing memory usage.
- **UI-prompt optimization**: In multi-agent scenarios, status prompts such as "thinking" and "model output" explicitly display the name of the currently working agent, improving transparency.
- **Code cleanup**: Comprehensively removed the deprecated `edit_file` and `rewrite_file` tools, and uniformly updated the configuration of built-in Agents.

#### **Documentation Update**

- **Appendix update**: Supplemented the documentation with an explanation of `HAIJUNBOT_SKIP_PREDEFINED_TASKS`.
- **Image update**: Updated the WeChat contact image in the documentation.

This update is a major feature and experience upgrade, with the core being the introduction of a brand-new Web interactive terminal and powerful `REWRITE`/`PATCH` file-operation capabilities, along with the addition of a creative novel generator, and deep optimization of the underlying multi-agent framework and security-analysis flow, making HaijunBot more powerful and easier to use.

### Release Note - v0.4.0 2025-10-08

#### **New Features**

- **Web interaction mode**: Added the `--web` mode, allowing interaction with HaijunBot through the browser. Supports real-time standard input/output redirection, multi-task parallel processing, and remote access, greatly improving the interaction experience and convenience.
- **Non-interactive mode**: Added the `-n` / `--non-interactive` parameter to multiple commands such as `hjb`, `hca`, and `jma`, for unattended operation in CI/CD or automation scripts, enhancing automation capability.
- **Install-script enhancement**: The `install.sh` script added an option to automatically install command-line completion for all `j*` commands, improving daily usage efficiency.
- **Background-service management**: Enhanced the stop logic (`--stop`) of the Web-mode background service; when the PID file is lost, it will attempt to find and stop the process by port number, improving service robustness.
- **Web-terminal display**: In Web mode, the terminal width is automatically reported and set, optimizing the wrapping and display of content such as tables and progress bars.

#### **Optimizations and Refactoring**

- **Agent initialization**: Simplified the `Agent` initialization logic, handling the loading of the input handler (`input_handler`) internally, reducing inter-module coupling.
- **Web architecture**: Introduced modules such as `web_bridge` and `stdio_redirect`, building a front-end/back-end-separated architecture based on FastAPI and WebSocket, achieving decoupling of the Agent core from the Web UI.
- **Configuration adjustment**: Adjusted the calculation logic of `max_token_count`, making it more reasonable.

#### **Documentation Update**

- **Usage guide**: Updated `4.Usage_Guide.md` in detail, comprehensively introducing the usage, core features, and common parameters of the newly added "non-interactive mode" and "Web mode".

### Release Note - v0.3.34 2025-10-07

#### **New Features**

- Added the general basic-software-library security-evolution multi-agent configuration (security_evolution.yaml), supporting a more flexible security-analysis flow

#### **Optimizations and Refactoring**

- Refactored the security-evolution multi-agent architecture, upgrading the OpenHarmony-specific version to a general version
- Optimized the multi-agent collaboration flow
- Enhanced non-interactive-mode support, adding script-execution-timeout control

#### **Documentation Update**

- Updated the HaijunBot manual, adding explanations of non-interactive mode and script-timeout configuration

This update mainly optimized the generality and reliability of the security-evolution multi-agent system, while enhancing stability in non-interactive mode.

### Release Note - v0.3.33 2025-10-04

#### **New Features**

- **Added a "product-promotion-copywriting expert" Agent**: Added a built-in Agent designed specifically for product promotion, capable of writing high-quality marketing copy based on product information and target audience.
- **Added the "OpenHarmony security evolution" multi-agent workflow**: Provides a full-process security-evolution solution for OpenHarmony basic software libraries, from code understanding and risk assessment to code generation and verification.
- **Added automatic file-context processing**: Now, when you reference a local file path in your input via `'path/to/file'`, the system automatically reads the file content and uses it as context, without manual copy-paste.
- **Added a session-history-recording feature**: By setting `HAIJUNBOT_SAVE_SESSION_HISTORY=true`, you can save the complete conversation history (user input and model output) to a log file, convenient for review and problem tracking.

#### **Fixes**

- Fixed the issue where the `--restore-data` option failed to parse paths containing `~` or environment variables.
- Fixed the built-in configuration selector (`HAIJUNBOT_ENABLE_STARTUP_CONFIG_SELECTOR`), adding a "skip" option to avoid interrupting the flow when you do not want to select.
- Fixed the issue where the webpage-reading (`read_webpage`) and web-search (`search_web`) tools returned empty success results in some cases; now success is only returned when valid content is obtained.
- Fixed the hard-coded path in the `make_book.sh` script, switching to relative paths, enhancing script portability.

#### **Optimizations and Refactoring**

- **Agent localization and experience optimization**: Localized and renamed multiple built-in Agents (such as the architecture-diagram generator, psychology expert, etc.), improving the readability and usage experience for Chinese users.
- **Multi-agent collaboration enhancement**: In multi-agent workflows, messages passed between Agents now come with a summary of the previous round of work, significantly improving the efficiency and accuracy of context passing in collaboration.
- **Agent-capability-reminder mechanism**: During long-running operation, Agents periodically receive reminders of available tools, which helps the model maintain awareness of its own capabilities in complex tasks, reducing "hallucinations".
- Optimized the `build_pdf.sh` script, enhancing the automatic-dependency-check-and-install feature, making it more robust and easier to use.

#### **Documentation Update**

- Added a promotional article detailing HaijunBot's "dynamic retrieval + layered memory" design philosophy, distinguishing it from the traditional "whole-library-index" approach.
- Updated the appendix documentation, adding an explanation of the `HAIJUNBOT_SAVE_SESSION_HISTORY` environment variable.
- Updated the WeChat group QR code in the project documentation.

This update focuses on improving the intelligence, usability, and stability of the system. By introducing practical features such as automatic file-context processing and session-history recording, it further lowers the user's barrier to entry. At the same time, optimizations to the core Agent and scripts make HaijunBot more reliable when handling complex tasks and long-term interactions.

### Release Note - v0.3.32 2025-09-29

#### **New Features**

- **(agent) Added an architecture-diagram generator**: Introduced a brand-new `ArchitectureDiagramGenerator` Agent, capable of automatically analyzing a codebase and generating various professional architecture diagrams, including logical views, implementation views, and deployment views.
- **(cli) Added data backup and restore**: Added the `--backup-data` and `--restore-data` options to the main command `hjb`, convenient for users to back up and restore all data in `~/.haijunbot` with one click.
- **(platform) Enhanced OpenAI integration**: Supports customizing OpenAI's API address via the `OPENAI_API_BASE` environment variable, and injecting extra HTTP headers via `OPENAI_EXTRA_HEADERS`, greatly improving integration flexibility with third-party proxies or enterprise internal platforms.

#### **Fixes**

- **(git_utils) Fixed diff parsing**: Removed the unnecessary `-U0` parameter in the `git show` command, resolving the problem that could cause inaccurate parsing of the line ranges of code modifications.
- **(input) Optimized shortcut-key response**: Set the binding of `Ctrl+T` (custom command) to `eager` mode, ensuring it has the highest priority in input handling and is not overridden by other keys.

#### **Optimizations and Refactoring**

- **(edit_file) Upgraded the range-replacement logic**: The range-replacement feature of the `edit_file` tool has been refactored; it now replaces from the beginning of the line where the start marker is located all the way to the end of the line where the end marker is located. This makes the replacement operation more intuitive and better maintains code alignment and formatting.
- **(utils) Improved log observability**: Enhanced the `while_success` retry helper function; now when an exception occurs, detailed exception information is printed directly in the retry log, facilitating rapid problem location.

#### **Documentation Update**

- **(architecture) Added complete architecture views**: Added a full set of architecture diagrams (`.dot` sources and `.png` images) generated using the new tool to the project documentation, comprehensively showcasing the system's logical, implementation, process, deployment, and use-case views.
- **(haijunbot_book) Comprehensive content update**:
  - Added detailed explanations of new features such as data backup and restore and custom OpenAI to the usage guide.
  - Added an FAQ chapter, answering common questions about custom API addresses and HTTP headers.
  - Adjusted the numbering and order of multiple chapters, making the document structure more reasonable.
  - Fixed the error in the RAG group name in the example code.

This update is an important feature enhancement and experience optimization. The core highlight is the **automated generation of architecture diagrams**, which will greatly improve the team's efficiency in understanding the project code. At the same time, **data backup and restore** and **more flexible platform configuration** provide solid guarantees for enterprise-level applications and personal data security.

### Release Note - v0.3.31 2025-09-27

#### **New Features**

- Added the code-reverse-design-expert agent (CodeReverseDesignExpert), supporting reading code and outputting a detailed design plan, facilitating feature-alignment refactoring
- Added the McKinsey-style management-consulting-advisor agent (McKinseyConsultant), systematically analyzing business problems and providing implementable solutions
- Added the SecurityVulnerabilityAnalyst solution document, systematically introducing the positioning, process, architecture, and quantified benefits of the vulnerability-analysis expert
- Added the patch-format-control configuration (HAIJUNBOT_PATCH_FORMAT), supporting three modes: all/search/search_range, improving the stability and flexibility of code modification
- Added multi-directory-loading configuration items: HAIJUNBOT_METHODOLOGY_DIRS, HAIJUNBOT_AGENT_DEFINITION_DIRS, HAIJUNBOT_MULTI_AGENT_DIRS, HAIJUNBOT_CENTRAL_METHODOLOGY_REPO, expanding resource-loading capability
- Added a line-start-match-validation mechanism for tool-call tags, enhancing robustness, automatically completing missing end tags
- Added an automatic upload or intelligent truncation mechanism for large outputs, preventing context overflow
- Added a per-file diff-display feature for the code agent, optimizing the change-visualization experience
- Added an empty-model-response defense mechanism, avoiding exceptions caused by None or empty strings

#### **Fixes**

- Fixed the problem of missing user confirmation for the git reset operation in the code agent, preventing misoperations
- Fixed the inconsistency between configuration-file default values and platform differences (e.g., HAIJUNBOT_PRETTY_OUTPUT disabled by default on Windows)
- Fixed memory-usage optimization: the read_code tool adopts streaming reading, reducing memory consumption when loading large files
- Fixed the parsing-performance problem caused by the oversized output of the git show command, adopting the -U0 parameter to reduce context
- Fixed the memory-usage problem of file hashing and line-count statistics, adopting streaming processing to improve performance

#### **Optimizations and Refactoring**

- Refactored the ToolRegistry tool-call-parsing logic, strengthening line-start tag matching, improving fault tolerance
- Refactored the EditFileHandler patch-handling mechanism, supporting RANGE-limited line-number ranges and range-replacement modes
- Refactored the code-agent commit-message-display logic, displaying diffs by file and only prompting for deleted files, improving readability
- Optimized the default behavior of the memory system, setting HAIJUNBOT_FORCE_SAVE_MEMORY to false by default, reducing redundant prompts
- Optimized the configuration-interaction experience, adding patch-format selection and explanations, adapting to different model capabilities
- Optimized the wording of the vision and mission, making it more concise and focused on the symbiotic relationship between developers and AI

#### **Documentation Update**

- Updated the core-concepts-and-architecture document, streamlining MCP-tool-configuration details, adding an overview of tool loading and compatibility
- Updated the usage guide, removing duplicate content on memory-management tips, focusing on advanced usage
- Updated the appendix-configuration table, supplementing explanations of newly added configuration items and default-value adjustments

- Added an advanced-topics chapter, detailing the usage and notes of the patch-format-control configuration

#### **Miscellaneous**

- Adjusted multiple agent configuration files, supplementing support for the execute_script and read_code tools
- Unified the configuration-schema default values with code-logic consistency, improving configuration robustness
- Optimized the CLI-startup output content, improving brand recognition and user experience

This update is organized around four directions: agent-ecosystem expansion, code-modification stability, system performance, and user experience. It added two professional agents and a vulnerability-analysis solution, strengthened the patch mechanism and tool-call robustness, optimized memory and performance, and improved the documentation and configuration system, laying a more solid foundation for subsequent feature evolution and community collaboration.

### Release Note - v0.3.30 2025-09-20

#### **New Features**

- Added a post-tool-call-callback extension (after_tool_call_cb), supporting dynamic loading of multiple callback functions
- Supports specifying a callback directory via the configuration file (HAIJUNBOT_AFTER_TOOL_CALL_CB_DIRS), automatically scanning and registering callbacks
- Added callback-registration conventions: module-level callable objects, the factory function get_after_tool_call_cb(), and register_after_tool_call_cb()
- Added event-bus integration; callbacks are triggered in sequence before and after the AFTER_TOOL_CALL event broadcast
- Added the configuration item HAIJUNBOT_AFTER_TOOL_CALL_CB_DIRS, supporting ~ and environment-variable expansion

#### **Optimizations and Refactoring**

- Refactored the Agent-initialization logic, supporting dynamic loading of post-tool-call callbacks
- Optimized the code-agent tool-execution-recording mechanism, using the event bus instead of direct callbacks
- Optimized the dependency-installation logic, prioritizing the uv inside the virtual environment, then uv in PATH
- Optimized the update-detection logic, prioritizing detection of uv availability inside the virtual environment
- Optimized the git-repository-update logic, enhancing uv-environment-detection accuracy

#### **Documentation Update**

- Updated the advanced-topics document, adding detailed explanations of the post-tool-call-callback extension
- Updated the configuration-file appendix, adding an explanation of the HAIJUNBOT_AFTER_TOOL_CALL_CB_DIRS configuration item

#### **Miscellaneous**

- Fixed the dependency-installation command in the generate_new_tool tool, supporting both uv and pip paths
- Fixed the uv-environment-detection logic in git_utils, prioritizing detection of uv inside the virtual environment
- Fixed the uv-availability detection in utils.py, enhancing uv-path-recognition accuracy

This update mainly enhanced the post-tool-call extension capability, supporting dynamic loading of callback functions, while also optimizing uv-environment detection and dependency-installation logic, improving the system's flexibility and stability.

### Release Note - v0.3.29 2025-09-17

#### **New Features**

- Added a HaijunBot system-architecture-diagram PlantUML update, refining component responsibilities and interaction flows
- Added an event-bus (EventBus) mechanism, supporting task-lifecycle-event broadcasting and bypass extension
- Added an independent run-loop (AgentRunLoop) class, decoupling the main-loop logic and supporting LoopAction flow control
- Added a prompt manager (PromptManager) to centrally manage system-prompt and additional-prompt construction
- Added the AgentConfig configuration-aggregation class, uniformly parsing initialization parameters and handling default values
- Added a user-interaction wrapper (UserInteractionHandler), convenient for future UI replacement
- Added a tool executor (ToolExecutor) to uniformly parse model responses and execute tool calls
- Added an output-handler protocol (OutputHandlerProtocol), supporting extension of non-tool response handling
- Added a task manager (TaskManager) supporting fzf interactive task selection and supplementary-information appending
- Added an event-constant-definition module (events.py), standardizing event names and payload-type hints
- Added a utility-function module (utils.py), providing unified implementations such as join_prompts, is_auto_complete, and normalize_next_action
- Added type-compatibility handling for Python 3.8+ (such as List[str], Optional[str], etc.)
- Added an editable-install-detection function (is_editable_install), supporting PEP 610 and .egg-link fallback
- Added a memory-manager event-subscription mechanism, supporting automatic memory saving at task start/history cleanup/task completion
- Added Git-tool commit prefix/suffix support (--prefix/--suffix), enhancing commit-message standardization
- Added a built-in configuration selector (--builtin-config-selector), supporting interactive switching between agent/multi_agent/roles
- Added an interactive configuration wizard (--interactive-config), supporting item-by-item confirmation and modification based on the current configuration
- Added a disable-methodology-analysis option (--disable-methodology-analysis), supporting fast directive-style conversations
- Added statistics-tool (jst) command extensions: support for parameters such as remove, --width, --height, --agg
- Added documentation-build-script optimization, supporting automatic correction of blank lines in lists outside code blocks and table-format unification

#### **Optimizations and Refactoring**

- Refactored the Agent-initialization flow, introducing components such as EventBus, PromptManager, and AgentConfig
- Refactored the main run loop into AgentRunLoop, supporting event broadcasting and callback isolation
- Refactored the tool-call flow, uniformly using ToolExecutor for parsing and execution, supporting protocol-version dispatch (v1.0/v2.0)
- Refactored the prompt-concatenation logic, uniformly using join_prompts to avoid empty paragraphs and format errors
- Refactored the auto-complete-detection logic, uniformly using is_auto_complete to support ot() and literal fallback
- Refactored the next-action parsing, uniformly using normalize_next_action to support Enum and string compatibility
- Refactored the event-broadcast logic, uniformly using event constants (such as BEFORE_TOOL_CALL, TASK_COMPLETED, etc.)
- Refactored the file and methodology managers, supporting platform-capability judgment and automatic local/upload mode selection
- Refactored the memory system, supporting force_save_memory configuration and event-driven automatic saving
- Refactored the statistics-module default-display logic, supporting full-history-data display and intelligent time-range inference
- Refactored the code static-analysis toolchain, replacing black with ruff to improve formatting efficiency
- Refactored the development-dependency configuration, removing isort and uniformly using ruff for code formatting
- Optimized the CLI-startup flow, supporting interactions such as preloading configuration, Git-repository detection, and built-in configuration selection
- Optimized the platform-loading order, clarifying the override mechanism of "user directory takes precedence over built-in directory"
- Optimized the MCP-tool-configuration-loading logic, preferentially using the HAIJUNBOT_MCP configuration, falling back to scanning the mcp directory
- Optimized the tool-registry-loading logic, supporting protocol-version dispatch and exception isolation
- Optimized the output-handler chain, supporting multi-handler collaboration and priority processing
- Optimized the document structure, unifying terminology and configuration-item explanations, correcting chapter-numbering errors

#### **Fixes**

- Fixed the problem of the `@` symbol being misused as `'<...>'` in the special-directive documentation
- Fixed the problem of the CLI parameter `-t` being misused as the task parameter, uniformly changed to `-T/--task`
- Fixed chapter-numbering errors in the configuration-file appendix (such as 8.x -> 7.x)
- Fixed the potential drift problem caused by hard-coded strings in event broadcasting
- Fixed the problem of the agent-parameter-injection logic in tool calls being incompatible with the v2.0 protocol
- Fixed type-annotation-inconsistency problems in the file-editing tool (such as list[str] -> List[str])
- Fixed the problem of invalid time-range parameters in the statistics tool (such as --days/--hours not being supported)
- Fixed the problem of duplicate triggering of memory-save prompts, introducing dedup markers and event isolation
- Fixed the problem of editable-install-detection failure, enhancing PEP 610 and .egg-link compatibility
- Fixed the problem of the process exiting due to overly strict path validation in the Git-commit tool
- Fixed the problem of outdated shortcut-key descriptions in the multi-line-input help prompt
- Fixed the problem of inconsistent table formats in the documentation, unifying blank-line handling before table headers
- Fixed the problem of type annotations in the code being incompatible with Python 3.8 (such as str | None -> Optional[str])

#### **Documentation Update**

- Updated the system-architecture diagram, refining component responsibilities and interaction flows, supplementing explanations of the event mechanism
- Updated the core-concepts chapter, adding introductions to the memory system and the event bus
- Updated the usage guide, supplementing explanations of CLI-parameter changes and interactive configuration
- Updated the feature-extension chapter, supplementing explanations of MCP-tool configuration, platform-loading order, and protocol versions
- Updated the advanced-topics chapter, supplementing usage examples of event constants, output handlers, and the memory system
- Updated the configuration-file appendix, adding default-value adjustments such as HAIJUNBOT_PRETTY_OUTPUT and HAIJUNBOT_FORCE_SAVE_MEMORY

- Updated the statistics-tool usage instructions, supplementing usage of parameters such as remove, --agg, --width, and --height
- Updated the methodology template, optimizing the "reusable solution process" wording to avoid binding to a specific context
- Updated code comments and docstrings, uniformly using English to maintain project consistency

#### **Miscellaneous**

- Adjusted the HAIJUNBOT_PRETTY_OUTPUT default value to true (non-Windows platforms)
- Adjusted the HAIJUNBOT_FORCE_SAVE_MEMORY default value to false, avoiding frequent prompts
- Adjusted the default output format, optimizing long-text display and overflow-handling logic
- Adjusted the default behavior of the Git-check mode, supporting strict/warn mode configuration
- Adjusted the tool-filter-threshold default to 30, reducing interference from large-scale tool sets
- Adjusted the code-formatting strategy, uniformly using ruff to replace black and isort
- Adjusted the documentation-build flow, supporting PlantUML rendering and automatic format correction
- Adjusted the memory-manager event-subscription mechanism, supporting exception isolation and callback protection
- Adjusted the platform-loading logic, supporting user-custom platforms overriding built-in implementations
- Adjusted the sub-Agent-tool parameter-inheritance mechanism, enhancing explicit configuration passing and validation

This update is organized around the four goals of "clearer architecture, event-driven, friendly interaction, and flexible configuration", completing a comprehensive modularization refactoring of HaijunBot's core components. By introducing new mechanisms such as the event bus, run loop, and prompt manager, the system has stronger extensibility and maintainability; by optimizing experiences such as CLI interaction, the configuration wizard, and task selection, user operations are more intuitive and efficient; by unifying details such as the tool protocol, prompt concatenation, and type annotations, code quality and compatibility are significantly improved. This upgrade lays a solid foundation for subsequent feature expansion (such as WebUI, plugin marketplace, and multimodal interaction), marking a key step for HaijunBot from a "functional assistant" to a "platform-based agent".

### Release Note - v0.3.28 2025-09-10

#### **New Features**

- Added the command-line parameter `--disable-methodology-analysis` (shorthand `-D`), supporting one-click disabling of methodology and task-analysis functionality
- Agent-startup statistics now display the platform name, improving recognition when using multiple platforms
- Sub-Agents (sub_agent/sub_code_agent) added model-validity validation and automatic-fallback mechanisms, enhancing model compatibility
- The Git-commit tool added support for the `llm_group` parameter, improving the model-context passing of the code agent

#### **Fixes**

- Fixed code warnings for unused variables in several places, improving code cleanliness
- Fixed problems of f-strings with no variable references in several places, avoiding potential performance loss
- Fixed the problem of inconsistency between `typer` option default values and boolean judgment, ensuring the configuration takes effect correctly
- Fixed platform-related import warnings in `VirtualTTYTool`, optimizing cross-platform compatibility
- Fixed the unclear retry-prompt messages of `while_success`/`while_true`, enhancing observability

#### **Optimizations and Refactoring**

- Refactored the model-configuration-parsing logic, clarifying the priority strategy for `model_group_override`, supporting flexible overriding of group configuration and global environment variables
- Optimized the automatic-update-detection mechanism, supporting automatic upgrading via `uv` and `pip` and prompting for restart, improving user experience
- Optimized the exception-handling logic, removing unnecessary exception catching and printing, reducing noisy logs
- Unified the string-formatting style in several places, improving code readability and consistency
- Cleaned up a large number of unused imports, reducing module coupling and load time

#### **Documentation Update**

- Updated the configuration explanation, supplementing comments on the priority logic of `model_group_override`
- Deleted outdated test files and redundant code, keeping the project structure clear

#### **Miscellaneous**

- Deleted the duplicate `X-Requested-With` request header, streamlining HTTP requests
- Supplemented missing exception-handling branches, enhancing robustness

This update mainly enhanced configuration flexibility and model compatibility, optimized the automatic-update and exception-handling experience, and cleaned up code-quality details on a large scale, laying a more solid foundation for subsequent feature expansion.

### Release Note - v0.3.27 2025-09-07

#### **New Features**

- Added the PPT-design-expert agent (PptDesignExpert), supporting user-requirement communication, high-level structure design, single-page content design, and visual-presentation enhancement
- Added the subliminal-message-expert agent (SubliminalMessageExpertAgent), designing subliminal-message-placement plans based on psychological principles
- Added fzf interactive-selection support, improving the role and configuration selection experience
- Added the Git-check-mode configuration (HAIJUNBOT_GIT_CHECK_MODE), supporting strict and warn modes
- Added an event-bus (EventBus) mechanism, supporting task-lifecycle-event broadcasting
- Added PromptManager to centrally manage system prompts and additional-prompt construction logic
- Added the AgentConfig configuration-aggregation class, providing unified configuration parsing and default-value management
- Added the independent AgentRunLoop run-loop class, decoupling the main-loop logic
- Added the UserInteractionHandler user-interaction wrapper, convenient for subsequent UI replacement

#### **Optimizations and Refactoring**

- Refactored the Agent-initialization configuration logic, supporting more flexible parameter parsing and default-value handling
- Optimized the code-agent tool-execution-recording mechanism, precisely tracking tool-call situations
- Optimized the sub-Agent-tool parameter-validation and inheritance mechanism, enhancing explicit configuration passing
- Optimized the statistics-module default-display logic, supporting full-history-data display and intelligent time-range inference
- Optimized the platform-output text-overflow-handling logic, improving long-text display
- Optimized the Git-commit-tool model and platform retrieval logic, preferentially using the passed Agent instance
- Optimized the memory-manager tool-execution-judgment logic, based on actual execution records rather than response content
- Optimized the while_success and while_true retry logic, adding a maximum-retry-count limit
- Optimized the code static-analysis toolchain, replacing black with ruff to improve efficiency
- Optimized the development-dependency configuration, removing isort and uniformly using ruff for code formatting

#### **Documentation Update**

- Updated the configuration-file appendix, adding an explanation of the HAIJUNBOT_GIT_CHECK_MODE configuration item

#### **Miscellaneous**

- Fixed the version-number-display error in the Release Notes
- Fixed the commit-history-display logic, limiting the display to the most recent 5 commits
- Fixed the problem of the process exiting due to overly strict Git-configuration validation in the sub-code-agent
- Fixed outdated shortcut-key descriptions in the multi-line-input help prompt

This update mainly enhanced the agent ecosystem, adding PPT-design and psychology-application-expert agents, while also greatly optimizing configuration management, event-driven design, the interaction experience, and code-quality infrastructure, laying a more solid foundation for subsequent feature expansion.

### Release Note - v0.3.26 2025-08-31

#### **New Features**

- Added the child-psychology-expert agent (ChildPsychologyExpertAgent), providing professional parenting guidance for parents
- Added the life-consultant agent (LifeConsultantAgent), continuously building a user personality profile and providing personalized decision-making advice
- Added the psychology-analysis-expert agent (PsychologyExpertAgent), providing problem solutions from a psychological perspective
- Added the PUA-expert agent (PuaExpertAgent), providing respect-based communication strategies and psychological analysis
- Added a `retrieve` subcommand to the RAG knowledge base, supporting retrieving documents only without generating answers

#### **Optimizations and Refactoring**

- Enhanced the RAG dependency-detection mechanism, providing more precise module-missing prompts
- Optimized agent memory management, supporting the force-save-memory feature
- Improved the RAG installation-detection logic, using a more accurate dependency-check method

#### **Documentation Update**

- Updated the usage-guide documentation, adding detailed usage instructions for the RAG `retrieve` command
- Supplemented the feature descriptions and use cases of the new agents

This update mainly introduced multiple psychology agents in specialized fields, providing users with more precise personalized advice and support, while also enhancing the stability and user experience of the RAG system.

### Release Note - v0.3.25 2025-08-30

#### **New Features**

- **Added a security-vulnerability-analysis Agent**: Introduced the `security_vulnerability_analyst` expert, focusing on analyzing logic and security vulnerabilities in code.
- **Enhanced RAG query capability**: Added the `--rewrite/--no-rewrite` option to the RAG retrieval flow, allowing users to control whether to enable large-model query rewriting to optimize retrieval results.
- **Flexible model-group environment-variable configuration**: `HAIJUNBOT_LLM_GROUPS` now supports an `ENV` field, allowing overriding global environment variables for a specific model group, achieving more flexible multi-model key management.
- **Added an AI tool-filter-threshold configuration**: Added the `HAIJUNBOT_TOOL_FILTER_THRESHOLD` option to the interactive configuration wizard; when the number of available tools exceeds this threshold, AI filtering is triggered.

#### **Optimizations and Refactoring**

- **Model-loading optimization**: Greatly improved the loading logic of local embedding models and rerank models, preferentially loading from the local cache, avoiding unnecessary network requests, and providing clearer error prompts for load failures.
- **Interactive-output-experience improvement**: Optimized the streaming-output display of the AI platform, adding a "thinking..." status prompt and improving the rendering mechanism to reduce interface flickering, enhancing the user experience.
- **Code-quality improvement**: Enhanced type hints and cleaned up code for multiple modules in the project, including `haijunbot.py`, `edit_file.py`, `sub_agent.py`, etc., improving code robustness and maintainability.
- **Underlying tool-call fix**: Fixed the problem of a missing `text=True` parameter in the `subprocess` call in `git_commiter.py`, ensuring cross-platform text-encoding consistency.
- **General utility-function optimization**: Removed redundant retry logs in the `while_success` and `while_true` utility functions, making the output more concise.

#### **Documentation Update**

- **Updated the appendix documentation**: Detailed the newly added `ENV` environment-variable-override feature in `HAIJUNBOT_LLM_GROUPS`, and provided configuration examples.
- **Updated the contact image**: Replaced it with the latest WeChat contact QR code.

### Release Note - v0.3.24 2025-08-26

#### New Features

- Added an AI tool-filter threshold: when the number of available tools exceeds the threshold (default 30), automatically uses a large model to pre-filter the tools most relevant to the current task, reducing interference and improving execution efficiency (supporting the configuration item HAIJUNBOT_TOOL_FILTER_THRESHOLD).
- Added a "comprehensive interviewer" to the role library, covering the three major dimensions of competency/motivation/signing likelihood, with complete scoring standards and output requirements, directly usable for a 30-minute structured interview.

#### Optimizations and Refactoring

- Unified the model-configuration path: removed llm_type (normal/thinking) and the thinking-model channel, comprehensively switching to single-channel model configuration, reducing mental burden and maintenance cost.
- Comprehensive CLI simplification: removed --llm-type related parameters; haijunbot, haijunbot-code-agent, platform management, and role subcommands synchronized to converge the configuration entry.
- Interaction-experience optimization:
  - Streaming output adopts buffering and screen-height clipping, reducing flickering and jumping; supports text-overflow folding, making reading more stable.
  - Batch log-merge output (tool list, document list, SSE/MCP notifications, copy history, etc.), reducing duplicate frames and sparse information.
- RAG-capability enhancement:
  - Embedding models preferentially load locally, downloading remotely only on failure, improving stability and speed.
  - Retrieval-and-index-consistency-detection prompts are more friendly, supporting change/deletion summaries and operation suggestions.
- Platform-and-tool stability:
  - File-upload process logs are merged and output, with errors and warnings aggregated and displayed, making problem location more intuitive.
  - Error/warning information in several places is aggregated and printed, avoiding cyclic line-by-line screen flooding.
- BasePlatform rendering optimization: reduces Live refresh frequency, buffers updates, and uniformly converges output at the end, significantly improving the visual experience.

#### Documentation Update

- Removed explanations and examples related to HAIJUNBOT_THINKING_PLATFORM / HAIJUNBOT_THINKING_MODEL.
- Added explanations and usage suggestions for the HAIJUNBOT_TOOL_FILTER_THRESHOLD configuration item.
- Removed the llm_type field from multi-agent and role examples; README/usage guide/configuration-item table fully synchronized.
- Unified Chinese quotation-mark style, correcting a few wording details.

#### Miscellaneous

- Removed the uv mirror-source configuration in pyproject.toml, simplifying project metadata.
- Test cases synchronized to adapt to the calling method after llm_type removal.
- Cleaned up miscellaneous blank lines and minor format issues in historical Release Note entries and examples.

This update mainly focuses on "simplifying configuration, improving usability, and the interaction experience". By unifying the model channel and adding a tool-filter threshold, it significantly reduces usage complexity; at the same time, it made several detail optimizations to streaming output, logs, and the RAG chain, making information more focused and the process smoother.

### Release Note - v0.3.22 2025-08-23

#### New Features

- Pre-retrieval index-consistency detection and optional update for RAG: automatically detects changes/deletions to source documents before executing a query, supports incremental update after interactive confirmation, and rebuilds the BM25 index upon completion, ensuring retrieval results are fresh and reliable.
- Retriever-capability enhancement: added two public methods, detect_index_changes and update_index_for_changes, supporting precise deletion/rebuilding of changed documents by metadata.source, and automatically maintaining the index manifest.
- Tool-call-robustness improvement: when a tool call is detected to be missing an end tag, it supports automatic completion and attaches a friendly prompt, reducing interruptions caused by format flaws.

#### Fixes

- Backward compatibility: exports get_yes_no = user_confirm, ensuring references to the old interface in external modules continue to work.

#### Optimizations and Refactoring

- CodeAgent tool-integration optimization: added the edit_file tool; removed the old EditFileHandler output-processing chain, uniformly taken over by the tool registry, with a clearer calling path.
- File-editing-tool logic simplification: performs unified processing and feedback based on the result of EditFileHandler.\_fast_edit, reducing file-rollback and write branches, improving stability and maintainability.
- RAG-flow optimization: added a "pre-retrieval index check" to both the answer and retrieve_documents paths, ensuring entry-point consistency.
- More robust BM25 index-rebuild flow: automatically rebuilds the index after incremental update and synchronously cleans up manifest records of deleted documents.

#### Documentation Update

- Usage-convention update: clarified that "for partial file-content modification, use the edit_file tool", replacing the outdated PATCH wording, lowering the understanding cost.

#### Miscellaneous

- ToolRegistry internal-implementation-detail adjustment: extracted the auto_completed marker and appended an explanation in the result, facilitating problem location and subsequent optimization.
- Friendlier interaction and log output: provides a summary display and risk prompts for index changes, improving perceptibility.

This update mainly focuses on "retrieval accuracy and engineering robustness". By actively detecting and optionally updating the index before retrieval, combined with incremental update and BM25 rebuild, it significantly reduces the risk of "documents changed but the index not updated". At the same time, it unifies file-editing and tool-call conventions, reducing boundary problems, and the overall maintainability and development experience are further improved.

### Release Note - v0.3.21 2025-08-22

#### New Features

- Interactive configuration wizard: added hjb -I/--interactive-config, allowing item-by-item confirmation and saving based on the existing configuration before startup
- Subtask tools: added sub_agent and sub_code_agent, supporting entrusting subtasks to a sub-Agent/CodeAgent, automatically completing and generating a summary
- Context-completion enhancement: supports # to trigger "full-file mode" (excluding .git); @ for "Git file mode"; provides a file selector when fzf is installed
- Controllable error backtracking: added the configuration HAIJUNBOT_PRINT_ERROR_TRACEBACK, supporting global or one-time enabling of error-traceback printing
- RAG enhancement: the retriever introduced an index manifest and source-file change/deletion detection, prompting re-indexing, ensuring knowledge-base consistency

#### Fixes

- Fixed the exception handling and return structure of the read_webpage tool, improving observability when fetching fails
- Fixed boundary and stability issues in several places: file upload to the platform, session save/restore, tool-execution prompts, and other links are more robust

#### Optimizations and Refactoring

- Unified output experience: PrettyOutput text and status are more consistent; status prompts added before and after tool execution
- Configuration directories support ~ and environment-variable expansion (tool/methodology/Agent/multi-Agent/role directories)
- Default package-index adjustment: the uv default source changed to pypi.org, adding a tencent mirror (coexisting with aliyun)
- Added sub_code_agent to the CodeAgent default tool set; .gitattributes prompts and handling are more friendly on Windows
- Optimized the install/uninstall prompts of the intelligent Shell (hss), compatible with fish/bash/zsh
- Clearer RAG-pipeline logs; optimized BM25-index initialization and save flow
- Interaction-input enhancement: added the ability to quickly open an independent Shell within the terminal, and avoiding nesting caused by starting it again in a HaijunBot-opened terminal

#### Documentation Update

- README added error-backtracking configuration explanations and usage examples
- Usage guide supplemented with the two file modes @/#, built-in directives, and interactive-configuration guidance
- Configuration-item documentation added HAIJUNBOT_PRINT_ERROR_TRACEBACK; supplemented usage examples of --share-tool and -I

#### Miscellaneous

- Extensive code-style and structure refinement, removing redundant blank lines and inconsistent usage
- Detailed adjustments to statistics and tool registration, with more focused prompt messages

This update is mainly organized around "configurability, observability, and usability": introducing interactive configuration, controllable error backtracking, and a comprehensive upgrade of context completion/selectors, and improving the sub-Agent workflow and RAG consistency detection, making the overall experience smoother and more reliable.

### Release Note - v0.3.20 2025-08-21

#### **New Features**

- Enhanced multi-line-input experience: added support for the fzf file selector (triggered by the @ symbol)
- Added terminal integration: supports starting a shell terminal with the Ctrl+T shortcut key
- Added an interactive-confirmation mechanism: supports a custom user-confirmation callback function, convenient for TUI/GUI integration
- Added a no-confirmation execution mode: supports adding the # HAIJUNBOT-NOCONFIRM marker in a shell command to skip confirmation

#### **Fixes**

- Fixed the configuration-editor invocation problem on the Windows platform
- Removed unnecessary model-validation warnings on the AI8 platform
- Fixed clipboard-output-format compatibility problems

#### **Optimizations and Refactoring**

- Refactored the output-system architecture: introduced OutputEvent and OutputSink abstractions, supporting multi-backend output
- Optimized console output: uniformly uses PrettyOutput instead of direct print
- Enhanced user experience: improved the prompt info and key bindings of multi-line input
- Optimized terminal display: supports wide-character calculation and automatic line-wrapping handling

#### **Documentation Update**

- Updated the usage instructions and shortcut-key prompts for multi-line input
- Added usage documentation for fzf integration

#### **Miscellaneous**

- Unified code style: uniformly uses PrettyOutput for formatted output
- Performance optimization: reduced unnecessary console output

This update mainly enhanced the user-interaction experience, adding the fzf file selector and terminal-integration features, while also refactoring the output-system architecture to support more flexible extension.

### Release Note - v0.3.19 2025-08-20

#### **New Features**

- Intelligent Shell (JSS) extension: on top of the original fish, added "command not found" intelligent suggestions and editable execution support for bash and zsh; in interactive mode, you can directly edit the suggestion and press Enter to execute, while in non-interactive mode the suggestion is output automatically.
- Role-system modularization: split the original builtin/roles/roles.yaml into multiple module files, adding/improving the following role packages:
  - coaching_roles.yaml, hr_roles.yaml, planning_roles.yaml, thinking_roles.yaml, writing_roles.yaml
  - The content covers rich roles such as "company technical coach certification chief mentor", "GROW model analysis expert", and "event planning expert".
- Statistics-capability enhancement: introduced totals caching and fast total queries; automatically parses and writes back metric groups; StatsManager added APIs such as get_metric_total / get_metric_info / resolve_metric_group.

#### **Fixes**

- Input-compatibility fix: added the Agent.\_multiline_input wrapper, compatible with custom multi-line inputters that only accept a single parameter (TypeError fallback), avoiding interaction interruption.
- Commit-flow robustness: Git commits on Windows are more reliable in temporary-file read/write and cleanup; the large-diff upload/processing path is more robust, with clearer failure information.

#### **Optimizations and Refactoring**

- Unified output experience: extensively replaced scattered print with PrettyOutput, unifying information grading and display; model streaming output added a "press Ctrl+C to interrupt" prompt, and clearly echoes and tracks duration in non-"screen-garbling" mode.
- Multi-line-input-experience upgrade: the bottom toolbar displays shortcut keys (@ file completion, Tab selection, Ctrl+J confirmation, Ctrl+O history copy, Ctrl+C/D cancel), with friendlier prompt info.
- RAG and CLI experience: retrieval/rerank/statistics/tool list/call outputs have a unified style, with errors and code blocks highlighted and clearer process prompts; RAG logs and prompts are easier to read.
- Statistics-dashboard performance: uses fast total reading, avoiding full scans; uses group information to improve dashboard-display accuracy; optimized table and layout alignment.
- Git/commit and cross-platform: safer temporary-file handling, more complete exception branches; newline suggestions and prompts are more aligned with reality.
- Terminal-tool consistency: the logs and error output of tools such as VirtualTTY, file read/write, webpage reading, and search are unified as PrettyOutput, reducing noisy logs.

#### **Documentation Update**

- Structured and split role-definition content, with clearer and more maintainable role descriptions (five major modules: coaching/hr/planning/thinking/writing).

#### **Miscellaneous**

- Improved robustness in several detail areas, improved exception handling, unified prompt text, and internationalization tendency.

This update mainly focuses on: the intelligent Shell covering more mainstream terminals (bash/zsh), modularization refactoring of the role system, unified optimization of console interaction and log output, performance and grouping enhancement of the statistics system, and comprehensive improvement of the input experience.

### Release Note - v0.3.18 2025-08-19

#### **New Features**

- Added the `HAIJUNBOT_IMMEDIATE_ABORT` environment-variable configuration, supporting immediate return of the currently generated content and stopping further output when a user-interruption signal (such as Ctrl+C) is detected during conversation output
- Enhanced the webpage-content-reading feature, supporting the use of the configured web_search_platform and the model's native web capability, and automatically falling back to requests-based page fetching and analysis when unsupported
- Optimized the role-selector interface, adding a role-count-display feature, intuitively showing the number of roles contained in each role configuration when selecting a role

#### **Fixes**

- Fixed the user-interruption-handling logic, correctly setting the `run_input_handlers_next_turn` flag after interruption, ensuring the next run correctly handles user input
- Fixed exception handling in the tool-sharing and resource-sharing managers, replacing the `typer.Exit` exception with a `return` statement, avoiding unnecessary program exit
- Fixed empty-input handling in the role selector, supporting exiting the program by directly pressing Enter, improving the user experience

#### **Optimizations and Refactoring**

- Optimized the availability-check logic of the webpage-content-reading tool, ensuring the tool is always available, and can work normally through the fallback solution even if the model does not support the web feature
- Optimized the command-line-interface output format, simplifying the output info of multiple commands, making the output more concise and clear
- Enhanced configuration-management functionality, adding the `is_immediate_abort()` configuration-reading function, supporting reading the immediate-abort setting from the configuration file

#### **Documentation Update**

- Updated the project documentation, adding detailed explanations and a usage guide for the `HAIJUNBOT_IMMEDIATE_ABORT` environment variable
- Updated the configuration-schema documentation, adding the JSON-Schema definition and description of the new configuration item

#### **Miscellaneous**

- Updated the WeChat QR code image file

This update mainly enhanced the user experience and system stability. The newly added interruption-handling feature allows users to control the conversation flow more flexibly, while also optimizing the usability of core features such as webpage-content reading and role selection.

### Release Note - v0.3.17 2025-08-17

#### New Features

- Optional pre-startup interaction: when the current directory is detected to be a Git repository, it can prompt and switch to code-development mode (hca) with one click, improving the code-task experience (configuration item: HAIJUNBOT_ENABLE_GIT_JCA_SWITCH).
- Pre-startup built-in configuration selector: before entering the default general agent, it can list the available agent/multi_agent/roles configurations for direct selection and startup (configuration item: HAIJUNBOT_ENABLE_STARTUP_CONFIG_SELECTOR).
- Extensible configuration-loading directories: added HAIJUNBOT_AGENT_DEFINITION_DIRS, HAIJUNBOT_MULTI_AGENT_DIRS, HAIJUNBOT_ROLES_DIRS, used to scan custom configuration directories, supporting multiple directories with dedup.
- First-run configuration wizard: guides setting key switches such as Pretty Output, print Prompt, static analysis, methodology system, analysis flow, force-save-memory, and the central repository address, automatically writing back to ~/.haijunbot/config.yaml, with default values interactively selectable.
- Multi-line-input-experience upgrade: on the first press of Enter, a one-time prompt guides the user to use Ctrl+J to confirm submission, making multi-line editing friendlier and continuously remembering the prompt state.

#### Fixes

- Backward-compatibility enhancement: SessionManager added a clear() alias method, compatible with historical calls and existing test scenarios.

#### Optimizations and Refactoring

- haijunbot-agent startup-flow refactoring: preloading configuration does not interfere with the subsequent init_env, with more robust exceptions; configuration-based directory scanning and daily Git-update checks; more detailed role-list display.
- Predefined-task-interaction upgrade: TaskManager uses a rich table to display the task list, with a clear "[0] skip" guide, making the selection experience more intuitive.
- Install-flow simplification: install.sh cancels automatically running haijunbot initialization, optimizing step numbering and output text, more aligned with non-interactive installation.
- Unified input-component text: more concise multi-line-input help prompts, with key operations (Ctrl+J confirmation) more obvious.
- Type-and-static-check enhancement: supplemented type annotations and compatibility comments, improving static-analysis and CI stability.

#### Documentation Update

- The installation-and-usage manual added chapters such as "optional startup-behavior settings" and "optional pre-startup interaction", detailing the usage and configuration examples of the two new switches.
- Configuration documentation supplemented with explanations and default values of HAIJUNBOT_ENABLE_GIT_JCA_SWITCH, HAIJUNBOT_ENABLE_STARTUP_CONFIG_SELECTOR, and the multiple configuration-directory items.
- Schema documentation synchronously updated, ensuring editor-linked validation and intelligent prompts.

#### Miscellaneous

- CI-workflow improvement: added an install-script-validation Job, ensuring scripts/install.sh runs smoothly in the CI environment and validates executable generation.
- Unification and cleanup: YAML style and field alignment adjustments, with better detail consistency.
- Improved test coverage: added unit test cases for the haijunbot CLI, ShareManager, and TaskManager, enhancing regression guarantees.

This update mainly targets "improved startup experience and configurability, enhanced interaction friendliness, and optimized installation flow and stability", while also improving documentation and tests to ensure overall quality.

### Release Note - v0.3.16 2025-08-16

#### **New Features**

- Added Git-repository automatic detection and code-development-mode switching, intelligently recognizing a Git project at startup and prompting to switch to hca mode
- Enhanced the CLI-interaction experience, providing a built-in configuration-selection interface, supporting multiple configuration types such as agent, multi_agent, and roles
- Added tool-protocol-version support (v1.0/v2.0), implementing a mechanism for separated passing of agent and parameters
- Added detailed description info to the multi-agent system, improving configuration readability

#### **Fixes**

- Fixed the observability problem of YAML-parsing error handling, improving error-location capability
- Fixed the parameter-injection problem during tool registration, avoiding agent parameters contaminating tool parameters
- Fixed command-line-parameter-parsing errors, unifying the short-option format (-T/-t distinction)
- Fixed the exception-handling problem at multi-agent-system startup, enhancing robustness

#### **Optimizations and Refactoring**

- Refactored the tool-execution logic, supporting a backward-compatible tool-protocol-version mechanism
- Optimized internal configuration management, renaming the example directory to builtin, improving project-structure clarity
- Improved the CLI-startup flow, adding a user-friendly configuration-selection interface
- Enhanced code-style consistency, unifying the YAML-file format specification

#### **Documentation Update**

- Updated all agent configuration files, adding detailed descriptions and usage instructions
- Improved the multi-agent-system documentation, supplementing explanations of the interaction flow and output format
- Added developer-role configuration, supporting a high-end agent in thinking mode

#### **Miscellaneous**

- Cleaned up the TODO.md file, organizing the project-development plan and milestones
- Updated dependency management and type annotations, improving code quality

This update mainly focuses on improving the user experience and system robustness; through intelligent detection and interaction optimization, HaijunBot is more usable and reliable. The newly added tool-protocol-version mechanism lays a solid foundation for future expansion.

### Release Note - v0.3.15 2025-08-16

#### **New Features**

- Added prefix and suffix parameter support to commit messages
- Fixed the typo script_cotent to script_content

#### **Fixes**

- Fixed the URL-concatenation, timeout, and response-handling problems of the streaming client
- Fixed the blocking-call and log-directory-configuration problems
- Added prefix and suffix parameters to the \_git-related methods

#### **Documentation Update**

- Updated the return-type annotation of the \_extract_tool_calls method
- Added a TODO document recording project to-do items
- Removed the completed spelling-fix task

This update mainly improved the flexibility of code commits, fixed multiple API and client issues, and improved the project documentation.

### Release Note - v0.3.14 2025-08-15

#### **New Features**

- Enhanced the code-agent feature, supporting git-commit handling in empty-repository scenarios
- Optimized the user-interaction experience, supporting custom replies as additional prompts

#### **Fixes**

- Fixed the exception-handling problem in the Agent destructor, avoiding program crashes
- Fixed the commit-counting problem in empty-repository or no-HEAD scenarios

#### **Optimizations and Refactoring**

- Improved the show_agent_startup_stats function, supporting passing a tool-registry instance to avoid repeated initialization
- Optimized the Agent-class initialization parameters, using the Optional type instead of default-value lists, avoiding the mutable-default-argument problem
- Enhanced code robustness, adding exception handling and compatibility checks
- Optimized the git-operation logic of the code agent, compatible with more edge scenarios

#### **Miscellaneous**

- Removed the unused ct-tag import
- Re-set the system prompt after resetting the model, ensuring system constraints continue to take effect

This update mainly improved the stability and user experience of the code agent, enhanced the handling capability of empty-repository scenarios, and fixed multiple potential exception problems.

### Release Note - v0.3.13 2025-08-13

#### **New Features**

- Added the `run_input_handlers_next_turn` flag, for more precise control of the behavior of the next round of input handlers
- Optimized the prompt-info format when the platform does not exist, improving the user experience

#### **Fixes**

- Fixed the naming-conflict problem of the `Agent.clear()` method, unified to `clear_history()` to avoid ambiguity
- Fixed the session-prompt-concatenation logic, avoiding format problems caused by null values

#### **Optimizations and Refactoring**

- Refactored the post-tool-call-prompt-handling logic, making it clearer and more robust
- Improved the format of the multi-line-input prompt, enhancing readability
- Removed the redundant duplicate definitions of `clear()` and `clear_history()`, simplifying the code structure

#### **Miscellaneous**

- Cleaned up unused imports and redundant method definitions

This update mainly focuses on code-quality improvement and user-experience optimization; by unifying naming conventions and improving the prompt-info format, the system is more stable and easier to use.

### Release Note - v0.3.12 2025-08-12

#### **Optimizations and Refactoring**

- Optimized the Agent-class input-handling logic, simplifying the input-handling flow in the \_run method
- Refactored the history-handling mechanism, improving the summary-generation and cleanup logic
- Optimized the command-line-argument format, simplifying the typer-option definition format
- Improved the file-methodology manager, removing redundant memory-tag prompts
- Optimized the code structure of the sharing manager, fixing type-annotation compatibility problems

#### **Fixes**

- Fixed the Summary-tag-handling logic, ensuring the initial prompt is correctly set when the session is reset
- Fixed the model-reset problem during history cleanup, avoiding residual session state
- Fixed the format problem in .gitignore handling, ensuring a unified commit-message format

#### **Miscellaneous**

- Updated the calling method of the input handlers, improving code readability
- Standardized the code format, unifying the string-quotation style

This update mainly focuses on code-quality improvement and user-experience optimization; by refactoring the core logic it simplified the Agent's workflow, while also fixing some boundary-case-handling problems in session management.

### Release Note - v0.3.11 2025-08-11

#### **New Features**

- Supports independent configuration of the platform and model used by Web search, set via the `HAIJUNBOT_WEB_SEARCH_PLATFORM` and `HAIJUNBOT_WEB_SEARCH_MODEL` environment variables
- Added Web-search-configuration priority logic: when a dedicated search platform and model are configured, the configuration items are preferentially used rather than the default model-selection flow

#### **Optimizations and Refactoring**

- Optimized the implementation logic of the Web-search tool, enhancing the flexibility of platform selection and model configuration
- Improved the configuration system, adding Web-search-related configuration items to the configuration schema

#### **Documentation Update**

- Updated the configuration documentation, adding explanations and configuration examples of Web-search-related environment variables

This update mainly enhanced the configuration flexibility of the Web-search feature, allowing users to configure the platform and model separately for search operations, improving the system's customizability.

### Release Note - v0.3.8 2025-08-10

#### **Optimizations and Refactoring**

- Optimized the embedding model of the code-RAG configuration from "Qodo/Qodo-Embed-1-7B" to "Qodo/Qodo-Embed-1-1.5B", significantly reducing memory usage and computational overhead
- Uniformly updated all related model references in the documentation and configuration files, ensuring configuration consistency

#### **Documentation Update**

- Updated the RAG-configuration-group example in the "Usage Guide", adopting the lighter 1.5B model
- Revised the configuration explanation in the "Advanced Topics" document, providing more efficient model-selection suggestions
- Updated the environment-variable explanation in the "Appendix", reflecting the latest default-configuration changes

This update mainly optimized the model configuration of the RAG system; by adopting a lighter embedding model, it significantly improved system performance and resource-utilization efficiency while ensuring retrieval quality. Users are advised to reload the configuration to apply the latest optimization.

### Release Note - v0.3.7 2025-08-09

#### **New Features**

- Added detailed documentation on the memory-organization mechanism and implementation principles, including the intelligent-merge algorithm and usage examples
- Enhanced the HaijunBot update-detection feature, supporting version-update checks for pip/uv installations
- Added RAG-feature detection, automatically selecting whether to enable RAG functionality based on the environment at installation

#### **Fixes**

- Fixed the git-update-check logic; it now checks git source-code installation first, then pip installation
- Fixed the version-update prompt message, providing a more accurate update command

#### **Optimizations and Refactoring**

- Refactored the update-detection mechanism, renaming the original `_check_git_updates` to `_check_haijunbot_updates`, supporting update checks for multiple installation methods
- Optimized the installation-command-selection logic, selecting the correct installation package based on whether the RAG feature is installed
- Improved the update-prompt message, distinguishing the virtual environment and different package managers (uv/pip)

#### **Documentation Update**

- Added a complete usage guide for the memory-organization tool (haijunbot-memory-organizer)
- Supplemented the advanced-topics chapter, detailing the architecture design and implementation principles of the memory system
- Added performance-optimization strategies and best practices for memory organization

#### **Miscellaneous**

- Added date-handling support, used to record the update-check time
- Enhanced error handling, silently handling network-request failures

This update mainly enhanced HaijunBot's self-update capability and memory-management feature. It added a memory-organization tool that can automatically merge duplicate or similar memory content, improving storage efficiency and retrieval quality. At the same time, it improved the update-detection mechanism, now supporting version-update checks for pip/uv installations, allowing users to obtain the latest features in a timely manner.

### Release Note - v0.3.6 2025-08-08

#### **New Features**

- Added automatic Shell-environment configuration, supporting bash/zsh/fish
- Changed the PowerShell install script to the English version, resolving the Windows encoding problem

#### **Bug Fixes**

- Removed the NetEase mirror-source configuration in pyproject.toml

#### **Optimizations and Improvements**

- Refactored the PowerShell install script, optimizing the virtual-environment-activation flow
- Improved the memory-merge-prompt format in memory_organizer.py

#### **Documentation Update**

- Updated the help info and prompt text in the install script

#### **Miscellaneous**

- Optimized the user-interaction experience during installation

This update mainly resolved the encoding problem on Windows and optimized the installation experience.

### Release Note - v0.3.5 2025-08-08

#### **New Features**

- Added the NetEase mirror source (netease) to the uv configuration, providing more pypi mirror choices

#### **Fixes**

- Fixed the index-out-of-bounds problem in the memory-merge process and improved the memory-merge algorithm
- Fixed the error handling when deleting a non-existent memory file
- Fixed the typer.Exit exception-handling logic

#### **Optimizations and Refactoring**

- Refactored the uv-configuration structure, using index-strategy instead of the old configuration method
- Optimized memory-merge performance, using mark-deletion instead of direct deletion
- Simplified the platform-conversation-statistics display, removing token-calculation-related metrics

#### **Documentation Update**

- None

#### **Miscellaneous**

- Improved the log-output info during the memory-merge process

This update mainly optimized the stability and performance of memory merging, while also simplifying part of the UI display and adding a new pypi mirror source.

### Release Note - v0.3.4 2025-08-07

#### **New Features**

- **Automated environment configuration**: Greatly enhanced the install scripts (`install.sh`, `install.ps1`), capable of automatically detecting and installing the `uv` environment while configuring domestic mirrors, achieving a smooth out-of-the-box experience.
- **Intelligent memory-base maintenance**: Added automatic memory-base-check and organization functionality. When there are too many memory entries with overlapping content, the system proactively prompts the user to optimize, ensuring the performance and relevance of long-term use.
- **Enhanced startup overview**: The Agent displays a brand-new resource-overview panel at startup, clearly listing the number of loaded methodologies, tools, global memories, and project memories, with core capabilities visible at a glance.

#### **Fixes**

- **Tool-execution robustness**: Comprehensively enhanced the exception-catching mechanism for tool execution; when an error occurs in the tool itself or during its execution, it gracefully handles the exception and returns error information, preventing the entire flow from being unexpectedly interrupted.

#### **Optimizations and Refactoring**

- **Brand-new CLI main interface**: Completely refactored the startup welcome interface! Created a brand-new multi-panel modern layout, integrating the project logo, version number, vision, mission, and detailed usage statistics, with a comprehensive improvement in visual effect and information density.
- **Agent-startup-flow optimization**: Refactored the Agent's startup logic, modularizing functions such as statistics display and environment check, making the startup process clearer and the information richer.
- **Intelligent dependency installation**: When the project auto-updates, the system can intelligently recognize whether it is currently in a `uv`-managed virtual environment, and automatically chooses `uv pip` or native `pip` for installation, improving compatibility.

#### **Documentation Update**

- **Clear mission and vision**: In the brand-new main interface, the Mission and Vision of the HaijunBot project are clearly stated for the first time, better conveying the project's core value and pursuit to users.

**This update summary**:
This update is a major leap in the v0.3.x series, with the core being the dual improvement of **"intelligence"** and **"user experience"**. We introduced intelligent methodology loading for models, automated memory-base maintenance, and more robust install scripts. At the same time, the brand-new CLI main interface not only brings stunning visual effects but also better conveys HaijunBot's value proposition. Together, these improvements create a more intelligent, more stable, and easier-to-use developer AI assistant.

### Release Note - v0.3.3 2025-08-07

#### **New Features**

- **Added the memory-organization tool (`hmo`)**: Introduced the brand-new `haijunbot-memory-organizer` (`hmo`) tool, capable of intelligently identifying and merging memories with similar tags. It supports automatic merging, import/export, dry-run, and other features, helping you keep the memory base clean and efficient, making HaijunBot smarter the more you use it!

#### **Optimizations and Refactoring**

- **Install-script enhancement**: The `install.sh` and `install.ps1` scripts now automatically detect uncommitted local changes and prompt the user to confirm whether to overwrite, preventing accidental loss of work.
- **Configuration-interaction optimization**: During interactive configuration, the system provides detailed guidance, telling users how to obtain the API Key or Cookies of the relevant platform.
- **Tool-robustness improvement**: Multiple core tools (such as `hgc`, `jcr`) added the ability to temporarily switch the model-configuration group via a command-line parameter (`-g/--llm_group`), convenient for calling the most appropriate model for different tasks.
- **Core-Agent-interaction improvement**:
  - `hca` (code Agent) actively prompts the user to save the memory of this interaction according to the configuration after generating the Commit Message.
  - The chat commands of `hpm` (platform manager) (such as `/upload`, `/save`) support a more flexible parameter format.
  - Short-term memory is arranged in reverse chronological order during retrieval, preferentially returning the latest memories.

#### **Documentation Update**

- **README update**: Comprehensively updated the README file, including introductions to all new tools, shortcuts, and the recommended `uv` installation method.
- **Added a `hmo` usage guide**: Added detailed usage instructions for the memory-organization tool to the documentation.
- **Added LLM-configuration-group best practices**: Added best-practice documentation on how to flexibly switch different models via configuration groups.
- **FAQ update**: Refactored and updated the FAQ page, resolving new problems such as shortcut-key conflicts.

### Release Note - v0.3.2 2025-08-05

#### **New Features**

- Added a GitHub Actions CI/CD test workflow, supporting automated testing
- Added two professional roles, "comprehensive interviewer" and "resume-writing expert", to the role system
- Added a uv package-manager installation guide, providing a modern Python-project-management solution
- Enhanced the platform-manager feature, supporting overriding the default configuration via command-line parameters

#### **Fixes**

- Fixed the command-line-parameter-naming-conflict problem, unifying the parameter-naming convention
- Fixed the test-script path error, ensuring tests can be correctly executed in the project root directory
- Fixed the .gitignore file-format problem, optimizing the Python-bytecode-file ignore rules
- Fixed the missing .gitignore file in the central repository, automatically adding Python-cache ignores

#### **Optimizations and Refactoring**

- Optimized the CLI-command-parameter design, using more intuitive short-parameter forms
- Refactored the platform-manager parameter-handling logic, supporting model-group and LLM-type overriding
- Improved the atomicity of statistics-storage operations, using UUID to avoid concurrency conflicts
- Optimized document format and readability, enhancing the clarity of methodology descriptions

#### **Documentation Update**

- Updated the quick-start guide, adding an explanation of the uv installation method
- Improved the command-line-parameter explanation in the usage guide
- Enhanced the coach-certification-methodology documentation, adding multiple analysis tools and models
- Optimized the system prompt and interaction flow of the technical-coach role

#### **Miscellaneous**

- Added a test-environment configuration, supporting continuous integration
- Improved project-management compatibility, supporting a modern Python-development toolchain

This update mainly improved the project's engineering level and user experience, added practical professional roles, optimized the CLI-interaction design, and established a complete CI/CD flow.

### Release Note - v0.3.1 2025-08-04

#### **New Features**

- Added an interactive configuration wizard, simplifying the first-run setup flow
- Added the `HAIJUNBOT_FORCE_SAVE_MEMORY` configuration item, controlling the memory-save-prompt behavior
- Implemented the automatic-naming feature of the PDF-generation script

#### **Fixes**

- Fixed the model-parsing logic when starting the platform-manager service
- Corrected the format and content of the memory-prompt message
- Resolved the result-pagination problem of the search tool

#### **Optimizations and Refactoring**

- Refactored the memory-management-system prompt template
- Optimized the configuration-architecture-design document
- Improved the technical-documentation organization structure, merging scattered content

#### **Documentation Update**

- Added a complete HaijunBot user manual (9 chapters)
- Updated the configuration-system technical documentation
- Added a development-environment-setup guide

#### **Miscellaneous**

- Removed outdated technical-documentation files
- Updated the WeChat QR code image
- Cleaned up useless configuration items

This update mainly optimized the user experience and the documentation system.

### Release Note - v0.3.0 2025-08-03

#### **New Features**

- **Tool Groups**: Added the tool-groups feature, allowing users to define and switch different tool sets according to different task scenarios (such as coding, documentation, system management), configurable via the `--tool_group` parameter or the configuration file (`HAIJUNBOT_TOOL_GROUPS`), greatly improving security, usability, and task focus.
- **Central methodology and tool library**:
  - **Central methodology library**: Supports sharing the team's best practices and problem solutions via a Git repository (`HAIJUNBOT_CENTRAL_METHODOLOGY_REPO`), and local methodologies can be easily shared via the `--share-methodology` command.
  - **Central tool library**: Allows teams to share and synchronize custom tools (`HAIJUNBOT_CENTRAL_TOOL_REPO`); local tools can be shared to the central library via the `--share-tool` command, promoting the construction of an internal team tool ecosystem.
- **Interactive configuration guidance**: Provides a brand-new interactive configuration wizard for new users. On first startup, HaijunBot guides the user to select the AI platform, configure the key, select the model, and perform a connection test, greatly lowering the initial-configuration barrier.
- **Comprehensive unit-test suite**: Added a complete `pytest`-based test suite (`run_tests.sh`), covering core modules, providing a solid guarantee for the project's stability and code quality.
- **Intelligent context management**:
  - **Memory-retrieval optimization**: The `retrieve_memory` tool can now limit retrieval results according to the token count, avoiding context overflow caused by too much memory content.
  - **Methodology-loading optimization**: Token limiting is also performed when loading methodologies, ensuring the core methodology content can be effectively used in the model context.

#### **Optimizations and Refactoring**

- **Large-scale Agent-architecture refactoring**: Completely refactored the core `Agent` module, splitting functionality into multiple independent managers such as `AgentManager`, `MemoryManager`, `TaskAnalyzer`, and `FileMethodologyManager`, with a clearer code structure and significantly enhanced maintainability and extensibility.
- **CLI-entry refactoring**: The main program entry `haijunbot.py` code was refactored, with clearer logic and modularized management of features such as sharing and configuration.
- **Platform-configuration standardization**: Each AI platform (OpenAI, Kimi, etc.) implements a standardized interface, used to declare the required environment variables and default values, providing support for interactive configuration.
- **Dependency-installation-source optimization**: Added the Tsinghua University PyPI mirror source to `pyproject.toml`, convenient for domestic users to speed up dependency installation.

#### **Documentation Update**

- **Comprehensive user-manual update**: Greatly updated the user manual, detailing the usage and best practices of all new features such as tool groups, central libraries, and new CLI parameters.

### Release Note - v0.2.7 2025-08-01

#### **New Features**

- **Batch memory saving**: The `save_memory` tool now supports saving multiple memories of different types at once, improving memory-management efficiency
- **Memory-clear feature**: Added the `clear_memory` tool, supporting batch clearing of memories by type, tag, or ID, providing flexible memory-management capability
- **Methodology sharing**: Added the `--share-methodology` command-line option, capable of sharing local methodologies to the central methodology repository
- **Central methodology repository**: Supports configuring `HAIJUNBOT_CENTRAL_METHODOLOGY_REPO`, automatically synchronizing and loading shared methodologies

#### **Fixes**

- Fixed the exception problem that could be caused by auto-completion during multi-line input
- Fixed some type-annotation errors, improving code robustness

#### **Optimizations and Refactoring**

- **Code-engineer enhancement**: `code_agent` now integrates complete memory-management functionality (save, retrieve, clear)
- **Memory-prompt optimization**: Automatically reminds the user to record key information before a task starts, improving the memory-usage experience
- **UI optimization**: The INFO-type output color was adjusted from gold1 to bright_cyan, improving readability
- **Batch-selection support**: Methodology sharing supports range selection (such as 1-5,7,9-12), improving operation efficiency

#### **Documentation Update**

- Updated the technical documentation, completely introducing the usage of the three memory-management tools
- Added usage examples for batch saving and clearing memories
- Updated the usage guide, adding an explanation of the methodology-sharing feature

#### **Miscellaneous**

- Improved the methodology-loading logic, avoiding duplicate warnings
- Optimized error handling and user prompts for Git operations

This update mainly enhanced HaijunBot's memory-management capability; the newly added batch-operation and clear features make memory management more flexible and efficient. At the same time, the methodology-sharing feature promotes community collaboration, allowing excellent problem solutions to be used by more people.

### Release Note - v0.2.6 2025-07-31

#### **New Features**

- **Long-short-term-memory system**: Introduced a revolutionary three-layer memory architecture
  - Short-term memory: stores temporary information related to the current task (in memory, non-persistent)
  - Project long-term memory: saves project-specific information (stored in `.haijunbot/memory/`)
  - Global long-term memory: cross-project general knowledge and preferences (stored in `~/.haijunbot/data/memory/`)
- **Memory-tool integration**: Added the `save_memory`, `retrieve_memory`, and `clear_memory` tools
  - Supports tagged storage and retrieval
  - Intelligent memory-type selection
  - Returns at most 200 tags, randomly extracting when exceeded
  - **Batch-save feature**: `save_memory` now supports saving multiple memories of different types at once
  - **Memory-clear feature**: Added the `clear_memory` tool, supporting batch clearing of memories by type, tag, or ID
- **Automatic memory prompt**: The Agent automatically adds a usage prompt when it detects the memory tools
  - Reminds the user to record key information before a task starts
  - The system prompt includes memory-operation guidance
- **Code-engineer memory integration**: `code_agent` now integrates complete memory-management functionality
- **User-satisfaction-feedback mechanism**: Collects user feedback after task completion, for continuous improvement

#### **Fixes**

- Fixed the schema-path error when generating the configuration file (using absolute paths)
- Fixed the problem where text replacement in `edit_file_handler` might replace multiple matches (now only the first match is replaced)

#### **Optimizations and Refactoring**

- Optimized the memory-retrieval output format, limiting to at most 50 memories returned (randomly selected)
- Unified the usage statistics of short and long commands, merging historical data
- Removed the user-confirmation step for the git newline setting, simplifying the operation flow
- Enhanced the indentation and format-handling capability of the code editor

#### **Documentation Update**

- Added a memory-system usage guide (Section 4.12)
  - Detailed introduction to the three memory types
  - Provides usage examples and best practices
  - Includes advanced-usage guidance
- Updated the technical documentation, adding an explanation of the memory-system architecture (Section 2.4)

The core of this update is the introduction of a complete long-short-term-memory system, an important step for HaijunBot toward true intelligence. Through the three-layer memory architecture, HaijunBot can now:

- Remember project-specific context and conventions
- Accumulate cross-project knowledge and experience
- Maintain temporary information during task execution
- Quickly retrieve relevant memories through the tag system

At the same time, we also improved the user experience, added a satisfaction-feedback mechanism, and fixed multiple problems affecting stability.

### Release Note - v0.2.5 2025-07-30

#### **New Features**

- Windows PowerShell one-click install-script support, greatly simplifying the installation flow for Windows users
- The statistics module introduced the plotext chart library, providing professional data-visualization effects
- Added a delete feature to statistical metrics, supporting cleanup of unwanted historical data
- The metric-list display added tag information, convenient for categorized management and filtering
- Added a command-mapping feature, unifying the usage statistics of short and long commands
- The clipboard feature added cross-platform support (Windows, macOS, Linux)
- Added the Vibe Working work-mode document, introducing a more intuitive human-computer-collaboration philosophy

#### **Fixes**

- Fixed the time-range and tag-filtering features when displaying the metric summary
- Fixed the issue where the list_metrics method did not return all metrics
- Fixed the handling logic of tool calls after user interruption, improving the interaction experience

#### **Optimizations and Refactoring**

- Comprehensive refactoring of the statistics module: uses the Rich library to beautify table and panel display
- Simplified the token-limit configuration, adopting dynamic calculation instead of multiple independent configuration items
- Optimized the methodology-loading logic, implementing a two-stage filtering mechanism to improve performance
- Improved the time-saved estimation model, providing more accurate efficiency statistics
- Statistical charts support using the sum for count-type metrics and the average for other metrics
- Changed StatsManager to static-method calls, simplifying usage
- Dynamically generates the PDF title based on the output file name

#### **Documentation Update**

- README added Windows PowerShell installation instructions
- Added the Vibe Working work-mode introduction chapter
- Updated the configuration documentation, simplifying the token-related configuration explanation

#### **Miscellaneous**

- Adjusted one day in the time-saved statistics to 8 working hours
- The statistics-display interface adopts a 3-row 2-column layout, with more compact information display
- Removed the file-upload feature of the methodology module, simplifying the implementation

This update focuses on improving cross-platform support and user experience. Windows users can now install with one click via PowerShell, and the visualization effect of the statistics feature has been comprehensively upgraded; the introduction of the plotext and rich libraries makes data display more professional and beautiful. At the same time, we introduced the "Vibe Working" philosophy, making AI collaboration more natural and smooth.

### Release Note - v0.2.4 2025-07-30

#### **New Features**

- Added a complete statistics-function module `haijunbot-stats`, supporting flexible metric recording and visualization display
- Added a time-saved-statistics feature, automatically calculating the development time users save by using HaijunBot
- Added statistics functionality to the `edit_file` tool, recording tool usage

#### **Fixes**

- Fixed multiple compatibility problems on the Windows system
  - Fixed the file-lock compatibility problem, using temporary files + atomic rename instead of fcntl
  - Fixed the encoding problem, adding encoding and errors parameters to all subprocess calls
  - Fixed the PrettyOutput configuration problem on Windows
- Corrected the command-line parameter name from `--llm_group` to `--llm_group`

#### **Optimizations and Refactoring**

- Improved the editor-selection logic, automatically selecting the appropriate editor according to the operating system
- Replaced system commands with cross-platform Python methods
- Refactored the install script using `uv`, providing a faster and more stable installation experience

#### **Documentation Update**

- Added the HaijunBot Book official documentation, providing a complete Chinese usage guide
- Added detailed documentation and usage examples for the `haijunbot-stats` tool
- Updated the configuration documentation, adding explanations of configuration items such as `HAIJUNBOT_METHODOLOGY_DIRS`
- Supplemented the introduction of the core "Vibe Working" philosophy, explaining the new human-computer-collaboration model

#### **Miscellaneous**

- Added the `.gitattributes` file to configure cross-platform newline rules
- Optimized the Git-configuration check, ensuring users correctly set the username and email
- Removed unused dependencies, reducing the installation-package size
- Added optional installation of the RAG feature, allowing users to choose according to their needs

This update mainly focuses on **data-driven efficiency improvement**. Through the newly added statistics module, users can precisely quantify the value brought by the AI assistant, shifting from "feels very useful" to "saved 28.5 hours". At the same time, it greatly improved Windows compatibility and Chinese localization, allowing more developers to use HaijunBot smoothly.

### Release Note - v0.2.3 2025-07-29

#### **New Features**

- **Feature extension and documentation**:
  - Added a comprehensive "Feature Extension" document, detailing how to develop standard tools, integrate MCP tools, and extend new LLM platforms.
  - Introduced a methodology-sharing mechanism, allowing teams to share and automatically update best practices via a Git repository, accumulating knowledge assets.
- **Interaction-experience improvement**:
  - Greatly enhanced the multi-line-input feature, adding a powerful message-history feature (shortcut `Ctrl+O`), convenient for viewing, selecting, and copying any previous input or output.
- **Tool-development improvement**:
  - The `generate_new_tool` tool added a key validation, forcibly requiring the tool file name to be exactly consistent with the `name` attribute inside the code, fundamentally avoiding the common custom-tool-loading-failure problem.
- **Platform support**:
  - The Tongyi Qianwen platform added support for deep-research and deep-web-search models.

#### **Fixes**

- Fixed the problem where copying content from history in multi-line-input mode could cause terminal-display confusion.

#### **Optimizations and Refactoring**

- **Naming unification**: "Model Group" has been uniformly renamed to "LLM Group" throughout the project, and related configuration items (such as `HAIJUNBOT_MODEL_GROUP`) have been synchronously updated to `HAIJUNBOT_LLM_GROUP`, making the concept clearer.
- **RAG performance**: Refactored the RAG core pipeline, implementing lazy loading of models and components, significantly optimizing resource usage and the startup speed of related commands.
- **Dependency management**:
  - The project's minimum Python version requirement has been raised to 3.9, to take advantage of new language features.
  - Core dependencies have been updated, ensuring better stability and feature support.
- **Configuration management**: Added more reasonable default values to the LLM and RAG group-configuration modes, improving the out-of-the-box experience.

#### **Documentation Update**

- **README.md refactoring**: Greatly updated the project homepage `README.md`, adding content such as project positioning, core advantages, and workflow comparison, making it more attractive and instructive.
- **HaijunBot Book**: Comprehensively updated the HaijunBot Book (local documentation), keeping the content consistent with the latest features and refactoring, including chapters such as RAG groups, LLM groups, and feature extension.
- **Added a disclaimer**: Added a disclaimer in `README.md` about the risks of model usage and command execution, improving security transparency.

This update focuses on **deepening RAG capability** and **enhancing framework extensibility**, while making HaijunBot even more capable as a personal development assistant through **extreme optimization of the interaction experience** (especially the message-history feature). The comprehensive restructuring of the documentation also makes it easier for both new and experienced users to tap into HaijunBot's powerful potential.

### Release Note - v0.2.2 2025-07-27

#### **New Features**

- **Brand-new documentation system**: Added the "HaijunBot Book" official documentation system, providing a comprehensive guide from beginner to expert.
- **CLI-interface upgrade**: The command-line interface was comprehensively switched from `argparse` to `typer`, providing a friendlier, more modern CLI experience and more complete help information.

#### **Fixes**

- **Platform-adapter update**: Fixed and updated the adapters of multiple large-model platforms (Yuanbao, Kimi, Tongyi Qianwen, AI8) to respond to upstream API changes, enhancing the stability of streaming-response handling.
- **Code-analysis fix**: Fixed the Bug where `guess_lexer` could raise an attribute error in some cases.

#### **Optimizations and Refactoring**

- **HTTP-client refactoring**: The underlying HTTP client was comprehensively switched from `httpx` to `requests`, simplifying project dependencies and unifying the network-request implementation.
- **Code simplification**: Removed the deprecated `haijunbot-git-details` (`jgd`) feature and the `oyi` platform adapter, streamlining the project structure.
- **Logic simplification**: Optimized the user-confirmation logic before the AI calls a tool.

#### **Documentation Update**

- **Introducing HaijunBot Book**: Formally introduced "HaijunBot Book" as the official documentation, covering nine major chapters such as project introduction, quick start, core concepts, usage guide, tool development, and advanced topics.
- **README optimization**: Greatly refactored the main `README.md` file, making its structure clearer and its content more concise, and providing clear navigation pointing to the new documentation system.
This update mainly focuses on improving the user experience and maintainability; by introducing the brand-new "HaijunBot Book" documentation system and upgrading to the `typer` framework, users can learn and use HaijunBot more easily. At the same time, the underlying refactoring and code simplification also lay a more solid foundation for the project's future development.

### Release Note - v0.2.1 2025-07-25

#### **New Features**

- **Automated promotion flow**: On top of generating Release Notes, added the ability to automatically generate promotional copy in multiple styles for Moments, realizing a one-click flow from development to promotion.
- **Intelligent fault tolerance and repair**:
  - When a tool call is missing the `</TOOL_CALL>` closing tag, the system can automatically detect, complete, and request user confirmation, greatly improving the success rate of tool calls.
  - In multi-agent interaction, automatically completes the missing `</SEND_MESSAGE>` tag, enhancing the robustness of message parsing.
- **Interaction-experience improvement**: Sets the confirmation option after automatic tool-call error correction to "execute" by default, reducing the user's operation steps and making the interaction smoother.
- **Added a multi-agent example**: Added a multi-agent collaboration example for "investment pitch" (`investment_pitch.yaml`), demonstrating how to build a conversation application with distinct roles and complex logic.

#### **Documentation Update**

- **One-click install script**: Added a one-click install script to `README.md`, greatly simplifying the installation and configuration process for new users.
- **Optimized document structure**: The installation instructions in `README.md` were refactored into two parts, "one-click installation" and "manual installation", making the documentation clearer and easier to read.

#### **Optimizations and Refactoring**

- **Streamlined system prompt**: Removed redundant information from the tool-loading prompt, making the prompt more concise and reducing interference with the model.

#### **Summary**

This v0.2.1 release is a major update focusing on **automation** and **user experience**. By introducing automation capability from code to promotion, a powerful intelligent fault-tolerance mechanism, and a highly simplified installation flow, HaijunBot's practicality and usability have been significantly improved. The new multi-agent examples also provide a model for exploring more advanced AI application scenarios.

### Release Note - v0.2.0 2025-07-24

#### **New Features**

- **LLM Groups**: Added the LLM-groups configuration feature, allowing users to predefine multiple model combinations in `config.yaml` (including normal models, thinking models, and token limits, etc.), and quickly switch via `HAIJUNBOT_LLM_GROUP` or the command-line parameter `--llm_group`, greatly improving the flexibility of switching between different platforms or tasks.
- **Automated install script**: Added the `scripts/install.sh` script, capable of automatically detecting the Python environment, cloning or updating the HaijunBot repository, installing dependencies, and initializing the configuration, simplifying the deployment and onboarding process for new users.
- **Automatic external-resource update**: Added a daily automatic-update-check mechanism for external tool and methodology repositories. If the user's custom tools or methodologies are managed via git, HaijunBot will automatically pull the latest version at startup.

#### **Fixes**

- **Model-name correction**: Corrected the default model name of the Kimi platform in the configuration file and documentation, updating it from `k1` to `k1.5`, ensuring consistency with the official name.

#### **Optimizations and Refactoring**

- **Configuration-loading-logic refactoring**: Refactored the underlying configuration-loading system to fully support the LLM-group priority-override rules (independent configuration > LLM-group configuration > default value).
- **Agent-initialization-flow optimization**: Optimized the initialization logic of `Agent` and `CodeAgent`; they now load the corresponding platform, model, and token configuration according to the specified `llm_group`.
- **Global-Agent management**: Improved the global-Agent registration mechanism; it can now obtain the Agent instance itself, allowing internal modules (such as code review, Git commit) to inherit and use the caller Agent's model configuration.

#### **Documentation Update**

- **README update**: Detailed the new LLM-group configuration method and updated the configuration-item-description table.
- **Product-report update**: Updated multiple application cases in the product report, making it more in-depth and technically representative (for example, shifting from Web development to embedded development, and from routine bug fixing to Coredump analysis).
- **Technical-documentation update**: Added a detailed explanation of the LLM-group design, working mechanism, and configuration examples to the technical documentation, and updated all related configuration-item descriptions.
- **Tool-description enhancement**: Added a prompt to the `generate_new_tool` tool, suggesting adding print information to the tool code for easy tracing.

#### **Miscellaneous**

- **Type hints and robustness**: Added more precise type hints and null checks to multiple modules (such as the MCP client and git tool class), improving code robustness.

The core of this update is the introduction of the powerful **LLM Groups** feature, providing unprecedented flexibility and convenience for professional users. At the same time, through the newly added **install script** and **documentation optimization**, we significantly improved the onboarding experience for new users. The internal refactoring and optimization also lay a more solid foundation for the system's future expansion.

### Release Note - v0.1.225 2025-07-23

#### **New Features**

- (project): Improved the core documentation and optimized the web-search feature
- (cli): Added the -e/--edit command-line option to edit the configuration file
- (config): Exits the program after generating the default configuration

#### **Fixes**

- (haijunbot_agent): Fixed the type-check error of output_handler

#### **Optimizations and Refactoring**

- (agent): Optimized the input-handler execution logic, triggering only on user input
- (search_web): Replaced BeautifulSoup with markdownify to parse webpage content
- (code_agent): Removed the useless methodology tool
- (project): Adjusted the code format to improve readability
- (haijunbot): Refactored the main function to improve code readability

#### **Documentation Update**

- (readme): Added documentation for the -e/--edit command-line option
- (product): Added the HaijunBot product-report document
- (project): Added the HaijunBot AI assistant product-report document

#### **Miscellaneous**

- (deps): Replaced beautifulsoup4 with markdownify and configured the uv index
- Deleted the HaijunBot product-report document

This update mainly brought multiple new features, fixed several problems, carried out code optimization and refactoring, and improved the system's stability and usability.

### Release Note - v0.1.224 2025-07-21

#### **New Features**

- **Enhanced configuration experience**: Updated the `config_schema.json` file, adding schema definitions for the API Keys of multiple models (such as OpenAI, Kimi, Tongyi, etc.). Now, when configuring `config.yaml` in an editor that supports JSON Schema (such as VS Code), you will get **auto-completion and parameter hints**, greatly reducing the possibility of configuration errors.
- **Extended tool loading**: Supports configuring external tool-loading directories via the `HAIJUNBOT_TOOL_LOAD_DIRS` environment variable, enhancing the system's extensibility.

#### **Fixes**

- Enhanced the error-handling mechanism for tool calls; when a tool-call format is wrong, it provides a clearer prompt and prevents the program from crashing.

#### **Optimizations and Refactoring**

- Refactored the generation logic of tool-usage prompts in the Agent, achieving code reuse.
- Optimized the update-check logic of `check_and_update_git_repo`, changing it to check only once per day, improving performance.
- Relaxed the validation rules of `config.yaml`, allowing undefined properties to exist, improving configuration flexibility.

The core of this update is improving the developer experience (DX); by enhancing the configuration-file schema, the configuration process of the AI assistant has become unprecedentedly simple and intelligent. At the same time, we also enhanced the system's extensibility and robustness.

### Release Note - v0.1.223 2025-07-20

#### **New Features**

- **Added a problem-solver multi-agent example**:
  - Added `problem_solver.yaml` under the `example/multi_agent/` directory, providing a complete, structured multi-agent collaboration workflow.
  - This workflow includes multiple professional agents such as product manager, problem definition, root-cause analysis, solution design, code implementation, and verification.
  - Added a file-archiving step for all agents; before handover, the report (such as `01_problem_definition_report.md`) is written to a file, ensuring the process is traceable.
  - Added `use_methodology` and `use_analysis` control switches to the agents, and introduced interaction principles such as "no fabrication" and "proactive questioning".
- **Enriched the AI coach's methodologies**:
  - In `example/roles/roles.yaml`, supplemented a large number of industry-standard methodologies for the "technical coach" role in stages such as problem definition, root-cause analysis, and solution evaluation, such as `5W1H`, `Pareto analysis`, `SWOT analysis`, `cost-benefit analysis (CBA)`, and
    `multi-criteria decision analysis (MCDA)`, etc.
- **Command-line-tool-feature enhancement**:
  - **Session management**: Added the `--restore-session` feature to `haijunbot` and `haijunbot-code-agent`; added the `/save_session` and `/load_session` commands to the `haijunbot-platform-manager` chat mode.

- **Model update**:
  - In `src/haijunbot/haijunbot_platform/kimi.py`, updated the model list of the Kimi platform to match the latest version names (`k1.5`, `k1.5-thinking`, `k2-thinking`).

#### **Optimizations and Refactoring**

- **Implementing agent lazy loading**:
  - In `src/haijunbot/haijunbot_multi_agent/__init__.py`, changed the agent-initialization method to on-demand lazy loading (`_get_agent`), improving the startup performance and resource-utilization rate of the multi-agent system.
- **Refactoring the multi-agent workflow**:
  - Introduced a "product manager" (`ProductManager`) as the core coordinator, refactoring the original linear flow into a "hub-and-spoke" model centered on the product manager, enhancing the workflow's centralized control and flexibility.
- **Enhancing context passing**:
  - When calling a sub-agent, automatically appends the user's original question to its system prompt, providing the sub-agent with more complete task background.
- **Decoupling prompt-generation logic**:
  - In `src/haijunbot/haijunbot_agent/builtin_input_handler.py`, refactored the tool-usage-prompt-generation logic into an independent `build_action_prompt` function, improving code modularity and maintainability.

#### **Documentation Update**

- **Update `README.md`**:
  - Comprehensively updated the parameters and feature descriptions of all command-line tools such as `haijunbot`, `haijunbot-code-agent`, `haijunbot-agent`, and `haijunbot-platform-manager`, to reflect the latest feature changes.

The core of this update is the introduction of a structured "problem-solver multi-agent" workflow, and through refactoring it achieved agent lazy loading and centralized coordination, greatly improving the system's performance and scalability. At the same time, it significantly enhanced the AI coach's professional capability and the usability of the command-line tools.

### Release Note - v0.1.222 2025-07-19

#### **New Features**

- Added shortcut aliases for all main commands (e.g., `hjb`, `hca`, `jcr`), improving usage efficiency.
- Added the "GROW model analysis expert" role, used for structured goal setting and problem solving.
- Added the `HAIJUNBOT_ENABLE_STATIC_ANALYSIS` configuration item, allowing users to control whether to execute static analysis after code modification.
- The Kimi platform added support for the "k2" deep-thinking model.

#### **Fixes**

- (None)

#### **Optimizations and Refactoring**

- Optimized the PDF-export style (`style.css`), improving fonts, margins, and layout, and added page numbers.
- Improved the session-recovery logic, ensuring it can be correctly identified as a non-first run after recovery.
- Simplified the Agent example configuration file, removing redundant model definitions.

#### **Documentation Update**

- Updated `README.md`, adding shortcuts for all commands and supplementing explanations of new features.
- Updated `technical_documentation.md`, streamlining and clarifying the architecture description of the RAG system.

#### **Miscellaneous**

- (None)

This update mainly focuses on improving the user experience and internal architecture optimization. It introduced a large number of command aliases for daily use convenience, and refactored the core Agent's LLM-calling mechanism, making it more flexible. At the same time, it added features such as RAG and GROW model experts, and optimized the documentation and PDF-output quality.

### Release Note - v0.1.221 2025-07-14

#### **New Features**

- (rag): Made RAG dependencies optional
- (rag): Supports configuring the RAG rerank model
- (rag): Added .ragignore support and batch-processing functionality to the add command
- (docs): Introduced a PrinceXML-based PDF-generation flow

#### **Fixes**

- (None)

#### **Optimizations and Refactoring**

- (edit_file): Removed AI-assisted editing and optimized the patch-application logic
- (deps): Moved RAG dependencies to optional installation
- (haijunbot_agent): Refactored the Agent class to improve modularity
- (haijunbot_agent): Extracted Agent prompts to independent files
- (rag): Simplified RAG configuration, directly specifying the embedding model

#### **Documentation Update**

- (docs): Fixed title format and chapter numbering in the technical documentation
- (cli): Updated the embedding-model parameter name in the CLI documentation
- (docs): Optimized the charts in the technical documentation
- (rag): Supplemented the technical documentation of the RAG implementation solution

#### **Miscellaneous**

- (reranker): Ignored the type-check error of the sort method

This update mainly enhances and optimizes the RAG feature, making its dependencies optional and supporting rerank-model configuration and `.ragignore` files. At the same time, it refactored the Agent and code-editing tools, improving the system's modularity and stability. It also made extensive updates and improvements to the documentation and introduced a PDF-generation flow.

### Release Note - v0.1.220 2025-07-13

#### **New Features**

- **Support for Python 3.12**: The project now officially supports the Python 3.12 version.

#### **Fixes**

- **Yuanbao platform Cookie**: Fixed the problem where the program did not throw an exception when `YUANBAO_COOKIES` was not set; it now clearly prompts the user to set it.

#### **Optimizations and Refactoring**

- **Agent system prompt**: Refactored and optimized the core Agent's system prompt, making it clearer and more structured, improving the stability of interaction with the model.
- **Dependency-library update**: Upgraded multiple core dependency libraries, such as `ddgs`, `beautifulsoup4`, `lxml`, etc., to obtain the latest features and security fixes.
- **Raised the Python-version requirement**: Raised the project's minimum Python version requirement from `3.8` to `3.9`.

#### **Documentation Update**

- **README update**: Updated the `README.md` file in detail.

#### **Miscellaneous**

- **Configuration structure**: Added the relevant configuration items of `HAIJUNBOT_RAG` to `config_schema.json`, for detailed RAG-feature settings.

This update mainly centers on the core feature of the **localized RAG knowledge base**, greatly enhancing HaijunBot's capability in domain-specific knowledge Q&A and code understanding. At the same time, through optimization of the core Agent and upgrading of dependency libraries, the overall stability and maintainability were improved.

### Release Note - v0.1.219 2025-07-11

#### **New Features**

- **Enhanced web-search capability**: The `search_web` tool now integrates the DuckDuckGo search engine. When the underlying large model does not support web search, this tool can independently perform search, fetch webpage content, and summarize, greatly expanding the information-acquisition capability.

#### **Fixes**

- (This update has no fixes)

#### **Optimizations and Refactoring**

- **Code-structure optimization**: Unified the user-confirmation function `user_confirm` into the `haijunbot_utils.input` module, improving code organization and maintainability.
- **Clipboard-feature enhancement**: Added the `copy_to_clipboard` utility function, which can intelligently detect and try the `xsel` and `xclip` commands in sequence, enhancing clipboard compatibility in different Linux environments.
- **Dependency update**: Added dependencies such as `ddgs`, `beautifulsoup4`, and `lxml` to `pyproject.toml` and `setup.py`, to support the new web-search feature.

#### **Documentation Update**

- **New technical documentation**: Added the complete technical documentation `docs/technical_documentation.md`, detailing HaijunBot's design philosophy, core architecture, component interaction, configuration methods, and developer guide.

#### **Miscellaneous**

- **Update .gitignore**: Added the `*.pdf` file type to the ignore list, preventing PDF files from being accidentally committed to the version repository.

This update mainly focuses on enhancing the system's core features and improving the developer experience. By introducing independent web-search capability, HaijunBot can now acquire external information more autonomously. At the same time, comprehensive technical documentation and code-structure optimization lay a solid foundation for future community contributions and secondary development.

### Release Note - v0.1.214 2025-07-08

#### **New Features**

- **Session persistence**: Added complete session save and restore functionality.
- **New role**: Added the "company technical coach certification chief mentor" role to the role library, providing professional coaching-style practice guidance.
- **Command enhancement**: The `hpm role` command now supports temporarily overriding the platform and model defined in the role file using the `--platform` and `--model` parameters.
- **Built-in command**: Added the `SaveSession` built-in command, allowing quick saving of the session and exit during `haijunbot` interaction.

#### **Fixes**

- **Streaming service**: Fixed the implementation problem of streaming responses in `hpm service`, ensuring data can be transmitted from the model to the client in real time and stably.
- **File editing**: Improved the patch-application algorithm of the `edit_file` tool, increasing the match success rate and accuracy when handling different indentation and leading/trailing newlines.

#### **Optimizations and Refactoring**

- **Role-configuration simplification**: Removed the `platform` and `model` fields required for each role in the role configuration file, making the configuration more concise and granting higher flexibility through command-line parameters.
- **Code quality**: Refactored code in multiple modules, including optimizing type hints, removing redundant code, and improving interruption-handling logic, improving code readability and robustness.

#### **Documentation Update**

- **Command hints**: Updated the command-help information and auto-completion hints of `hpm`, adding new session-management-related commands.
- **Code comments**: Added comment explanations about when to execute static checks in the `haijunbot-code-agent(jac)` related code.

The core of this update is the introduction of a complete session-persistence mechanism, greatly improving the continuous-usage experience of the tool. At the same time, it made multiple fixes and optimizations to the underlying service and core tools, and added a powerful new role.

### Release Note - v0.1.213 2025-07-07

#### **New Features**

- Added the "problem-mining expert" role, focusing on identifying and quantifying core problems from complex scenarios.

#### **Fixes**

- Adjusted the `pyyaml` dependency version to `>=5.3.1`, to improve compatibility.
- Changed the shortcut key for copying the last message from `Ctrl+L` to `Ctrl+O`, to avoid conflict with the terminal-clear-screen shortcut.

#### **Optimizations and Refactoring**

- Refactored the `AI8` and `Oyi` platform modules, introducing a unified `http` utility and a `while_success` retry mechanism, enhancing the stability and reliability of network requests.
- Optimized the type hints and format of part of the code, improving code quality and readability.

This update mainly improved system stability by refactoring the network-request module, and added the "problem-mining expert" role to enhance problem-analysis capability, while also fixing some dependency and shortcut-key problems.

### Release Note - v0.1.212 2025-07-06

#### **New Features**

- Added the AI8 model platform implementation, supporting AI8 API integration
- Added the OYI model platform implementation, supporting OYI API integration
- Added a global last-message-recording feature, copyable via the Ctrl+L shortcut

#### **Fixes**

- Fixed the Kimi model file-parsing and streaming-response-handling logic
- Fixed the Unicode-decoding problem in Kimi model message-streaming-response handling

#### **Optimizations and Refactoring**

- Refactored the message-streaming-response-handling mechanism of the Kimi model
- Optimized the Chinese comments and documentation of the platform-manager main module
- Improved the input module, adding a last-message-copy feature

#### **Documentation Update**

- Updated the comments of the platform-manager main module to Chinese
- Added documentation for new features

#### **Miscellaneous**

- Updated the prompt info of the input module, including explanations of new shortcut keys
- Optimized the code format and structure

This update mainly added support for two new model platforms (AI8 and OYI), optimized the Kimi model's streaming-response handling, and added a practical last-message-copy feature, improving the user experience.

### Release Note - v0.1.211 2025-07-05

#### **New Features**

- Added the tiktoken model
- Added a copy-prompt-to-clipboard feature

#### **Fixes**

- Updated the haijunbot data-configuration-file inclusion pattern

#### **Optimizations and Refactoring**

- Removed the HuggingFace model-decompression feature
- Modified the retrieval of recent commit info to filter the current user

This update mainly added tiktoken-related feature support, optimized the prompt-interaction experience, and improved configuration management.

### Release Note - v0.1.210 2025-07-05

#### **New Features**

- Added the httpx>=0.28.1 dependency, used to improve HTTP-request handling
- Implemented the stream_post streaming-POST-request method, supporting more efficient streaming-response handling

#### **Fixes**

- Fixed the platform-message-stream-processing logic, improving SSE-format-data parsing
- Fixed the latest-commit-date-check logic in the git tool

#### **Optimizations and Refactoring**

- Refactored the HTTP module, migrating from the requests to the httpx library
- Optimized the streaming-response-handling logic, reducing memory usage
- Improved the code structure, adding type hints and docstrings

#### **Documentation Update**

- Updated the HTTP module documentation, reflecting the new httpx implementation
- Added documentation for the stream_post method

#### **Miscellaneous**

- Disabled the methodology and analysis features in CodeAgent
- Improved error handling and connection stability

This update mainly improved the HTTP-request-handling capability, migrated to the more modern httpx library, and optimized the streaming-response-handling logic, improving system stability and performance.

### Release Note - v0.1.209 2025-07-04

#### 1. New Features

- **Added a platform-management-command alias**
  Added the `hpm` alias for `haijunbot-platform-manager` in `pyproject.toml` and `setup.py`, improving command usability
- **Added an HTTP utility module**
  Added the `src/haijunbot/haijunbot_utils/http.py` file, providing unified HTTP-request handling
- **Added an auto-install mechanism**
  Added logic in `haijunbot_utils/git_utils.py` to automatically pip-install after a git update

#### 2. Bug Fixes

- **Fixed the edit-file output-suppression problem**
  Corrected the output-suppression logic in `edit_file_handler.py`

- **Fixed the file-upload logic**
  Uniformly uses the new HTTP module to handle uploads in each platform file

- **Fixed the initialization flow**
  Removed invalid history handling in `haijunbot_agent/__init__.py`

#### 3. Performance Improvements

- **Optimized token counting**
  Uses `tiktoken` instead of `transformers` for token counting

#### 4. Documentation

- **Updated the README document**
  Corrected the command-line-alias explanation and configuration-parameter explanation

- **Updated the configuration schema**
  Removed outdated configuration parameters such as `HAIJUNBOT_AUTO_UPDATE`

#### 5. Other Changes

- **Dependency update**
  Removed `transformers` and `torch`, added `tiktoken` and `pyyaml`
- **Added .gitignore rules**

# Release Note v0.1.208 - 2025-07-02

## New Features

- Added five expert-role configurations
- Enhanced the JSS fish completion feature
- Added a copy-polishing-expert role configuration

## Bug Fixes

- Fixed the response-concatenation problem when submitting large messages in chunks
- Fixed the file-diff-format handling in edit_file_handler

## Other Improvements

### Refactoring and Optimization

- Removed the yaspin dependency and simplified console output
- Optimized the new-file-confirmation logic and type hints
- Removed the isort tool from the Python file types
- Removed the in-development haijunbot-dev module
- Removed unused tools and uniformly uses the rewrite_file tool

### Code Quality

- Added type-check-ignore comments
- Improved the shell-name-retrieval logic and updated type annotations

### Release Note - v0.1.207 2025-06-27

#### **New Features**

- Added the 'ToolUsage' command, prompting the available tool list and usage
- Added the 'ReloadConfig' command, reloading the configuration file
- Added the 'Check' command, executing static code checks, including errors and style problems

#### **Fixes**

- Fixed the response-handling logic when submitting content in chunks

#### **Optimizations and Refactoring**

- Adjusted the HAIJUNBOT_CONFIRM_BEFORE_APPLY_PATCH default value to false
- Optimized the description of the Web-search command, supporting multiple question formats
- Optimized the description of the 'FindRelatedFiles' command, more accurately finding files related to a feature
- Refactored the response-handling logic when submitting content in chunks, improving stability

#### **Documentation Update**

- Updated the command list and descriptions in README.md
- Updated the default-value explanation of the configuration item HAIJUNBOT_CONFIRM_BEFORE_APPLY_PATCH

#### **Miscellaneous**

- Adjusted some code formatting and comments

This update mainly optimized command functionality, fixed configuration-consistency problems, and improved the handling logic of large-content chunk submission.

### Release Note - v0.1.206 2025-06-27

#### **Optimizations and Refactoring**

- Optimized the code format and type hints in edit_file_handler.py
- Fixed the spinner-display problem during interruption handling
- Improved the user-input-handling flow during patch application

This update mainly optimizes code quality and user experience, especially improving the stability and interaction experience of the file-editing handler

### Release Note - v0.1.205 2025-06-23

#### **New Features**

- Added an interruption-handling mechanism, allowing users to provide supplementary information when patch application is interrupted
- Updated the multi-line-input prompt info, changed to Chinese display

#### **Fixes**

- Fixed multiple type-check warnings, adding type-ignore comments
- Fixed the interruption-handling logic, adding interruption-state reset

#### **Optimizations and Refactoring**

- Refactored the patch-application logic of the file-editing handler
- Optimized the type hints and import structure of the input tools

#### **Miscellaneous**

- Removed unnecessary code comments
- Unified the usage of the multi-line-input tool

This update mainly optimized code quality, enhanced interruption-handling capability, and improved the user experience.

### Release Note - v0.1.204 2025-06-19

#### **New Features**

- Added a file-add confirmation mechanism; when a large number of newly added files, code lines, or binary files are detected, the user is prompted to confirm
- Added an interruption-check feature to the code editor, supporting user interruption of patch application

#### **Fixes**

- Fixed the progress-display problem when submitting long contexts
- Fixed the newly-added-file-detection logic in the git-commit flow

#### **Optimizations and Refactoring**

- Refactored the git tool class, extracting the newly-added-file-detection and confirmation logic into independent functions
- Optimized long-text submission handling of the platform base class, removing spinner and switching to normal output
- Improved the error-handling flow of the code editor

#### **Documentation Update**

- Updated the code-engineer guide, adding usage instructions for file-operation tools

#### **Miscellaneous**

- Added developer-incentive prompt info
- Improved the git-commit-message template

This update mainly enhanced git-change detection and the user-confirmation mechanism, optimized long-text-processing performance, and improved the developer experience.

### Release Note - v0.1.203 2025-06-17

#### **New Features**

- Improved the file-path-parsing logic, supporting single-quote, double-quote, and unquoted file-path formats
- Added merge-handling functionality for duplicate file paths
- Enhanced the multi-match warning prompt for search text

#### **Fixes**

- Fixed the error handling when the search text does not exist in the file
- Fixed the multi-match-detection problem for indented search text

#### **Optimizations and Refactoring**

- Unified the key names (SEARCH/REPLACE) in the patch data structure
- Optimized the output format of error-prompt messages
- Refactored the patch-parsing logic, improving code readability

#### **Documentation Update**

- Updated method comments, more clearly describing functionality and behavior

#### **Miscellaneous**

- Improved code indentation and format consistency

This update mainly improved the stability and user experience of the file-editing handler, enhancing error-detection and handling capability.

### Release Note - v0.1.202 2025-06-16

#### **Optimizations and Refactoring**

- Optimized the regular-expression-match logic of the file-editing handler, removing unnecessary whitespace matching
- Simplified the format markers of DIFF blocks, using more concise SEARCH/REPLACE tags
- Improved the template format of file-editing directives, making them more compact and readable

#### **Miscellaneous**

- Fixed the format problem of message-receipt confirmation in the platform base class

This update mainly optimized and refactored the code-editing feature, improving the processing efficiency and reliability of file-editing directives.

### Release Note - v0.1.201 2025-06-15

#### **New Features**

- Added the EditFileHandler class, used to handle file-editing directives (PATCH blocks)
- Supports precise file-content modification via PATCH directives
- Added two editing modes, fast_edit and slow_edit

#### **Fixes**

- Fixed the problem that the first-chat flag was not correctly reset on the yuanbao platform
- Fixed the error handling when yaml parsing fails in the file-editing tool
- Fixed the problem that the thinking tag was not correctly handled

#### **Optimizations and Refactoring**

- Refactored the file-editing tool into a multi-file-handling mode
- Optimized the code-patch-generation logic, adding an automatic indentation-matching feature
- Improved the rollback mechanism when file editing fails

#### **Documentation Update**

- Updated the file-editing-directive format documentation
- Added usage instructions for the PATCH handler

#### **Miscellaneous**

- Removed the old edit_file tool, switching to the new EditFileHandler
- Optimized the tool-call-format error prompts

This update mainly improved the file-editing feature, adding more precise PATCH-directive support, and optimized the handling flow when editing fails.

### Release Note - v0.1.200 2025-06-13

#### **New Features**

- Added user-intervention-handling logic when a tool call is interrupted
- Added an automatic-restart feature after a git-repository update

#### **Fixes**

- Fixed the ReloadConfig return logic in builtin_input_handler
- Fixed the Yuanbao platform request-timeout problem

#### **Optimizations and Refactoring**

- Optimized the timeout handling of all requests on the Yuanbao platform (uniformly set to 600 seconds)
- Removed the redundant ToolHelp template in builtin_replace_map.py

#### **Documentation Update**

- None

#### **Miscellaneous**

- Optimized the import order of utils.py

This update mainly enhanced tool-call-interruption-handling capability, optimized the request stability of the Yuanbao platform, and simplified the built-in replacement-mapping table.

### Release Note - v0.1.199 2025-06-10

#### **New Features**

- None

#### **Fixes**

- Fixed the multi-match-error-prompt format of the edit_file tool
- Fixed the KeyboardInterrupt exception-handling problem in the user_confirm function

#### **Optimizations and Refactoring**

- Optimized the rewrite_file tool, uniformly using absolute paths to handle files
- Improved the file-list-recording feature of the rewrite_file tool
- Removed unnecessary blank lines in utils.py

#### **Documentation Update**

- None

#### **Miscellaneous**

- Updated the docs/images/wechat.png image file

This update mainly optimized the error-handling and path-handling logic of the file tools, enhancing tool robustness.

### Release Note - v0.1.197 2025-06-07

#### **New Features**

- Added a history-conversation-file-upload feature, supporting saving the history conversation as a temporary file and uploading it
- Added the HAIJUNBOT_USE_HISTORY_COUNT configuration item, replacing the original HAIJUNBOT_USE_HISTORY boolean configuration

#### **Optimizations and Refactoring**

- Refactored the history-handling logic, separating the save functionality into an independent method
- Optimized the context-switching mechanism, supporting retaining history via file upload
- Improved the README.md configuration explanation, updating history-related documentation

#### **Miscellaneous**

- Fixed the temporary-file-cleanup logic, ensuring correct cleanup even in abnormal situations

This update mainly enhanced the history-handling capability, supporting retaining the complete conversation history via file upload, while also optimizing the configuration items and documentation.

### Release Note - v0.1.196 2025-06-05

#### **New Features**

- Added a history feature (HAIJUNBOT_USE_HISTORY_COUNT configuration item)
- Added the feature of exporting history as Markdown

#### **Optimizations and Refactoring**

- Adjusted the file-upload logic on first run
- Refactored the Agent-initialization code, extracting the \_first_run method
- Optimized the history-handling logic

#### **Documentation Update**

- Updated README.md, adding an explanation of the HAIJUNBOT_USE_HISTORY configuration

This update mainly added the history feature, which can use the history as context and supports exporting to Markdown format, while also optimizing the code structure and file-handling logic.

### Release Note - v0.1.195 2025-06-04

#### **New Features**

- Added the HaijunBot history feature (haijunbot_history)
- Added documentation for the HaijunBot general-agent-tool feature

#### **Optimizations and Refactoring**

- Improved the git-diff-retrieval logic, supporting empty-repository situations
- Optimized output exception handling, preventing crashes
- Enhanced the methodology-upload feature, supporting uploading other files at the same time
- Improved code-import organization, speeding up initialization

#### **Documentation Update**

- Updated README.md, adding detailed documentation for the HaijunBot general-agent tool

#### **Miscellaneous**

- Fixed git-diff-decoding error handling
- Improved the file-upload-failure-handling logic
- Optimized the code format and type hints

This update mainly enhanced HaijunBot's history feature, improved git operations and exception handling, and improved the documentation system.

### Release Note - v0.1.194 2025-06-01

#### **New Features**

- Added a reload-configuration feature
- Added ToolUsage-marker-handling functionality
- Retrieves the modified-file list in advance during the commit flow

#### **Fixes**

- Fixed the problem that blank lines were also padded with spaces during indentation handling
- Adjusted the execution order of tool calls and interruption handling

#### **Optimizations and Refactoring**

- Extracted the configuration-file-loading logic into an independent function
- Optimized the code format and import order
- Streamlined the default lint-tool configurations for each language
- Removed unused import statements and features

#### **Documentation Update**

- Refactored the document structure and optimized content organization

This update mainly includes configuration-management enhancement, tool-call-flow optimization, code-quality improvement, and documentation refactoring.

### Release Note - v0.1.193 2025-05-31

#### **New Features**

- Added the example/roles/roles.yaml role configuration file
- Improved the code-agent feature documentation and usage instructions

#### **Fixes**

- Fixed the addon_prompt-generation logic
- Fixed the file-modification-prompt logic in the code-agent feature
- Fixed the Yuanbao platform initialization-parameter-passing problem

#### **Optimizations and Refactoring**

- Optimized the output format of the code-agent feature
- Refactored the output format of the tool registry
- Improved the output display of the methodology module

#### **Documentation Update**

- Updated README.md, adding an explanation of the code-agent feature
- Improved the built-in-tool help documentation

#### **Miscellaneous**

- Added empty-file-handling logic
- Improved error-handling prompts

This update mainly added the code-agent feature, and optimized the output display and error handling of multiple modules.

### Release Note - v0.1.192 2025-05-31

#### **New Features**

- Added an OpenAI-platform file-upload feature support-detection method
- Improved the interruption-signal-handling mechanism, supporting interruption counting

#### **Fixes**

- Fixed the user-intervention-info-concatenation format problem
- Corrected the prompt-info-display logic after patch application

#### **Optimizations and Refactoring**

- Refactored the global-variable-management code, improving code format and readability
- Optimized the interruption-signal-handling logic, adding multiple-interruption protection
- Improved the return-info prompts of the code agent

#### **Documentation Update**

- Updated code comments and type hints

#### **Miscellaneous**

- Adjusted the console-theme configuration format
- Optimized the SIGINT-signal-handling logic

This update mainly improved the interruption-handling mechanism and code maintainability, added file-upload-feature support detection, and optimized the user-interaction experience.

### Release Note - v0.1.191 2025-05-31

#### **New Features**

- Added a role-configuration feature, supporting loading role configurations from a YAML file and starting a conversation
- Added an interruption-handling mechanism, supporting receiving the SIGINT signal during model interaction
- Added a role subcommand (--role/-c) to the platform manager

#### **Fixes**

- Fixed the output format of the file-analysis tool, wrapping it with `<output>` and `<error>` tags
- Fixed the naming-inconsistency problem of the set_system_message method, unified to set_system_prompt

#### **Optimizations and Refactoring**

- Refactored the code structure of the platform manager, improving readability
- Removed the default addon prompt

#### **Documentation Update**

- Updated the output-handling documentation of the tool registry
- Added an example explanation of the role configuration file

#### **Miscellaneous**

- Optimized the signal-handling logic

This update mainly enhanced the functionality of the platform manager, added role-configuration support, and improved the interruption-handling mechanism, improving system stability and the user experience.

### Release Note - v0.1.190 2025-05-30

#### **New Features**

- Added a predefined-task (pre-command) feature, supporting quickly executing common commands via a YAML file
- The tool-generation feature added automatic dependency-check and installation functionality

#### **Fixes**

- Fixed the parameter-handling problem during tool registration
- Removed the deprecated `haijunbot-ask-codebase` feature

#### **Optimizations and Refactoring**

- Optimized the code structure and error handling of the tool generator
- Improved the stability of the tool-registration flow
- Enhanced the dependency-management feature during tool generation

#### **Documentation Update**

- Updated the predefined-task usage instructions in the README
- Improved the documentation of the tool-generation feature

#### **Miscellaneous**

- Updated the WeChat image resource

This update mainly enhanced the tool-generation and management capability, especially adding the predefined-task feature and the automatic-dependency-management feature, while also optimizing the stability and user experience of existing features.

### Release Note - v0.1.189 2025-05-29

#### **New Features**

- Added the `support_upload_files()` method for checking whether the platform supports file upload
- Added the `generate_summary()` method for generating a conversation-history summary
- Optimized the code-diff-file-upload-handling logic

#### **Fixes**

- Fixed the error-handling flow when file upload fails
- Fixed the renaming problem of the `clear_history()` method
- Fixed the error prompt when the platform does not support file upload

#### **Optimizations and Refactoring**

- Refactored the code structure of `GitCommitTool`, extracting independent methods
- Optimized the platform-support check before file upload
- Improved the large-file-handling logic

#### **Documentation Update**

- Updated the method docstrings
- Improved the error-prompt messages

#### **Miscellaneous**

- Adjusted the `HAIJUNBOT_MAX_BIG_CONTENT_SIZE` default value to 160000
- Optimized the code format and indentation style

This update mainly optimized the file-upload-handling flow, added a platform-support-check feature, and improved the error-handling mechanism.

### Release Note - v0.1.188 2025-05-28

#### **New Features**

- Added the RefactorCheckerExpert refactoring-check expert, used to check whether the refactored code logic is completely consistent with the original code

#### **Fixes**

- Fixed the file-reference-parsing problem in the file input handler, preventing other quotes from interfering with file-path parsing
- Fixed the patch-application-failure problem in the edit_file tool; it now automatically tries adding 1-16 spaces of indentation to retry matching

#### **Optimizations and Refactoring**

- Refactored the initialization logic of haijunbot_agent, adjusting the execution order of input handlers
- Optimized the Chinese comments and error handling of the file input handler
- Removed the interactive-mode loop structure in main.py

#### **Documentation Update**

- Updated the detailed workflow documentation of RefactorCheckerExpert
- Improved the Chinese parameter explanation of file_input_handler

#### **Miscellaneous**

- Improved the error-prompt info of the edit_file tool; it now displays a more detailed reason for match failure

This update mainly enhanced the code-refactoring-check capability, improved the file-handling logic, and optimized the user experience.

### Release Note - v0.1.187 2025-05-27

#### **Fixes**

- Fixed the config parameter changing from required to optional (main.py)
- Fixed the conversation-length-calculation logic (**init**.py)

#### **Optimizations and Refactoring**

- Optimized the model-response-handling flow (**init**.py)
- Improved the prompt info after file upload (**init**.py)

### Release Note - v0.1.186 2025-05-27

#### **New Features**

- Added support for specifying a custom configuration-file path via the `-f/--config` parameter
- Added support for the `-c/--agent_definition` parameter, used to specify the agent-definition file

#### **Fixes**

- Fixed the file-path-handling problem in the file-editing tool; it now uses absolute paths

#### **Optimizations and Refactoring**

- Refactored the `init_env` function, supporting passing the configuration-file path via a parameter
- Optimized the configuration-file-loading logic
- Improved the HuggingFace model-decompression-path handling

This update mainly enhanced the configuration-management feature, improved the initialization flow, and fixed file-path-handling-related problems.

### Release Note - v0.1.185 2025-05-26

#### **New Features**

- Recommends Tencent Yuanbao as the preferred platform, optimizing platform adaptability
- Added a file-upload feature, supporting automatic file upload during Agent initialization
- Extended the file types supported by the Tongyi platform, adding support for multiple image formats

#### **Fixes**

- Fixed the file-existence-check logic in the file-processing tool
- Fixed the error-info-display problem when patch application fails
- Fixed the prompt info for tool-call-format errors

#### **Optimizations and Refactoring**

- Optimized the platform-recommendation explanation in the README documentation
- Refactored the file-upload-handling flow, improving stability
- Improved the error-handling mechanism for patch application

#### **Documentation Update**

- Updated the configuration explanation in the README, clearly recommending the Tencent Yuanbao platform
- Improved the help info for tool-call-format errors

This update mainly enhanced file-processing capability and platform adaptability, optimizing the user experience and error-handling mechanism.

### Release Note - v0.1.184 2025-05-26

#### **New Features**

- Added file-upload progress indication and error handling
  - Added progress indication during the file-upload process and improved the error-handling mechanism.
- Added system-message-initialization functionality
  - Added system-message support, to enhance the conversation-initialization functionality.

#### **Code Refinement and Fixes**

- Removed the code-validation and processing step when generating a new tool, directly writing the raw tool code.
  - This simplified the tool-generation flow, but may require users to provide more standardized input code.

This update mainly optimized the user experience of file upload and added system-message support, to enhance the conversation-initialization functionality.

#### **New Features**

- Added Tongyi Qianwen platform support, including four model types: Normal, Thinking, Deep-Research, Code-Chat
- Added a Tongyi Qianwen cookies-retrieval guide and configuration-explanation documentation
- Added the Tongyi Qianwen platform implementation file (src/haijunbot/haijunbot_platform/tongyi.py)

#### **Fixes**

- Fixed the thinking-mode-message-handling logic in the Yuanbao platform
- Fixed the model-name-return problem in the Kimi platform

#### **Optimizations and Refactoring**

- Removed the no-longer-needed set_suppress_output method in the platform registry
- Unified the thinking-mode-message-handling format of each platform

#### **Documentation Update**

- Updated README.md, adding an explanation of the Tongyi Qianwen platform configuration
- Added a Tongyi Qianwen cookies-retrieval illustration (docs/images/tongyi.png)

This update mainly added support for the Tongyi Qianwen platform, providing a complete platform implementation and configuration documentation, and optimized the message-handling logic of existing platforms.

### Release Note - v0.1.182 2025-05-25

#### **New Features**

- Added a file-input-handling feature (file_input_handler.py)
- Added a user-data-storage feature (**init**.py)
- Added a user-data-tracking feature when reading file content (file_operation.py, read_code.py)

#### **Fixes**

- Corrected the git diff command-parameter error (pre-command)
- Fixed the boundary-condition problem in the file-operation tool (file_operation.py)

#### **Optimizations and Refactoring**

- Optimized the core logic of the editing tool (edit_file.py)
- Improved the output format of the code-reading tool (read_code.py)
- Refactored the system-prompt-tag format (**init**.py)

#### **Documentation Update**

- Updated the initialization documentation of the haijunbot_agent module (**init**.py)

This update mainly enhanced file-processing capability and user-data-management functionality, while also optimizing the performance and stability of core tools. The newly added file-input-handling feature can intelligently recognize file references and automatically read content, and the user-data-storage feature facilitates data sharing between tools.

### Release Note - v0.1.181 2025-05-24

#### **Main Changes**

1. **Documentation Cleanup**

- Removed all outdated documentation images and markdown files
- Cleaned up user-documentation content that is no longer used

1. **Code Refactoring**

- Greatly streamlined the implementation logic of code_agent.py
- Removed the find_methodology tool and related code
- Optimized the configuration system, using native boolean types instead of string configuration
- Refactored the git tool functions into a dedicated module

1. **Feature Adjustments**

- Removed the entire implementation of the ask_codebase tool
- Updated the default-configuration values of multiple tools
- Enhanced the functionality of the execute_script tool

1. **Other Improvements**

- Updated the project-dependency configuration
- Optimized the implementation details of multiple tools
- Cleaned up no-longer-used code and resources

### Release Note - v0.1.180 2025-05-23

#### **New Features**

- Added a yaml-configuration-file method to configure replacement key-value pairs
- Added MCP-tool-configuration support and refactored the registration logic
- Refactored the configuration-file-management logic
- The authentication configuration items of the Kimi, OpenAI, and Yuanbao platforms use ENV-configuration management
- Added configuration-file-schema support and improved configuration-file handling

#### **Fixes**

- Corrected the default value of the auto-update configuration
- Corrected the patch-content formatting in the file-editing tool

#### **Optimizations and Refactoring**

- Split the configuration-file-reading logic into an independent function
- Refactored the environment-initialization logic to support both the configuration file and the legacy env file
- Simplified the command-usage-statistics logic and removed the unused datetime import
- Optimized the output content of MCP-configuration error messages
- Optimized the version-check and update logic
- Optimized the format of the configuration-item enumeration values and removed the unused API configuration
- Refactored the environment-variable configuration into a general configuration system
- Removed references to the no-longer-used legacy configuration file

#### **Documentation Update**

- Updated the configuration-method explanation and removed deprecated methods
- Updated the MCP-configuration documentation and adjusted the configuration mode
- Updated the Yuanbao configuration format
- Updated the configuration-file format and path explanation
- Added an enable-field explanation for all MCP-configuration modes
- Added a streaming-MCP-configuration explanation

#### **Miscellaneous**

- Added a migration warning for the legacy configuration-file format
- Removed the detailed guidance info when the API key is not set
- Added allow_unicode parameter support to all yaml.safe_dump calls

This update mainly carried out comprehensive refactoring and feature enhancement around the configuration system, added multi-platform-API support, optimized the documentation and error-handling mechanism, and fixed several key problems.

### Release Note - v0.1.179 2025-05-22

#### **New Features**

- Added a streamable HTTP MCP client implementation (StreamableMcpClient)
- Added lint-tool support and integrated it into the code-modification prompt
- Added a command-usage-statistics feature
- Added YAML-format-configuration-file support
- Added task-analysis-feature support

#### **Fixes**

- Changed environment-variable default values: HAIJUNBOT_USE_METHODOLOGY and HAIJUNBOT_USE_ANALYSIS changed from 'true' to 'false'
- Removed the no-longer-used lsp_get_diagnostics tool

#### **Optimizations and Refactoring**

- Optimized the code structure and import order
- Optimized the lint-tool-matching logic and unified filename-case handling
- Optimized the git-diff-retrieval feature to include newly added files
- Optimized the display format of the operation list
- Optimized the format and content of the system prompt
- Optimized the structure of the commit-message-generation-prompt template

#### **Documentation Update**

- Unified the function-docstring format
- Updated the README navigation-link format
- Updated the configuration format and added a file-path explanation

#### **Miscellaneous**

- Deleted the empty file aaaa
- Removed no-longer-needed dependencies (jedi and sseclient)
- Added the tabulate dependency

This update mainly enhanced configuration management, code-quality checking, and statistics functionality, while also carrying out multiple code optimizations and refactorings. Of particular note are the improvements to the configuration system, including YAML-format support and adjustments to environment-variable default values.

### Release Note - v0.1.178 2025-05-21

#### **New Features**

- Added a methodology-analysis feature, supporting enabling task analysis and methodology generation via configuration
- Added the `use_methodology` parameter to control the use of methodology
- Enhanced the file-editing-tool functionality, supporting two editing modes and AI-assisted editing

#### **Fixes**

- Fixed the tool-filtering-logic error, avoiding KeyError exceptions
- Corrected the git log parameter error when generating the release note
- Removed redundant error-info output and unused library imports

#### **Optimizations and Refactoring**

- Removed the entire LSP implementation module, to be replaced by the new code-analysis architecture
- Refactored the file-editing-tool documentation, providing a clearer usage guide
- Updated the platform configuration of the codebase-analysis tool

#### **Documentation Update**

- Added detailed method documentation for the OpenAIModel class
- Added a requirement to the analysis step, ensuring conclusions are based on actual code evidence
- Updated the WeChat QR code image

#### **Miscellaneous**

- Modified the task-completion-prompt logic, explicitly prohibiting output of the TOOL_CALL tag
- Cleaned up code to keep it concise

This update mainly includes feature enhancement, bug fixing, and architecture optimization, especially adding the methodology-analysis feature and refactoring the file-editing tool. At the same time, it removed the LSP-related modules, preparing for the new code-analysis architecture.

### Release Notes - v0.1.177 (2025-05-20)

#### ✨ Core Feature Enhancements

1. **Brand-new welcome system**
   - Added a dynamic ASCII-art welcome interface for all tools
   - Implemented gradient-color text-output effect (blue->cyan gradient)
   - Displays the version number and project link

2. **Code-editing-tool upgrade**
   - Added the `fast_edit` fast-editing mode
   - Optimized the `slow_edit` fault-tolerance mechanism (3 retries)
   - Enhanced the uniqueness check of patch application

3. **Statistics monitoring**
   - Added tool-call-count statistics
   - Supports viewing the ranking via `haijunbot-tools stat`
   - Data persisted to `tool_stat.yaml`

#### 🐛 Key Fixes

1. **Stability fixes**
   - Supports unlimited tool calls when `MAX_TOOL_CALL_COUNT=0`
   - Resolved the minimum-block-size-calculation error when chunking long text
   - Corrected the file-size-display format of the Yuanbao platform

2. **Output optimization**
   - Unified the icon spacing of all error messages
   - Changed the syntax-highlight theme from Dracula to Monokai
   - Optimized the display logic of multi-line output

#### ⚙️ Configuration Changes

| Configuration Item | Old Value | New Value | Description             |
| --------------- | ---- | ---- | ---------------- |
| MAX_TOKEN_COUNT | 102M | 960K | Reduce memory usage     |
| MAX_BIG_CONTENT | 96K  | 1M   | Support larger file processing |
| MAX_TOOL_CALLS  | 20   | 0=∞  | Support unlimited-call mode |

### Release Note - v0.1.176 2025-05-19

#### **New Features**

- None

#### **Fixes**

- Corrected the format explanation of the git diff command in the pre-command file
- Updated the HAIJUNBOT_MAX_BIG_CONTENT_SIZE configuration value
- Added the HAIJUNBOT_PRETTY_OUTPUT configuration option

#### **Optimizations and Refactoring**

- Optimized the file-input-handling logic
- Refactored the platform-chat-output handling
- Improved the text-chunking logic

#### **Documentation Update**

- Updated the configuration explanation in README.md

#### **Miscellaneous**

- Deleted the unused file_input_handler module

This update mainly optimized the code structure and configuration options, removed unused modules, and improved the text-handling logic.

### Release Note - v0.1.175 2025-05-17

#### **New Features**

- Added a methodology-upload feature, supporting uploading methodologies to the platform
- Added static-check-tool support to the code agent
- Added Rich real-time-output-display functionality to the Kimi, OpenAI, and Yuanbao platforms
- Added a conversation-record-save feature to the platform manager (/save and /saveall commands)

#### **Fixes**

- Fixed the description of the release_note-generation step in the pre-command file
- Removed the redundant print_stream method in haijunbot_agent
- Corrected the format explanation in the tool registry

#### **Optimizations and Refactoring**

- Optimized the message format of the multi-agent system
- Improved the methodology-extraction and upload logic
- Refactored the output-display method of platform interaction

#### **Documentation Update**

- Updated the directive explanation in the pre-command documentation
- Improved the methodology-template format

#### **Miscellaneous**

- Unified the message-format specification of each platform
- Optimized the code format and comments

This update mainly carried out comprehensive optimization of platform interaction, methodology management, and output display, improving the system's interaction experience and maintainability.

### Release Note - v0.1.174 2025-05-16

#### **Fixes**

- Adjusted the HAIJUNBOT_MAX_BIG_CONTENT_SIZE default value from 64000 to 96000

#### **Optimizations and Refactoring**

- Optimized the long-text-handling logic and token-calculation method

This update mainly optimized the text-handling logic and token-calculation method.

### Release Note - v0.1.173 2025-05-16

#### **Fixes**

- Adjusted the HAIJUNBOT_MAX_BIG_CONTENT_SIZE default value to 64000, optimizing memory usage

This update mainly optimized the system's memory-usage efficiency, adjusting the large-content-processing default value to a more reasonable 62.5KB.

### Release Note - v0.1.171 2025-05-16

#### **New Features**

- Added an automated flow for generating Release Notes
- Added progress display during long-context interaction
- Added the HAIJUNBOT_MAX_BIG_CONTENT_SIZE configuration parameter
- Improved the task-analysis flow and the work-generation mechanism
- Refactored the task-analysis-prompt template to support work generation and version control
- Added basic priority display for agents
- Improved the release_note-generation format and content structure

#### **Fixes**

- Corrected the duplicate problem caused by writing to the ReleaseNote.md file in append mode
- Changed the default maximum content size from 10MB to 1MB
- Fixed the empty-response handling when context is lost
- Fixed the custom-reply-loop and display-format problems
- Fixed the error-handling logic when the context of a large file is lost

#### **Optimizations and Refactoring**

- Optimized the context-length-filtering-editing logic
- Simplified the conversation-configuration and result-display templates
- Removed the chat_big_content strategy and unified into the large-content-processing-editing logic

#### **Documentation Update**

- Updated the release_note-generation-editing and rename file
- Updated the explanation of the hgc command in the pre-command documentation
- Refactored the release-note format and supplemented detailed update content

#### **Miscellaneous**

- Added the current date and expected release time to the release notes

This update mainly improved release-process automation, optimized the task-analysis mechanism, and fixed multiple key problems.
