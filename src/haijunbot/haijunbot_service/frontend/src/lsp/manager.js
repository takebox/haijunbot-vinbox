/**
 * Lightweight LSP client manager.
 *
 * Responsibilities:
 *  - Reuse WebSocket connections by (serverId, workspaceRoot)
 *  - Build its own JSON-RPC channel (auto-incrementing id + Promise map), independent of monaco.lsp's full synchronizer
 *  - Document sync (didOpen / didChange / didClose) only targets models of the requested language
 *  - Register hover / completion / diagnostics / definition / formatting language feature providers, isolated by language
 *  - Silent failure degradation: connection failures or missing servers only console.warn, without affecting the editor
 *
 * ## Why build our own (important)
 *
 * `monaco.lsp`'s `MonacoLspClient` has a built-in `TextDocumentSynchronizer` that takes over **all**
 * models from `monaco.editor.getModels()` after initialize, with no way to filter by language.
 * Used directly, a Python server would receive didOpen for Go files, and multiple languages/servers could not coexist.
 * An earlier implementation avoided this by "disposing non-target-language models", which broke multiple tabs (switching tabs lost the undo stack).
 *
 * So here we build a lightweight client ourselves: only reuse the native WebSocket, manage JSON-RPC and document sync ourselves,
 * and register providers via `monaco.languages.registerXxxProvider(language, ...)`, naturally isolated by language.
 * **Never dispose any model**.
 */

import * as monaco from "monaco-editor/esm/vs/editor/editor.main.js";

/** @type {Map<string, {client: LspClient, socket: WebSocket, spec: object, root: string, models: Set<object>, subs: Map<object, {changeSub: object, disposeSub: object}>}>} */
const sessions = new Map();

/** Languages with registered providers, to avoid duplicate registration. */
const registeredProviders = new Set();

function sessionKey(serverId, root) {
  return `${serverId}::${root || ""}`;
}

/**
 * Lightweight JSON-RPC over WebSocket client.
 * Requests match responses via an auto-incrementing id; notifications are sent one-way; server-initiated messages (e.g. publishDiagnostics) go through the callback.
 */
class LspClient {
  /**
   * @param {WebSocket} socket
   * @param {object} opts
   * @param {(msg: object) => void} [opts.onNotification] Handles server-initiated notifications
   */
  constructor(socket, opts = {}) {
    this.socket = socket;
    this.onNotification = opts.onNotification || (() => {});
    this._seq = 0;
    this._pending = new Map(); // id -> {resolve, reject}
    this._ready = new Promise((resolve, reject) => {
      this._readyResolve = resolve;
      this._readyReject = reject;
    });
    this._initialize();
  }

  _initialize() {
    this.socket.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!msg || typeof msg !== "object") return;
      if (typeof msg.id === "number" || typeof msg.id === "string") {
        // Response to a request
        const pending = this._pending.get(msg.id);
        if (pending) {
          this._pending.delete(msg.id);
          if (msg.error)
            pending.reject(new Error(msg.error.message || "LSP error"));
          else pending.resolve(msg.result);
        }
      } else if (msg.method) {
        // Server-initiated notification (e.g. publishDiagnostics)
        this.onNotification(msg);
      }
    };
    this.socket.onerror = () => {
      this._failAll(new Error("LSP WebSocket error"));
    };
    this.socket.onclose = () => {
      this._failAll(new Error("LSP WebSocket closed"));
    };
    // Mark ready (the socket being open is guaranteed by the caller)
    this._readyResolve();
  }

  _failAll(err) {
    for (const [, pending] of this._pending) pending.reject(err);
    this._pending.clear();
  }

  /** Wait for the initialization handshake to complete (optional; usable as soon as the connection is established). */
  ready() {
    return this._ready;
  }

  /**
   * Send a JSON-RPC request, returning a Promise<result>.
   * @param {string} method
   * @param {object} params
   */
  request(method, params) {
    const id = ++this._seq;
    return new Promise((resolve, reject) => {
      this._pending.set(id, { resolve, reject });
      try {
        this.socket.send(
          JSON.stringify({ jsonrpc: "2.0", id, method, params: params || {} }),
        );
      } catch (err) {
        this._pending.delete(id);
        reject(err);
      }
    });
  }

  /** Send a JSON-RPC notification (no response). */
  notify(method, params) {
    try {
      this.socket.send(
        JSON.stringify({ jsonrpc: "2.0", method, params: params || {} }),
      );
    } catch {
      /* Ignore send failures */
    }
  }

  close() {
    try {
      this.socket.close();
    } catch {
      /* ignore */
    }
    this._failAll(new Error("LSP client closed"));
  }
}

/**
 * Establish a WebSocket to the language server and complete the LSP initialize handshake.
 *
 * @param {object} params
 * @param {object} params.spec Language server manifest
 * @param {string} params.workspaceRoot workspace root directory
 * @param {object} params.deps
 * @returns {Promise<LspClient>}
 */
async function connectLspClient({ spec, workspaceRoot, deps }) {
  const { host, port } = deps.getGatewayAddress();
  const wsProtocol = deps.getWebSocketProtocol();
  const rootParam = workspaceRoot
    ? `?root=${encodeURIComponent(workspaceRoot)}`
    : "";
  const url = `${wsProtocol}://${host}:${port}/api/lsp/${encodeURIComponent(spec.id)}${rootParam}`;

  const socket = await openLspSocket({
    url,
    protocols: deps.buildWebSocketProtocols(),
  });

  const client = new LspClient(socket, {
    onNotification: (msg) => handleServerNotification(spec, msg),
  });

  // LSP initialize handshake
  const capabilities = await client.request("initialize", {
    processId: null,
    rootUri: workspaceRoot ? `file://${workspaceRoot}` : null,
    capabilities: {
      textDocument: {
        hover: { contentFormat: ["markdown", "plaintext"] },
        completion: { completionItem: { snippetSupport: true } },
        definition: {},
        documentFormatting: { dynamicRegistration: false },
        publishDiagnostics: {},
      },
    },
  });
  client.notify("initialized", {});

  // Register language feature providers according to the server's capabilities
  registerLanguageFeatures(spec, capabilities || {}, deps);
  return client;
}

/** Open a WebSocket and wait for the handshake (with timeout). */
function openLspSocket({ url, protocols, timeoutMs = 8000 }) {
  return new Promise((resolve, reject) => {
    let settled = false;
    let socket;
    try {
      socket = new WebSocket(url, protocols);
    } catch (error) {
      reject(error);
      return;
    }
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      try {
        socket.close();
      } catch {
        /* ignore */
      }
      reject(new Error("LSP WebSocket connection timed out"));
    }, timeoutMs);
    socket.onopen = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(socket);
    };
    socket.onerror = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(new Error("LSP WebSocket connection failed"));
    };
    socket.onclose = (event) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(
        new Error(
          `LSP WebSocket was closed: code=${event?.code} reason=${event?.reason || ""}`,
        ),
      );
    };
  });
}

/**
 * Handle server-initiated notifications (currently only publishDiagnostics).
 * Find the matching Monaco model by the uri in the notification and write the diagnostic markers.
 */
function handleServerNotification(spec, msg) {
  if (msg.method === "textDocument/publishDiagnostics") {
    const params = msg.params || {};
    const uri = String(params.uri || "").toLowerCase();
    // Iterate all sessions to find a matching model
    for (const entry of sessions.values()) {
      for (const model of entry.models) {
        if (String(model.uri.toString(true)).toLowerCase() === uri) {
          const markers = (params.diagnostics || []).map((d) => ({
            severity: toMonacoSeverity(d.severity),
            message: d.message || "",
            startLineNumber: (d.range?.start?.line ?? 0) + 1,
            startColumn: (d.range?.start?.character ?? 0) + 1,
            endLineNumber: (d.range?.end?.line ?? 0) + 1,
            endColumn: (d.range?.end?.character ?? 0) + 1,
            source: d.source || spec.id,
          }));
          monaco.editor.setModelMarkers(model, `lsp:${spec.id}`, markers);
          return;
        }
      }
    }
  }
}

function toMonacoSeverity(severity) {
  // LSP: 1=Error 2=Warning 3=Information 4=Hint
  switch (severity) {
    case 1:
      return monaco.MarkerSeverity.Error;
    case 2:
      return monaco.MarkerSeverity.Warning;
    case 3:
      return monaco.MarkerSeverity.Info;
    case 4:
      return monaco.MarkerSeverity.Hint;
    default:
      return monaco.MarkerSeverity.Error;
  }
}

/**
 * Register hover / completion providers per server capability (only once per language).
 * Providers are naturally isolated by language via `monaco.languages.registerXxxProvider(language, ...)`.
 */
function registerLanguageFeatures(spec, capabilities, deps) {
  const language = spec.monacoLanguage;
  if (!language || registeredProviders.has(language)) return;

  const serverCaps = capabilities?.capabilities || {};

  /**
   * Ensure the target file in the definition result has a Monaco model (needed for cross-file peek).
   * Monaco's built-in peek uses monaco.editor.getModel(uri) to fetch the target model and render its content;
   * if the target file was never opened, the model does not exist → peek only shows the file name/line-column and blank content.
   * Here we asynchronously load the target file and create the model before the provider returns (without activating a tab),
   * so peek gets the content. Load failures are silently skipped (preserving the original degradation behavior).
   */
  async function ensureDefinitionModels(result) {
    if (!deps?.ensureModelForUri) return;
    const items = Array.isArray(result) ? result : [result];
    for (const it of items) {
      if (!it) continue;
      const uri = it.targetUri || it.uri;
      if (uri) {
        try {
          await deps.ensureModelForUri(uri);
        } catch {
          /* Ignore: a single target failing to load does not affect the remaining definitions */
        }
      }
    }
  }

  if (serverCaps.hoverProvider) {
    monaco.languages.registerHoverProvider(language, {
      provideHover: async (model, position) => {
        const client = getClientForModel(model, spec);
        if (!client) return null;
        try {
          const result = await client.request("textDocument/hover", {
            textDocument: { uri: model.uri.toString(true) },
            position: {
              line: position.lineNumber - 1,
              character: position.column - 1,
            },
          });
          if (!result) return null;
          const contents = Array.isArray(result.contents)
            ? result.contents
            : [result.contents];
          const value = contents
            .map((c) => (typeof c === "string" ? c : c?.value || ""))
            .join("\n\n");
          if (!value) return null;
          return { contents: [{ value, isTrusted: true }] };
        } catch {
          return null;
        }
      },
    });
  }

  if (serverCaps.completionProvider) {
    monaco.languages.registerCompletionItemProvider(language, {
      triggerCharacters: serverCaps.completionProvider.triggerCharacters || [],
      provideCompletionItems: async (model, position) => {
        const client = getClientForModel(model, spec);
        if (!client) return { suggestions: [] };
        try {
          const result = await client.request("textDocument/completion", {
            textDocument: { uri: model.uri.toString(true) },
            position: {
              line: position.lineNumber - 1,
              character: position.column - 1,
            },
            context: { triggerKind: 1 },
          });
          const items = Array.isArray(result) ? result : result?.items || [];
          return {
            suggestions: items.map((item) => ({
              label: item.label,
              kind: toMonacoCompletionKind(item.kind),
              insertText: item.insertText ?? item.label,
              detail: item.detail || "",
              documentation:
                item.documentation && typeof item.documentation === "object"
                  ? item.documentation.value
                  : item.documentation,
              sortText: item.sortText,
              filterText: item.filterText,
            })),
          };
        } catch {
          return { suggestions: [] };
        }
      },
    });
  }

  if (serverCaps.definitionProvider) {
    monaco.languages.registerDefinitionProvider(language, {
      provideDefinition: async (model, position) => {
        const client = getClientForModel(model, spec);
        if (!client) return null;
        try {
          const result = await client.request("textDocument/definition", {
            textDocument: { uri: model.uri.toString(true) },
            position: {
              line: position.lineNumber - 1,
              character: position.column - 1,
            },
          });
          // Cross-file peek requires the target model to be ready; preload it before returning
          await ensureDefinitionModels(result);
          return toMonacoDefinition(result);
        } catch {
          return null;
        }
      },
    });
  }

  if (serverCaps.documentFormattingProvider) {
    monaco.languages.registerDocumentFormattingEditProvider(language, {
      provideDocumentFormattingEdits: async (model, options) => {
        const client = getClientForModel(model, spec);
        if (!client) return [];
        try {
          const result = await client.request("textDocument/formatting", {
            textDocument: { uri: model.uri.toString(true) },
            options: {
              tabSize: options?.tabSize ?? 4,
              insertSpaces: options?.insertSpaces ?? true,
            },
          });
          return toMonacoTextEdits(result);
        } catch {
          return [];
        }
      },
    });
  }

  registeredProviders.add(language);
}

function getClientForModel(model, spec) {
  const uri = String(model.uri.toString(true)).toLowerCase();
  for (const entry of sessions.values()) {
    if (entry.spec.id !== spec.id) continue;
    for (const m of entry.models) {
      if (String(m.uri.toString(true)).toLowerCase() === uri)
        return entry.client;
    }
  }
  return null;
}

function toMonacoCompletionKind(kind) {
  // LSP CompletionItemKind: 1=Text ... 25=TypeParameter
  const map = {
    1: monaco.languages.CompletionItemKind.Text,
    2: monaco.languages.CompletionItemKind.Method,
    3: monaco.languages.CompletionItemKind.Function,
    4: monaco.languages.CompletionItemKind.Constructor,
    5: monaco.languages.CompletionItemKind.Field,
    6: monaco.languages.CompletionItemKind.Variable,
    7: monaco.languages.CompletionItemKind.Class,
    8: monaco.languages.CompletionItemKind.Interface,
    9: monaco.languages.CompletionItemKind.Module,
    10: monaco.languages.CompletionItemKind.Property,
    11: monaco.languages.CompletionItemKind.Unit,
    12: monaco.languages.CompletionItemKind.Value,
    13: monaco.languages.CompletionItemKind.Enum,
    14: monaco.languages.CompletionItemKind.Keyword,
    15: monaco.languages.CompletionItemKind.Snippet,
    16: monaco.languages.CompletionItemKind.Color,
    17: monaco.languages.CompletionItemKind.File,
    18: monaco.languages.CompletionItemKind.Reference,
    19: monaco.languages.CompletionItemKind.Folder,
    20: monaco.languages.CompletionItemKind.EnumMember,
    21: monaco.languages.CompletionItemKind.Constant,
    22: monaco.languages.CompletionItemKind.Struct,
    23: monaco.languages.CompletionItemKind.Event,
    24: monaco.languages.CompletionItemKind.Operator,
    25: monaco.languages.CompletionItemKind.TypeParameter,
  };
  return map[kind] ?? monaco.languages.CompletionItemKind.Text;
}

/** LSP 0-based position → Monaco 1-based position. */
function toMonacoPosition(pos) {
  return {
    lineNumber: (pos?.line ?? 0) + 1,
    column: (pos?.character ?? 0) + 1,
  };
}

/** LSP 0-based range → Monaco 1-based IRange. */
function toMonacoRange(range) {
  return {
    startLineNumber: (range?.start?.line ?? 0) + 1,
    startColumn: (range?.start?.character ?? 0) + 1,
    endLineNumber: (range?.end?.line ?? 0) + 1,
    endColumn: (range?.end?.character ?? 0) + 1,
  };
}

/**
 * Normalize an LSP textDocument/definition result into a Monaco-acceptable
 * Location | LocationLink[] | null.
 *
 * LSP returns one of three shapes:
 *  - Location {uri, range}
 *  - Location[] (array)
 *  - LocationLink[] {originSelectionRange?, targetUri, targetRange, targetSelectionRange}
 */
function toMonacoDefinition(result) {
  if (!result) return null;
  const items = Array.isArray(result) ? result : [result];
  if (items.length === 0) return null;
  // If any LocationLinks (with targetUri) are present, treat the whole result as LocationLink
  const isLink = items.some((it) => it && it.targetUri);
  if (isLink) {
    return items
      .filter((it) => it && it.targetUri)
      .map((it) => ({
        uri: monaco.Uri.parse(it.targetUri),
        range: toMonacoRange(it.targetRange),
        originSelectionRange: it.originSelectionRange
          ? toMonacoRange(it.originSelectionRange)
          : undefined,
        targetSelectionRange: it.targetSelectionRange
          ? toMonacoRange(it.targetSelectionRange)
          : undefined,
      }));
  }
  return items
    .filter((it) => it && it.uri)
    .map((it) => ({
      uri: monaco.Uri.parse(it.uri),
      range: toMonacoRange(it.range),
    }));
}

/**
 * Normalize an LSP textDocument/formatting TextEdit[] into Monaco TextEdit[].
 * LSP TextEdit: {range, newText}; Monaco TextEdit: {range: IRange, text}.
 */
function toMonacoTextEdits(result) {
  if (!Array.isArray(result)) return [];
  return result
    .filter((it) => it && it.range)
    .map((it) => ({ range: toMonacoRange(it.range), text: it.newText ?? "" }));
}

/**
 * Ensure a usable LSP session exists and hook the specified model into sync.
 *
 * @param {object} params
 * @param {object} params.spec Language server manifest
 * @param {string} params.workspaceRoot workspace root directory
 * @param {object} params.model Monaco ITextModel
 * @param {object} params.deps Dependency injection (getGatewayAddress/getWebSocketProtocol/buildWebSocketProtocols)
 * @returns {Promise<boolean>} Whether the hookup succeeded
 */
export async function ensureClient({ spec, workspaceRoot, model, deps }) {
  if (!spec || !spec.id || !model) return false;

  const key = sessionKey(spec.id, workspaceRoot);
  let entry = sessions.get(key);

  if (!entry || entry.socket.readyState !== WebSocket.OPEN) {
    try {
      const client = await connectLspClient({ spec, workspaceRoot, deps });
      entry = {
        client,
        socket: client.socket,
        spec,
        root: workspaceRoot,
        models: new Set(),
        subs: new Map(),
      };
      sessions.set(key, entry);
      client.socket.addEventListener("close", () => {
        if (sessions.get(key) === entry) sessions.delete(key);
        // The socket closed unexpectedly: unbind all models of this session to avoid subscription and timer leaks
        releaseEntry(entry);
      });
    } catch (error) {
      console.warn(
        `[lsp] Language server "${spec.id}" is unavailable; degraded to syntax highlighting only.` +
          (spec.installHint ? `  Install hint: ${spec.installHint}` : ""),
        error?.message || error,
      );
      return false;
    }
  }

  // Skip if already hooked up
  if (entry.models.has(model)) return true;

  // didOpen
  entry.client.notify("textDocument/didOpen", {
    textDocument: {
      uri: model.uri.toString(true),
      languageId: model.getLanguageId(),
      version: model.getVersionId(),
      text: model.getValue(),
    },
  });
  entry.models.add(model);

  // Content changes → didChange (debounced)
  const changeSub = model.onDidChangeContent(() => {
    scheduleDidChange(entry.client, model);
  });
  // Model disposal → didClose and unbind
  const disposeSub = model.onWillDispose(() => {
    entry.client.notify("textDocument/didClose", {
      textDocument: { uri: model.uri.toString(true) },
    });
    unbindModel(entry, model);
  });
  entry.subs.set(model, { changeSub, disposeSub });

  return true;
}

/**
 * Unbind a single model from a session: cancel pending timers and release subscription handles.
 * Does not send didClose (the caller decides whether it is needed).
 */
function unbindModel(entry, model) {
  const pending = changeTimers.get(model);
  if (pending) {
    clearTimeout(pending);
    changeTimers.delete(model);
  }
  const handles = entry.subs.get(model);
  if (handles) {
    entry.subs.delete(model);
    try {
      handles.changeSub.dispose();
    } catch {
      /* ignore */
    }
    try {
      handles.disposeSub.dispose();
    } catch {
      /* ignore */
    }
  }
  entry.models.delete(model);
}

/**
 * Release all resources of a session entry: cancel the subscriptions and timers of all models in the session.
 * Idempotent; can be called repeatedly.
 */
function releaseEntry(entry) {
  if (!entry) return;
  for (const model of Array.from(entry.models)) {
    unbindModel(entry, model);
  }
  entry.models.clear();
  entry.subs.clear();
}

/** Debounce map: model -> timer */
const changeTimers = new Map();

function scheduleDidChange(client, model) {
  const existing = changeTimers.get(model);
  if (existing) clearTimeout(existing);
  const timer = setTimeout(() => {
    changeTimers.delete(model);
    client.notify("textDocument/didChange", {
      textDocument: {
        uri: model.uri.toString(true),
        version: model.getVersionId(),
      },
      contentChanges: [{ text: model.getValue() }],
    });
  }, 300);
  changeTimers.set(model, timer);
}

/**
 * Release the connection of a specific server.
 * @param {string} serverId
 * @param {string} root
 */
export function disposeClient(serverId, root) {
  const key = sessionKey(serverId, root);
  const entry = sessions.get(key);
  if (!entry) return;
  sessions.delete(key);
  releaseEntry(entry);
  try {
    entry.client.close();
  } catch {
    /* ignore */
  }
}

/** Release all connections (called when the component is unmounted). */
export function disposeAll() {
  for (const [key, entry] of sessions.entries()) {
    releaseEntry(entry);
    try {
      entry.client.close();
    } catch {
      /* ignore */
    }
    sessions.delete(key);
  }
  registeredProviders.clear();
  for (const timer of changeTimers.values()) clearTimeout(timer);
  changeTimers.clear();
}

/** The current number of active connections, for debugging. */
export function getActiveClientCount() {
  return sessions.size;
}

/**
 * Issue a textDocument/definition request for the given model, returning the raw LSP result.
 *
 * Used for custom Ctrl+F12 navigation: Monaco's built-in revealDefinition can only jump to
 * already loaded models and cannot automatically open an unopened target file, so the frontend
 * grabs the target uri + range and opens and positions the file itself.
 *
 * @param {object} model Monaco ITextModel
 * @param {{lineNumber: number, column: number}} position Monaco 1-based cursor position
 * @returns {Promise<object|null>} LSP Location | LocationLink[] | Location[] | null
 */
export async function getDefinition(model, position) {
  if (!model || !position) return null;
  const uri = String(model.uri.toString(true)).toLowerCase();
  for (const entry of sessions.values()) {
    let found = false;
    for (const m of entry.models) {
      if (String(m.uri.toString(true)).toLowerCase() === uri) {
        found = true;
        break;
      }
    }
    if (!found) continue;
    try {
      return await entry.client.request("textDocument/definition", {
        textDocument: { uri: model.uri.toString(true) },
        position: {
          line: (position.lineNumber ?? 1) - 1,
          character: (position.column ?? 1) - 1,
        },
      });
    } catch {
      return null;
    }
  }
  return null;
}
