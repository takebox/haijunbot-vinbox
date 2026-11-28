// AutoWorker plugin frontend sidebar view.
// Convention: Pure browser ES module, uses window.Vue for rendering, exports default component, no import 'vue'.
// Function: Manage a batch of tasks under backend working directory in editor left sidebar:
//   - Settings area: Configure backend working directory (localStorage persistence);
//   - Task list: Grouped by status, supports create/edit/mark complete/abandon;
//   - Context menu: Create Agent to execute task (Agent working_dir = task subdirectory);
//   - Scheduled polling + manual refresh.
// Authentication: All reads/writes via host window.__haijunbotFetch (auto-carries haijunbot auth),
//       calls plugin private function layer via plugin function proxy endpoint /api/plugins/master/function-call.

const PLUGIN = "autoworker";
// Backend working directory persistence key (fixed per plugin).
const WORKDIR_KEY = "haijunbot_autoworker_workdir";
// Polling interval (milliseconds).
const POLL_INTERVAL = 15000;

// Replicate App.vue gateway address parsing (sidebar component has no props injection, must parse itself)
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
    } catch {
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

// Get current page HTTP protocol (consistent with App.vue getHttpProtocol)
function getHttpProtocol() {
  return window.location.protocol === "https:" ? "https" : "http";
}

function gatewayBase() {
  const parsed = parseGatewayAddress(
    localStorage.getItem("haijunbot_gateway_url") || "",
  );
  const host = (parsed && parsed.host) || "127.0.0.1";
  const port = (parsed && parsed.port) || "8000";
  // Protocol: use explicit (https) if specified; otherwise use current page protocol (consistent with App.vue),
  // to avoid HTTPS page requesting http address causing mixed content blocked by browser.
  const protocol =
    parsed && parsed.protocol === "https" ? "https" : getHttpProtocol();
  return `${protocol}://${host}:${port}`;
}

// Call plugin private function via gateway plugin function proxy endpoint
async function callFunction(functionName, args) {
  const authedFetch =
    (typeof window !== "undefined" && window.__haijunbotFetch) || fetch;
  const resp = await authedFetch(
    `${gatewayBase()}/api/plugins/master/function-call`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plugin: PLUGIN,
        function: functionName,
        arguments: args || {},
      }),
    },
  );
  let result;
  try {
    result = await resp.json();
  } catch (e) {
    throw new Error("Gateway response anomaly", { cause: e });
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

// Status display and sort weight
const STATUS_LABELS = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  abandoned: "Abandoned",
};
const STATUS_COLORS = {
  pending: "#d29922",
  running: "#58a6ff",
  completed: "#3fb950",
  abandoned: "#888",
};
const STATUS_ORDER = ["running", "pending", "completed", "abandoned"];

export default {
  name: "AutoWorkerSidebarView",
  props: {
    workingDir: { type: String, default: "" },
  },
  data() {
    return {
      // Status mapping exposed to instance for template use (template cannot access module scope variables)
      STATUS_LABELS,
      STATUS_COLORS,
      // Backend working directory (localStorage persistence)
      workdir: "",
      workdirInput: "",
      workdirEditing: false,
      // Current active Agent (for display)
      agentName: "",
      // Task list and view state
      tasks: [],
      loading: false,
      error: "",
      message: "",
      // Detail/edit
      selected: null,
      editForm: { title: "", description: "", tags: "", due_date: "" },
      // Create task form
      creating: false,
      createForm: { title: "", description: "", tags: "", due_date: "" },
      // Context menu
      menuVisible: false,
      menuStyle: {},
      menuItem: null,
      busy: false,
    };
  },
  computed: {
    groupedTasks() {
      const groups = {};
      for (const s of STATUS_ORDER) groups[s] = [];
      for (const t of this.tasks) {
        const s = STATUS_LABELS[t.status] ? t.status : "pending";
        groups[s].push(t);
      }
      return STATUS_ORDER.filter((s) => groups[s].length > 0).map((s) => ({
        status: s,
        label: STATUS_LABELS[s],
        color: STATUS_COLORS[s],
        items: groups[s],
      }));
    },
  },
  mounted() {
    this.restoreWorkdir();
    this.refreshAgentName();
    if (this.workdir) this.refresh();
    // Subscribe to host agent_changed event: sync refresh top name when switching Agent
    const on = typeof window !== "undefined" && window.__haijunbotOn;
    if (typeof on === "function") {
      this._offAgentChanged = on("agent_changed", () => {
        this.refreshAgentName();
      });
    }
    // Scheduled polling (when working directory exists)
    this._pollTimer = setInterval(() => {
      if (this.workdir && !this.loading && !this.selected) this.refresh(true);
    }, POLL_INTERVAL);
    // Click elsewhere / press Esc to close context menu
    this._onDocClick = () => this.closeItemMenu();
    this._onDocKeydown = (e) => {
      if (e.key === "Escape") this.closeItemMenu();
    };
    document.addEventListener("click", this._onDocClick);
    document.addEventListener("keydown", this._onDocKeydown);
  },
  beforeUnmount() {
    if (typeof this._offAgentChanged === "function") this._offAgentChanged();
    if (this._pollTimer) clearInterval(this._pollTimer);
    document.removeEventListener("click", this._onDocClick);
    document.removeEventListener("keydown", this._onDocKeydown);
  },
  watch: {
    workingDir() {
      this.refreshAgentName();
    },
  },
  methods: {
    // ---- Working directory settings ----
    restoreWorkdir() {
      try {
        const saved = (localStorage.getItem(WORKDIR_KEY) || "").trim();
        if (saved) {
          this.workdir = saved;
          this.workdirInput = saved;
        }
      } catch {
        /* Ignore when localStorage unavailable */
      }
    },
    toggleWorkdirEdit() {
      this.workdirEditing = !this.workdirEditing;
      if (this.workdirEditing) this.workdirInput = this.workdir || "";
    },
    saveWorkdir() {
      const value = (this.workdirInput || "").trim();
      if (!value) {
        this.error = "Please fill in backend working directory";
        return;
      }
      this.error = "";
      this.workdir = value;
      try {
        localStorage.setItem(WORKDIR_KEY, value);
      } catch {
        /* Ignore storage failure */
      }
      this.workdirEditing = false;
      this.selected = null;
      this.refresh();
    },
    // Pick working directory using host-provided directory selection dialog
    async pickWorkdir() {
      const pick =
        typeof window !== "undefined" && window.__haijunbotPickDirectory;
      if (typeof pick !== "function") {
        this.error = "Host does not provide directory selection channel";
        return;
      }
      try {
        const dir = await pick();
        if (dir) this.workdirInput = dir;
      } catch (e) {
        this.error = String((e && e.message) || e);
      }
    },
    // ---- Agent info ----
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
    // ---- Task list ----
    async refresh(silent) {
      if (!this.workdir) {
        this.tasks = [];
        return;
      }
      if (!silent) {
        this.loading = true;
        this.error = "";
        this.message = "";
      }
      try {
        const payload = await callFunction("list_tasks", {
          workdir: this.workdir,
        });
        this.tasks = Array.isArray(payload.data) ? payload.data : [];
        // Sync refresh currently selected task details (if still in list)
        if (this.selected) {
          const found = this.tasks.find((t) => t.id === this.selected.id);
          if (found) this.selected = found;
        }
      } catch (e) {
        if (!silent) this.error = String((e && e.message) || e);
      } finally {
        if (!silent) this.loading = false;
      }
    },
    fmtDate(s) {
      if (!s) return "";
      try {
        return new Date(s).toLocaleString();
      } catch {
        return s;
      }
    },
    tagsText(tags) {
      return Array.isArray(tags) ? tags.join(", ") : "";
    },
    // ---- Detail / Edit ----
    openTask(task) {
      this.selected = task;
      this.editForm = {
        title: task.title || "",
        description: task.description || "",
        tags: this.tagsText(task.tags),
        due_date: task.due_date || "",
      };
      this.message = "";
      this.error = "";
    },
    back() {
      this.selected = null;
    },
    async saveTask() {
      if (!this.selected) return;
      if (!this.editForm.title.trim()) {
        this.error = "Title cannot be empty";
        return;
      }
      this.busy = true;
      this.error = "";
      this.message = "";
      try {
        await callFunction("update_task", {
          workdir: this.workdir,
          task_id: this.selected.id,
          title: this.editForm.title.trim(),
          description: this.editForm.description,
          tags: this.editForm.tags,
          due_date: this.editForm.due_date,
        });
        this.message = "Saved";
        await this.refresh(true);
      } catch (e) {
        this.error = String((e && e.message) || e);
      } finally {
        this.busy = false;
      }
    },
    // ---- Create task ----
    toggleCreate() {
      this.creating = !this.creating;
      if (this.creating) {
        this.createForm = { title: "", description: "", tags: "", due_date: "" };
        this.error = "";
      }
    },
    async createTask() {
      if (!this.createForm.title.trim()) {
        this.error = "Title cannot be empty";
        return;
      }
      this.busy = true;
      this.error = "";
      this.message = "";
      try {
        const payload = await callFunction("create_task", {
          workdir: this.workdir,
          title: this.createForm.title.trim(),
          description: this.createForm.description,
          tags: this.createForm.tags,
          due_date: this.createForm.due_date,
        });
        const created = payload.data || {};
        this.message = `Created task ${created.id || ""}`;
        this.creating = false;
        await this.refresh(true);
      } catch (e) {
        this.error = String((e && e.message) || e);
      } finally {
        this.busy = false;
      }
    },
    // ---- Status marking (manual fallback) ----
    async markStatus(task, status) {
      this.closeItemMenu();
      if (!task) return;
      this.busy = true;
      this.error = "";
      this.message = "";
      try {
        await callFunction("set_status", {
          workdir: this.workdir,
          task_id: task.id,
          status: status,
        });
        this.message = `Task ${task.id} marked as ${STATUS_LABELS[status] || status}`;
        await this.refresh(true);
      } catch (e) {
        this.error = String((e && e.message) || e);
      } finally {
        this.busy = false;
      }
    },
    // ---- Context menu ----
    openItemMenu(task, event) {
      this.menuItem = task;
      const menuWidth = 160;
      const menuHeight = 150;
      let left = event.clientX;
      let top = event.clientY;
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
    // Generate prompt to execute this task
    buildTaskPrompt(task) {
      const lines = [
        `Please execute task ${task.id}: ${task.title || ""}`,
      ];
      if (task.description) {
        lines.push("", "Task description:", task.description);
      }
      if (Array.isArray(task.tags) && task.tags.length) {
        lines.push("", `Tags: ${task.tags.join(", ")}`);
      }
      if (task.due_date) {
        lines.push(`Due date: ${task.due_date}`);
      }
      lines.push(
        "",
        "Notes:",
        "- Your current working directory is this task's directory.",
        "- You can use task_manager tool to view/update this task, save key info (add_note).",
        "- After completion, please use task_manager to mark this task status as completed.",
      );
      return lines.join("\n");
    },
    // Create Agent to execute this task (Agent working_dir = task subdirectory)
    async createAgentForTask(task) {
      this.closeItemMenu();
      if (!task) return;
      const create =
        typeof window !== "undefined" && window.__haijunbotCreateAgentForTask;
      if (typeof create !== "function") {
        this.error = "Host does not provide creation channel, cannot create Agent";
        return;
      }
      const taskDir = (task.task_dir || "").trim();
      if (!taskDir) {
        this.error = "Task directory unknown, please refresh first";
        return;
      }
      this.busy = true;
      this.error = "";
      this.message = `Creating Agent for task ${task.id}...`;
      try {
        const res = await create({
          workingDir: taskDir,
          task: this.buildTaskPrompt(task),
          name: `${task.id} ${task.title || ""}`.trim(),
        });
        if (res && res.success) {
          // Mark as running
          try {
            await callFunction("set_status", {
              workdir: this.workdir,
              task_id: task.id,
              status: "running",
            });
          } catch {
            /* Mark failure doesn't block creation result notification */
          }
          this.message = `Created Agent to execute task ${task.id}`;
          await this.refresh(true);
        } else {
          this.error = "Failed: " + ((res && res.error) || "Creation failed");
        }
      } catch (e) {
        this.error = "Failed: " + String((e && e.message) || e);
      } finally {
        this.busy = false;
      }
    },
    // Pass task to current active Agent (send prompt)
    async handleInCurrentAgent(task) {
      this.closeItemMenu();
      if (!task) return;
      const send =
        typeof window !== "undefined" && window.__haijunbotSendToActiveAgent;
      if (typeof send !== "function") {
        this.error = "Host does not provide send channel";
        return;
      }
      const res = send(this.buildTaskPrompt(task));
      if (res && res.success) {
        this.message = `Sent task ${task.id} prompt to current Agent`;
      } else {
        this.error = "Failed: " + ((res && res.error) || "Send failed");
      }
    },
    editFromMenu(task) {
      this.closeItemMenu();
      if (task) this.openTask(task);
    },
    statusBtnStyle(status) {
      return {
        color: STATUS_COLORS[status] || "#ddd",
        border: `1px solid ${STATUS_COLORS[status] || "#444"}`,
      };
    },
  },
  template: `
  <div style="padding:12px;font-size:13px;color:#ddd;overflow:auto;height:100%;box-sizing:border-box;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
      <strong style="font-size:14px;">Tasks</strong>
      <div style="display:flex;align-items:center;gap:6px;">
        <button @click="toggleWorkdirEdit" title="Set backend working directory"
          style="padding:2px 6px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;font-size:11px;">Settings</button>
        <button @click="refresh()" title="Refresh"
          style="padding:2px 6px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;font-size:11px;">🔄</button>
      </div>
    </div>
    <div style="font-size:11px;color:#888;margin-bottom:4px;" :title="workdir || ''">
      Working directory: {{ workdir || 'Not set' }}
    </div>
    <div style="font-size:11px;color:#58a6ff;margin-bottom:10px;">
      Current Agent: <span :title="agentName || ''">{{ agentName || 'No Agent selected' }}</span>
    </div>

    <!-- Working directory settings -->
    <div v-if="workdirEditing" style="margin-bottom:10px;padding:8px;background:#252526;border-radius:6px;">
      <div style="font-size:11px;color:#888;margin-bottom:4px;">Backend working directory (parent directory of task subdirectories)</div>
      <div style="display:flex;gap:6px;">
        <input v-model="workdirInput" type="text" placeholder="e.g. /home/user/tasks"
          @keydown.enter.prevent="saveWorkdir"
          style="flex:1;min-width:0;padding:5px 8px;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;font-size:12px;">
        <button @click="pickWorkdir" style="padding:5px 8px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;font-size:12px;">Select</button>
      </div>
      <div style="display:flex;gap:6px;margin-top:6px;">
        <button @click="saveWorkdir" style="padding:4px 10px;background:#1f6feb;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;">Save</button>
        <button @click="workdirEditing = false" style="padding:4px 8px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;font-size:11px;">Cancel</button>
      </div>
    </div>

    <!-- Messages -->
    <div v-if="message" style="margin-bottom:8px;padding:6px;background:#1f6feb33;border-radius:4px;font-size:12px;">{{ message }}</div>
    <div v-if="error" style="margin-bottom:8px;padding:6px;background:#f8514933;border-radius:4px;font-size:12px;color:#f85149;">{{ error }}</div>

    <!-- Working directory not set -->
    <div v-if="!workdir" style="color:#888;padding:20px;text-align:center;">
      Please click "Settings" in top right to configure backend working directory.
    </div>

    <!-- List view -->
    <div v-else-if="!selected">
      <div style="display:flex;gap:6px;margin-bottom:10px;">
        <button @click="toggleCreate"
          style="padding:4px 10px;background:#1f6feb;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;">+ New Task</button>
      </div>

      <!-- Create form -->
      <div v-if="creating" style="margin-bottom:10px;padding:8px;background:#252526;border-radius:6px;">
        <input v-model="createForm.title" type="text" placeholder="Title (required)"
          style="width:100%;box-sizing:border-box;margin-bottom:6px;padding:5px 8px;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;font-size:12px;">
        <textarea v-model="createForm.description" rows="2" placeholder="Description"
          style="width:100%;box-sizing:border-box;margin-bottom:6px;padding:5px 8px;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;font-size:12px;"></textarea>
        <input v-model="createForm.tags" type="text" placeholder="Tags (comma separated)"
          style="width:100%;box-sizing:border-box;margin-bottom:6px;padding:5px 8px;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;font-size:12px;">
        <input v-model="createForm.due_date" type="text" placeholder="Due date (e.g. 2026-10-20)"
          style="width:100%;box-sizing:border-box;margin-bottom:6px;padding:5px 8px;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;font-size:12px;">
        <div style="display:flex;gap:6px;">
          <button @click="createTask" :disabled="busy"
            style="padding:5px 12px;background:#1f6feb;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;">Create</button>
          <button @click="creating = false"
            style="padding:5px 10px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;font-size:12px;">Cancel</button>
        </div>
      </div>

      <div v-if="loading" style="color:#888;padding:20px;text-align:center;">Loading...</div>
      <div v-else-if="tasks.length === 0" style="color:#888;padding:20px;text-align:center;">No tasks</div>

      <div v-for="g in groupedTasks" :key="g.status" style="margin-bottom:12px;">
        <div :style="{color:g.color,fontSize:'11px',fontWeight:'600',marginBottom:'4px'}">
          {{ g.label }} ({{ g.items.length }})
        </div>
        <div v-for="t in g.items" :key="t.id"
          @click="openTask(t)" @contextmenu.prevent="openItemMenu(t, $event)"
          style="padding:8px;margin-bottom:6px;background:#252526;border-radius:6px;cursor:pointer;border-left:3px solid #58a6ff;">
          <div style="display:flex;justify-content:space-between;">
            <span style="color:#888;">{{ t.id }}</span>
            <span :style="{color: STATUS_COLORS[t.status] || '#888', fontSize:'11px'}">{{ STATUS_LABELS[t.status] || t.status }}</span>
          </div>
          <div style="margin-top:2px;font-weight:600;">{{ t.title }}</div>
          <div v-if="tagsText(t.tags)" style="font-size:11px;color:#888;margin-top:2px;">{{ tagsText(t.tags) }}</div>
          <div v-if="t.due_date" style="font-size:11px;color:#d29922;margin-top:2px;">Due {{ t.due_date }}</div>
        </div>
      </div>
    </div>

    <!-- Detail view -->
    <div v-else>
      <button @click="back()" style="margin-bottom:8px;padding:4px 10px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;">← Back</button>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <h3 style="margin:0;font-size:14px;">{{ selected.id }}</h3>
        <span :style="{color: STATUS_COLORS[selected.status] || '#888', fontSize:'12px'}">{{ STATUS_LABELS[selected.status] || selected.status }}</span>
      </div>
      <div style="font-size:11px;color:#888;margin:4px 0;">Created {{ fmtDate(selected.created_at) }} · Updated {{ fmtDate(selected.updated_at) }}</div>

      <!-- Edit form -->
      <div style="margin:8px 0;">
        <input v-model="editForm.title" type="text" placeholder="Title (required)"
          style="width:100%;box-sizing:border-box;margin-bottom:6px;padding:5px 8px;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;font-size:12px;">
        <textarea v-model="editForm.description" rows="4" placeholder="Description"
          style="width:100%;box-sizing:border-box;margin-bottom:6px;padding:5px 8px;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;font-size:12px;"></textarea>
        <input v-model="editForm.tags" type="text" placeholder="Tags (comma separated)"
          style="width:100%;box-sizing:border-box;margin-bottom:6px;padding:5px 8px;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;font-size:12px;">
        <input v-model="editForm.due_date" type="text" placeholder="Due date (e.g. 2026-10-20)"
          style="width:100%;box-sizing:border-box;margin-bottom:6px;padding:5px 8px;background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:4px;font-size:12px;">
        <button @click="saveTask" :disabled="busy"
          style="padding:5px 12px;background:#1f6feb;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;">Save</button>
      </div>

      <!-- Execute actions -->
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;">
        <button @click="createAgentForTask(selected)" :disabled="busy"
          style="padding:5px 10px;background:#238636;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;">Create Agent to Execute</button>
        <button @click="handleInCurrentAgent(selected)"
          style="padding:5px 10px;background:#333;color:#ddd;border:none;border-radius:4px;cursor:pointer;font-size:12px;">Pass to Current Agent</button>
      </div>

      <!-- Manual fallback marking -->
      <div style="font-size:11px;color:#888;margin-bottom:4px;">Mark Status</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;">
        <button v-for="s in ['pending','running','completed','abandoned']" :key="s"
          @click="markStatus(selected, s)" :disabled="busy"
          :style="statusBtnStyle(s)"
          style="padding:4px 8px;background:transparent;border-radius:4px;cursor:pointer;font-size:11px;">
          {{ STATUS_LABELS[s] }}
        </button>
      </div>

      <!-- notes -->
      <div style="font-size:12px;font-weight:600;margin:12px 0 6px;">Key Info ({{ (selected.notes || []).length }})</div>
      <div v-for="(n, i) in (selected.notes || [])" :key="i" style="background:#1e1e1e;padding:6px;border-radius:6px;margin-bottom:6px;">
        <div style="font-size:11px;color:#888;">{{ fmtDate(n.time) }}</div>
        <div style="white-space:pre-wrap;font-size:12px;margin-top:2px;">{{ n.content }}</div>
      </div>
      <div v-if="!(selected.notes || []).length" style="font-size:11px;color:#888;">None</div>

      <div style="font-size:11px;color:#888;margin-top:10px;word-break:break-all;">
        Task directory: {{ selected.task_dir }}
      </div>
    </div>

    <!-- List item context menu -->
    <div v-if="menuVisible" :style="menuStyle"
      style="position:fixed;z-index:9999;background:#2d2d30;border:1px solid #454545;border-radius:6px;box-shadow:0 4px 12px #0008;padding:4px;min-width:140px;">
      <div @click="createAgentForTask(menuItem)"
        style="padding:6px 10px;font-size:12px;color:#ddd;cursor:pointer;border-radius:4px;white-space:nowrap;">Create Agent to Execute This Task</div>
      <div @click="handleInCurrentAgent(menuItem)"
        style="padding:6px 10px;font-size:12px;color:#ddd;cursor:pointer;border-radius:4px;white-space:nowrap;">Pass to Current Agent{{ agentName ? ' (' + agentName + ')' : '' }}</div>
      <div @click="editFromMenu(menuItem)"
        style="padding:6px 10px;font-size:12px;color:#ddd;cursor:pointer;border-radius:4px;white-space:nowrap;">Edit</div>
      <div @click="markStatus(menuItem, 'completed')"
        style="padding:6px 10px;font-size:12px;color:#3fb950;cursor:pointer;border-radius:4px;white-space:nowrap;">Mark Complete</div>
      <div @click="markStatus(menuItem, 'abandoned')"
        style="padding:6px 10px;font-size:12px;color:#f85149;cursor:pointer;border-radius:4px;white-space:nowrap;">Mark Abandoned</div>
    </div>
  </div>
  `,
};