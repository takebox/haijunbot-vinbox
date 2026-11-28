// gh plugin frontend sidebar view.
// Convention: pure browser ES module, using window.Vue for rendering, exporting default component, no import 'vue'.
// Features: Browse/operate Issues and Pull Requests of the current repository.
// Auth: Read operations work anonymously; write operations (comment/close/merge) require GitHub token.
//       Token reuses GitHub official gh CLI login state (gh auth login), read by the backend gh plugin
//       private functions, frontend calls via plugin function proxy endpoints, does not directly access
//       api.github.com, and does not store GitHub token in the browser.

const PLUGIN = "gh";
// Current resolved repository (owner/repo), dynamically determined by resolveRepo based on workingDir.
// Initially empty: no hardcoded default repo, to avoid other users seeing a fixed repo after plugin release.
let currentRepo = "";
// Manually switched repository (owner/repo). Empty means follow workingDir auto-resolution;
// non-empty means user explicitly specified another repo, which will not be overridden by resolveRepo.
let manualRepo = "";
// Remember manually specified repo, persists after page refresh (key fixed per plugin).
const MANUAL_REPO_KEY = "haijunbot_gh_manual_repo";

// Replicate App.vue's gateway address parsing (sidebar component has no props injection, must parse itself)
function parseGatewayAddress(address) {
  address = (address || "").trim();
  if (!address) return null;
  if (address.includes("://")) {
    try {
      const url = new URL(address);
      return {
        protocol: url.protocol.replace(":", ""),
        host: url.hostname,
        port:
          url.port ||
          (url.protocol === "https:" || url.protocol === "wss:" ? "443" : "80"),
        path: url.pathname,
      };
    } catch (e) {
      return null;
    }
  }
  if (address.includes(":")) {
    const parts = address.split(":");
    if (parts.length === 2) {
      return { protocol: null, host: parts[0], port: parts[1], path: "" };
    }
  }
  return { protocol: null, host: address, port: "8000", path: "" };
}

// Get current page's HTTP protocol (consistent with App.vue getHttpProtocol)
function getHttpProtocol() {
  return window.location.protocol === "https:" ? "https" : "http";
}

function gatewayBase() {
  const parsed = parseGatewayAddress(
    localStorage.getItem("haijunbot_gateway_url") || "",
  );
  const host = (parsed && parsed.host) || "127.0.0.1";
  const port = (parsed && parsed.port) || "8000";
  // Protocol: use explicit https if specified; otherwise use current page protocol (consistent with App.vue),
  // Avoid mixed content blocking when HTTPS page requests http addresses.
  const protocol =
    parsed && parsed.protocol === "https" ? "https" : getHttpProtocol();
  return `${protocol}://${host}:${port}`;
}

// Call plugin private functions via gateway plugin function proxy endpoint
async function callFunction(functionName, args) {
  // Use App.vue's authenticated request function window.__haijunbotFetch (automatically includes
  // haijunbot auth info, token not exposed to plugin); fall back to regular fetch if host hasn't injected it.
  const authedFetch =
    (typeof window !== "undefined" && window.__haijunbotFetch) || fetch;
  // Except resolve_repo, all other functions require a repo; if no repo resolved,
  // pass empty and let backend return explicit error.
  const noRepoFns = ["resolve_repo"];
  const callArgs = args || {};
  if (!noRepoFns.includes(functionName) && !callArgs.repo) {
    callArgs.repo = currentRepo;
  }
  const resp = await authedFetch(
    `${gatewayBase()}/api/plugins/master/function-call`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plugin: PLUGIN,
        function: functionName,
        arguments: callArgs,
      }),
    },
  );
  let result;
  try {
    result = await resp.json();
  } catch (e) {
    throw new Error("Gateway response anomaly");
  }
  if (!result.success) {
    const err = result.error || {};
    throw new Error(err.message || err.code || "Call failed");
  }
  const payload = result.result || {};
  if (payload.success === false) {
    throw new Error(payload.error || "Operation failed");
  }
  return payload;
}

export default {
  name: "GhSidebarView",
  props: {
    workingDir: { type: String, default: "" },
  },
  data() {
    return {
      repo: currentRepo,
      repoInput: "",
      repoEditing: false,
      // Whether in "manually specified custom repo" mode: true means the currently displayed
      // repo is not the repo corresponding to the current Agent's working directory; in this
      // case issues/PRs should not be handed to the current Agent (Agent's working directory
      // belongs to another repo, gh commands would execute on the wrong repo).
      isManualRepo: false,
      // Current target Agent name (provided by host __haijunbotGetActiveAgentInfo; empty if none).
      // Used for header and context menu labeling the actual recipient of "handle in current Agent".
      agentName: "",
      tab: "issues",
      loading: false,
      loadingMore: false,
      error: "",
      items: [],
      // Pagination state: page is current loaded page, hasMore indicates if more pages exist,
      // total is backend-inferred total count (for "loaded N of M" display).
      page: 1,
      hasMore: false,
      total: 0,
      selected: null,
      comments: [],
      // Operations
      commentText: "",
      busy: false,
      message: "",
      // List item context menu
      menuVisible: false,
      menuStyle: {},
      menuItem: null,
    };
  },
  mounted() {
    this.restoreManualRepo();
    this.refreshAgentName();
    this.resolveRepo().then(() => this.refresh());
    // Subscribe to host agent_changed event: switching Agent updates the
    // "Current Agent" header even when workingDir hasn't changed (same directory
    // switch) (watch workingDir only triggers on value change).
    const on = typeof window !== "undefined" && window.__haijunbotOn;
    if (typeof on === "function") {
      this._offAgentChanged = on("agent_changed", () => {
        this.refreshAgentName();
      });
    }
    // Click outside / press Esc to close context menu
    this._onDocClick = () => this.closeItemMenu();
    this._onDocKeydown = (e) => {
      if (e.key === "Escape") this.closeItemMenu();
    };
    document.addEventListener("click", this._onDocClick);
    document.addEventListener("keydown", this._onDocKeydown);
  },
  beforeUnmount() {
    if (typeof this._offAgentChanged === "function") this._offAgentChanged();
    document.removeEventListener("click", this._onDocClick);
    document.removeEventListener("keydown", this._onDocKeydown);
  },
  watch: {
    workingDir() {
      // When agent switches repo, re-resolve and refresh; target Agent may change too, sync name refresh
      this.refreshAgentName();
      this.resolveRepo().then(() => this.refresh());
    },
  },
  methods: {
    // Get current target Agent name from host (matches the actual recipient of "handle in current Agent").
    // Silently set to empty if host doesn't provide the interface (doesn't block other plugin features).
    refreshAgentName() {
      const getInfo =
        typeof window !== "undefined" && window.__haijunbotGetActiveAgentInfo;
      if (typeof getInfo !== "function") {
        this.agentName = "";
        return;
      }
      try {
        const info = getInfo() || {};
        this.agentName = (info && info.agentName) || "";
      } catch {
        this.agentName = "";
      }
    },
    async resolveRepo() {
      // Manually specified repo takes priority: no longer overridden by workingDir auto-resolution.
      if (manualRepo) {
        currentRepo = manualRepo;
        this.repo = currentRepo;
        this.repoInput = currentRepo;
        this.isManualRepo = true;
        return;
      }
      try {
        const payload = await callFunction("resolve_repo", {
          working_dir: this.workingDir || "",
        });
        currentRepo = (payload && payload.repo) || "";
        this.repo = currentRepo;
        this.repoInput = currentRepo;
      } catch {
        // Resolution failed: clear repo (no hardcoded default repo)
        currentRepo = "";
        this.repo = "";
        this.repoInput = "";
      }
      this.isManualRepo = false;
    },
    // Restore last manually specified repo from localStorage (persists after page refresh).
    restoreManualRepo() {
      try {
        const saved = (localStorage.getItem(MANUAL_REPO_KEY) || "").trim();
        if (saved) manualRepo = saved;
      } catch {
        /* Ignore if localStorage unavailable */
      }
    },
    // Normalize user-entered repo: trim, remove .git suffix, validate owner/repo format.
    // Returns normalized owner/repo; returns empty string if invalid.
    normalizeRepoInput(raw) {
      let value = String(raw || "").trim();
      if (value.endsWith(".git")) value = value.slice(0, -4);
      // Allow pasting full URL / ssh address, extract owner/repo
      if (value.includes("://")) {
        // https://github.com/owner/repo or ssh://git@github.com/owner/repo
        value = value.replace(/^[a-z]+:\/\//i, "");
        value = value.replace(/^[^@/]*@/, "");
        value = value.replace(/^[^/]+\//, "");
      } else if (value.includes("@")) {
        // scp style git@github.com:owner/repo
        value = value.replace(/^[^@/]*@/, "");
        value = value.replace(/^[^:/]+\//, "");
        const colon = value.indexOf(":");
        if (colon !== -1) value = value.slice(colon + 1);
      }
      value = value.replace(/^\/+|\/+$/g, "");
      const parts = value.split("/").filter((p) => p);
      if (parts.length !== 2) return "";
      if (!/^[\w.-]+$/.test(parts[0]) || !/^[\w.-]+$/.test(parts[1])) return "";
      return `${parts[0]}/${parts[1]}`;
    },
    // Switch to user-entered repo.
    setRepo() {
      const normalized = this.normalizeRepoInput(this.repoInput);
      if (!normalized) {
        this.error = "Invalid repo format, please enter owner/repo (e.g., octocat/Hello-World)";
        return;
      }
      this.error = "";
      manualRepo = normalized;
      try {
        localStorage.setItem(MANUAL_REPO_KEY, normalized);
      } catch {
        /* Ignore storage failure */
      }
      currentRepo = normalized;
      this.repo = normalized;
      this.repoInput = normalized;
      this.isManualRepo = true;
      this.repoEditing = false;
      this.refresh();
    },
    // Restore to "follow current working directory" auto-resolved repo.
    useCurrentDirRepo() {
      manualRepo = "";
      try {
        localStorage.removeItem(MANUAL_REPO_KEY);
      } catch {
        /* Ignore */
      }
      this.repoEditing = false;
      this.resolveRepo().then(() => this.refresh());
    },
    toggleRepoEdit() {
      this.repoEditing = !this.repoEditing;
      if (this.repoEditing) {
        this.repoInput = this.repo || "";
        this.error = "";
      }
    },
    fmtDate(s) {
      if (!s) return "";
      try {
        return new Date(s).toLocaleString();
      } catch (e) {
        return s;
      }
    },
    // Normalize raw backend entries into list items.
    mapItem(it) {
      return {
        number: it.number,
        title: it.title,
        state: it.state,
        user: it.user,
        created_at: it.created_at,
        updated_at: it.updated_at,
        body: it.body || "",
        html_url: it.html_url,
        comments: it.comments,
      };
    },
    async refresh() {
      this.loading = true;
      this.error = "";
      this.message = "";
      // Clear list immediately on switch/refresh to avoid stale data from previous repo on request failure
      this.items = [];
      this.page = 1;
      this.hasMore = false;
      this.total = 0;
      this.selected = null;
      this.comments = [];
      try {
        const fn = this.tab === "issues" ? "list_issues" : "list_prs";
        const payload = await callFunction(fn, { state: "open", page: 1 });
        this.items = (payload.data || []).map((it) => this.mapItem(it));
        this.page = payload.page || 1;
        this.hasMore = !!payload.has_more;
        this.total = payload.total || this.items.length;
        this.selected = null;
        this.comments = [];
      } catch (e) {
        this.error = String((e && e.message) || e);
      } finally {
        this.loading = false;
      }
    },
    // Load next page and append to list (paginated display to avoid fetching too much at once).
    async loadMore() {
      if (this.loadingMore || !this.hasMore) return;
      this.loadingMore = true;
      this.error = "";
      try {
        const fn = this.tab === "issues" ? "list_issues" : "list_prs";
        const nextPage = this.page + 1;
        const payload = await callFunction(fn, {
          state: "open",
          page: nextPage,
        });
        const more = (payload.data || []).map((it) => this.mapItem(it));
        // Deduplicate: avoid duplicate entries at page boundaries (e.g., data changes during pagination)
        const seen = new Set(this.items.map((it) => it.number));
        for (const it of more) {
          if (!seen.has(it.number)) {
            this.items.push(it);
            seen.add(it.number);
          }
        }
        this.page = payload.page || nextPage;
        this.hasMore = !!payload.has_more;
        this.total = payload.total || this.items.length;
      } catch (e) {
        this.error = String((e && e.message) || e);
      } finally {
        this.loadingMore = false;
      }
    },
    async openItem(item) {
      this.selected = item;
      this.commentText = "";
      this.message = "";
      try {
        const fn = this.tab === "issues" ? "get_issue" : "get_pr";
        const detail = await callFunction(fn, { number: item.number });
        this.selected.body = ((detail.data && detail.data.body) || "").trim();
        const comments = await callFunction("list_comments", {
          number: item.number,
        });
        this.comments = Array.isArray(comments.data) ? comments.data : [];
      } catch (e) {
        this.error = String((e && e.message) || e);
      }
    },
    back() {
      this.selected = null;
      this.comments = [];
    },
    // ---- List item context menu ----
    openItemMenu(item, event) {
      this.menuItem = item;
      const menuWidth = 140;
      const menuHeight = 40;
      let left = event.clientX;
      let top = event.clientY;
      // Don't exceed viewport bottom-right
      if (left + menuWidth > window.innerWidth - 8) {
        left = window.innerWidth - menuWidth - 8;
      }
      if (left < 8) left = 8;
      if (top + menuHeight > window.innerHeight - 8) {
        top = window.innerHeight - menuHeight - 8;
      }
      if (top < 8) top = 8;
      this.menuStyle = { left: left + "px", top: top + "px" };
      this.menuVisible = true;
    },
    closeItemMenu() {
      this.menuVisible = false;
      this.menuItem = null;
    },
    // Generate prompt for handling the issue/PR.
    // isFork=true for "Fork and create CodeAgent to handle": goal is to modify code and submit PR to upstream original repo.
    buildItemPrompt(item, isFork = false) {
      const isIssue = this.tab === "issues";
      const repo = currentRepo || "(current repo)";
      const number = item.number;
      const title = item.title || "";
      if (isFork) {
        // Custom repo (forked from another repo): not our repo, goal is to fix code and submit PR to upstream original repo
        const head = `Please handle GitHub ${isIssue ? "Issue" : "Pull Request"} #${number}: ${title}`;
        const upstream = [
          `Target repo ${repo} is not our repo, but another open-source project's repo.`,
          "Local directory is a clone of the fork (origin points to your fork, upstream already configured to point to original repo).",
          "Goal: modify code to fix the issue, then submit a Pull Request to the upstream original repo.",
        ].join("\n");
        const flow = [
          "Open source contribution workflow:",
          "1. Cut a feature branch from upstream main: `git fetch upstream && git checkout -b fix/issue-<number> upstream/<upstream-main>`",
          "2. Complete changes on the branch, follow relevant development rules (including tests).",
          "3. Use `commit` tool to generate formal commit.",
          `4. Push branch to fork: \`git push origin <branch-name>\``,
          `5. Submit PR to upstream: \`gh pr create --repo ${repo} --head <your-fork>:<branch-name> --base <upstream-main> --title <title>\`, and link the Issue in description with \`Closes #${number}\`.`,
          "6. Before write operations (comment/close/merge), confirm with me first, then execute.",
        ].join("\n");
        return [head, "", upstream, "", flow].join("\n");
      }
      return isIssue
        ? [
            `Please handle GitHub Issue #${number} of current repo ${repo}: ${title}`,
            "",
            "Follow gh_rule to handle this Issue:",
            `1. Use \`gh issue view ${number}\` to view Issue details (title, author, body, labels, state), first restate content to confirm understanding.`,
            "2. Read body and existing comments, determine issue type and form handling plan.",
            "3. If code implementation needed, follow gh_rule and relevant development rules to complete modifications.",
            "4. Before write operations (comment/close), confirm with me first, then execute.",
          ].join("\n")
        : [
            `Please handle GitHub Pull Request #${number} of current repo ${repo}: ${title}`,
            "",
            "Follow gh_rule to handle this PR:",
            `1. Use \`gh pr view ${number}\` and \`gh pr diff ${number}\` to view details and changes.`,
            "2. Evaluate if mergeable or needs modification; if modification needed, follow gh_rule and relevant development rules to complete implementation/tests.",
            "3. Before merging, confirm with me first (including merge method), then execute.",
          ].join("\n");
    },
    // Handle issue/PR in currently active Agent
    async handleItem(item) {
      this.closeItemMenu();
      if (!item) return;
      // Defensive check: custom repo differs from current Agent working directory, handing to
      // current Agent would execute gh commands on wrong repo, so reject directly (UI already hides this entry).
      if (this.isManualRepo) {
        this.message = "Current repo is custom, differs from Agent working directory; please use 'Create new Agent to handle' instead";
        return;
      }
      const isIssue = this.tab === "issues";
      const kind = isIssue ? "Issue" : "Pull Request";
      const number = item.number;
      const send =
        typeof window !== "undefined" && window.__haijunbotSendToActiveAgent;
      if (typeof send !== "function") {
        this.message = "Host hasn't provided send channel, cannot handle";
        return;
      }
      const res = send(this.buildItemPrompt(item));
      if (res && res.success) {
        this.message = `Sent ${kind} #${number} handling prompt to current Agent`;
      } else {
        this.message = "Failed: " + ((res && res.error) || "Send failed");
      }
    },
    // Create new regular Agent to handle issue/PR
    async handleItemNewAgent(item) {
      this.closeItemMenu();
      if (!item) return;
      const isIssue = this.tab === "issues";
      const kind = isIssue ? "Issue" : "Pull Request";
      const number = item.number;
      const create =
        typeof window !== "undefined" && window.__haijunbotCreateAgentForTask;
      if (typeof create !== "function") {
        this.message = "Host hasn't provided create channel, cannot create Agent";
        return;
      }
      const workingDir = (this.workingDir || "").trim();
      if (!workingDir) {
        this.message = "Failed: working directory not resolved";
        return;
      }
      this.busy = true;
      this.message = `Creating new Agent to handle ${kind} #${number}...`;
      try {
        const res = await create({
          workingDir: workingDir,
          task: this.buildItemPrompt(item),
          name: `${kind} #${number}`,
        });
        if (res && res.success) {
          this.message = `Created new Agent to handle ${kind} #${number}`;
        } else {
          this.message = "Failed: " + ((res && res.error) || "Creation failed");
        }
      } catch (e) {
        this.message = "Failed: " + String((e && e.message) || e);
      } finally {
        this.busy = false;
      }
    },
    // Custom repo Issue: Fork original repo and clone to selected directory, then create CodeAgent there.
    // Flow: pick directory -> fork (reuse if exists) -> clone -> create CodeAgent.
    async handleItemForkCloneAgent(item) {
      this.closeItemMenu();
      if (!item) return;
      const repo = currentRepo;
      if (!repo) {
        this.message = "Failed: repo not resolved";
        return;
      }
      const number = item.number;
      const pick =
        typeof window !== "undefined" && window.__haijunbotPickDirectory;
      const create =
        typeof window !== "undefined" && window.__haijunbotCreateAgentForTask;
      if (typeof pick !== "function") {
        this.message = "Host hasn't provided directory picker, cannot select directory";
        return;
      }
      if (typeof create !== "function") {
        this.message = "Host hasn't provided create channel, cannot create Agent";
        return;
      }
      this.busy = true;
      try {
        this.message = "Please select target directory for Fork clone...";
        const targetDir = await pick();
        if (!targetDir) {
          this.message = "Cancelled";
          return;
        }
        this.message = `Forking and Cloning ${repo}...`;
        const prepared = await callFunction("prepare_issue_repo", {
          repo: repo,
          target_dir: targetDir,
        });
        const localDir = (prepared && prepared.local_dir) || "";
        if (!localDir) {
          this.message = "Failed: local directory not obtained";
          return;
        }
        this.message = `Creating CodeAgent (${localDir})...`;
        const res = await create({
          agentType: "code_agent",
          workingDir: localDir,
          task: this.buildItemPrompt(item, true),
          name: `Issue #${number}`,
        });
        if (res && res.success) {
          this.message = `Created CodeAgent to handle Issue #${number} (${localDir})`;
        } else {
          this.message = "Failed: " + ((res && res.error) || "Creation failed");
        }
      } catch (e) {
        this.message = "Failed: " + String((e && e.message) || e);
      } finally {
        this.busy = false;
      }
    },
    // ---- Write operations ----
    async postComment() {
      const body = (this.commentText || "").trim();
      if (!body) return;
      this.busy = true;
      this.message = "";
      try {
        await callFunction("comment", {
          number: this.selected.number,
          body: body,
        });
        this.commentText = "";
        this.message = "Comment posted";
        await this.openItem(this.selected);
      } catch (e) {
        this.message = "Failed: " + String((e && e.message) || e);
      } finally {
        this.busy = false;
      }
    },
    async closeIssue() {
      if (!confirm("Close issue #" + this.selected.number + "?")) return;
      this.busy = true;
      this.message = "";
      try {
        await callFunction("close_issue", { number: this.selected.number });
        this.message = "Issue closed";
        await this.refresh();
      } catch (e) {
        this.message = "Failed: " + String((e && e.message) || e);
      } finally {
        this.busy = false;
      }
    },
    async mergePr() {
      if (!confirm("Merge PR #" + this.selected.number + "?")) return;
      this.busy = true;
      this.message = "";
      try {
        await callFunction("merge_pr", {
          number: this.selected.number,
          merge_method: "merge",
        });
        this.message = "PR merged";
        await this.refresh();
      } catch (e) {
        this.message = "Failed: " + String((e && e.message) || e);
      } finally {
        this.busy = false;
      }
    },
    tabBtnStyle(t) {
      const active = this.tab === t;
      return {
        padding: "4px 10px",
        background: active ? "#1f6feb" : "#333",
        color: active ? "#fff" : "#ddd",
        border: "none",
        borderRadius: "4px",
        cursor: "pointer",
      };
    },
    openExternal(url) {
      if (url) window.open(url, "_blank");
    },
  },
  template: `
  <div style="padding:12px;font-size:13px;color:#ddd;overflow:auto;height:100%;box-sizing:border-box;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
      <strong style="font-size:14px;">GitHub</strong>
      <div style="display:flex;align-items:center;gap:6px;">
        <span style="font-size:11px;color:#888;" :title="repo || ''">{{ repo || 'No repo detected' }}</span>
        <button @click="toggleRepoEdit" title="Switch to another repo"
          style="padding:2px 6px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;font-size:11px;">Switch</button>
      </div>
    </div>
    <!-- Current target Agent: matches actual recipient of "handle in current Agent"; shows hint if no Agent -->
    <div style="font-size:11px;color:#58a6ff;margin-bottom:10px;">
      Current Agent: <span :title="agentName || ''">{{ agentName || 'No Agent selected' }}</span>
    </div>

    <!-- Repo switch: manually enter owner/repo to view other repos; can also restore to follow current working directory -->
    <div v-if="repoEditing" style="margin-bottom:10px;padding:8px;background:#252526;border-radius:6px;">
      <div style="font-size:11px;color:#888;margin-bottom:4px;">Repo (owner/repo, can paste GitHub URL)</div>
      <div style="display:flex;gap:6px;">
        <input v-model="repoInput" type="text" placeholder="e.g., octocat/Hello-World"
          @keydown.enter.prevent="setRepo"
          style="flex:1;min-width:0;padding:5px 8px;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;font-size:12px;">
        <button @click="setRepo" style="padding:5px 10px;background:#1f6feb;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;">OK</button>
      </div>
      <div style="display:flex;gap:6px;margin-top:6px;">
        <button @click="useCurrentDirRepo" style="padding:4px 8px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;font-size:11px;">Follow current directory</button>
        <button @click="repoEditing = false" style="padding:4px 8px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;font-size:11px;">Cancel</button>
      </div>
    </div>

    <!-- Messages -->
    <div v-if="message" style="margin-bottom:8px;padding:6px;background:#1f6feb33;border-radius:4px;font-size:12px;">{{ message }}</div>
    <div v-if="error" style="margin-bottom:8px;padding:6px;background:#f8514933;border-radius:4px;font-size:12px;color:#f85149;">{{ error }}</div>

    <!-- List view -->
    <div v-if="!selected">
      <div style="display:flex;gap:6px;margin-bottom:10px;">
        <button @click="tab='issues';refresh()" :style="tabBtnStyle('issues')">Issues</button>
        <button @click="tab='pulls';refresh()" :style="tabBtnStyle('pulls')">PRs</button>
        <button @click="refresh()" style="margin-left:auto;padding:4px 8px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;">🔄</button>
      </div>
      <div v-if="loading" style="color:#888;padding:20px;text-align:center;">Loading...</div>
      <div v-else-if="items.length === 0" style="color:#888;padding:20px;text-align:center;">No {{ tab === 'issues' ? 'issue' : 'PR' }} found</div>
      <div v-for="it in items" :key="it.number" @click="openItem(it)" @contextmenu.prevent="openItemMenu(it, $event)"
        style="padding:8px;margin-bottom:6px;background:#252526;border-radius:6px;cursor:pointer;border-left:3px solid #58a6ff;">
        <div style="display:flex;justify-content:space-between;">
          <span style="color:#888;">#{{ it.number }}</span>
          <span :style="{color: it.state === 'open' ? '#3fb950' : '#f85149', fontSize:'11px'}">{{ it.state }}</span>
        </div>
        <div style="margin-top:2px;font-weight:600;">{{ it.title }}</div>
        <div style="font-size:11px;color:#888;margin-top:2px;">@{{ it.user }} · {{ fmtDate(it.created_at) }}</div>
      </div>
      <!-- Pagination: show loaded/total, and provide "Load more" button -->
      <div v-if="items.length > 0" style="text-align:center;margin-top:10px;">
        <div style="font-size:11px;color:#888;margin-bottom:6px;">
          Loaded {{ items.length }} items<span v-if="total > items.length"> (approx {{ total }} total)</span>
        </div>
        <button v-if="hasMore" @click="loadMore" :disabled="loadingMore"
          style="padding:5px 14px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;font-size:12px;">
          {{ loadingMore ? 'Loading...' : 'Load more' }}
        </button>
      </div>
    </div>

    <!-- Detail view -->
    <div v-else>
      <button @click="back()" style="margin-bottom:8px;padding:4px 10px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;">← Back</button>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <h3 style="margin:0;font-size:14px;">#{{ selected.number }} {{ selected.title }}</h3>
        <a v-if="selected.html_url" href="javascript:void(0)" @click="openExternal(selected.html_url)" style="font-size:11px;color:#58a6ff;">Open ↗</a>
      </div>
      <div style="font-size:11px;color:#888;margin:4px 0;">@{{ selected.user }} · {{ fmtDate(selected.created_at) }}</div>
      <div style="white-space:pre-wrap;background:#1e1e1e;padding:8px;border-radius:6px;margin:8px 0;max-height:200px;overflow:auto;font-size:12px;">{{ selected.body || '(no description)' }}</div>

      <!-- Action buttons -->
      <div style="display:flex;gap:6px;margin-bottom:10px;">
        <button v-if="tab==='issues' && selected.state==='open'" @click="closeIssue" :disabled="busy"
          style="padding:5px 10px;background:#f8514933;color:#f85149;border:1px solid #f85149;border-radius:4px;cursor:pointer;">Close issue</button>
        <button v-if="tab==='pulls' && selected.state==='open'" @click="mergePr" :disabled="busy"
          style="padding:5px 10px;background:#238636;color:#fff;border:none;border-radius:4px;cursor:pointer;">Merge PR</button>
      </div>

      <!-- Comments -->
      <div style="font-size:12px;font-weight:600;margin-bottom:6px;">Comments ({{ comments.length }})</div>
      <div v-for="c in comments" :key="c.created_at" style="background:#1e1e1e;padding:6px;border-radius:6px;margin-bottom:6px;">
        <div style="font-size:11px;color:#888;">@{{ c.user }} · {{ fmtDate(c.created_at) }}</div>
        <div style="white-space:pre-wrap;font-size:12px;margin-top:2px;">{{ c.body }}</div>
      </div>
      <div v-if="comments.length === 0" style="font-size:11px;color:#888;">No comments</div>

      <textarea v-model="commentText" rows="3" placeholder="Write comment..."
        style="width:100%;box-sizing:border-box;margin-top:8px;padding:6px;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;font-size:12px;"></textarea>
      <button @click="postComment" :disabled="busy || !commentText.trim()"
        style="margin-top:6px;padding:6px 12px;background:#1f6feb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Post comment</button>
    </div>

    <!-- List item context menu -->
    <div v-if="menuVisible" :style="menuStyle"
      style="position:fixed;z-index:9999;background:#2d2d30;border:1px solid #454545;border-radius:6px;box-shadow:0 4px 12px #0008;padding:4px;min-width:120px;">
      <div v-if="!isManualRepo" @click="handleItem(menuItem)"
        style="padding:6px 10px;font-size:12px;color:#ddd;cursor:pointer;border-radius:4px;white-space:nowrap;">Handle in current Agent{{ agentName ? ' (' + agentName + ')' : '' }}</div>
      <div v-if="!isManualRepo" @click="handleItemNewAgent(menuItem)"
        style="padding:6px 10px;font-size:12px;color:#ddd;cursor:pointer;border-radius:4px;white-space:nowrap;">Create new Agent to handle</div>
      <div v-if="isManualRepo" @click="handleItemForkCloneAgent(menuItem)"
        style="padding:6px 10px;font-size:12px;color:#ddd;cursor:pointer;border-radius:4px;white-space:nowrap;">Fork and create CodeAgent to handle</div>
    </div>
  </div>
  `,
};
