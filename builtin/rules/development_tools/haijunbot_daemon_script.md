---
name: haijunbot_daemon_script
description: Triggered when there is a need to write, run, or debug JS scripts (background service scripts/daemon scripts/JS plugins) for haijunbot-daemon (the background service). Triggered whenever the user mentions "background service script", "daemon script", "run-script", "haijunbot.cap", "haijunbot.caps", "daemon JS plugin", or "local automation script". Not triggered: writing page scripts for the browser extension (use browser_ext_script); only using the daemon's windows.* capabilities to operate the desktop GUI (use haijunbot_daemon_windows); only writing ordinary Node/Python/Shell scripts (use script-generation).
---

# haijunbot-daemon Background Service Script Writing Specification

## Rule Overview

This rule governs the writing, running, and debugging of **JS scripts** (background service scripts) on the "haijunbot-daemon" background service.
haijunbot-daemon embeds a JS runtime based on [goja](https://github.com/dop251/goja) (pure Go, zero cgo).
Inside a script, the global object `haijunbot` is used to call the daemon's capabilities for local automation — reading system information, operating on files,
executing commands, managing processes, and so on. Scripts run with the daemon process's privileges, equivalent to shell script privileges.
Related source locations (with `{{ haijunbot_src_dir }}` as the HaijunBot source root):

- Runtime wrapper: `{{ haijunbot_src_dir }}/daemon/internal/jsruntime/runtime.go`
- Capability bridge: `{{ haijunbot_src_dir }}/daemon/internal/jsruntime/bridge.go`
- Subcommand entry point: `{{ haijunbot_src_dir }}/daemon/cmd/haijunbot-daemon/main.go` (`run-script`)
- Example scripts: `{{ haijunbot_src_dir }}/daemon/examples/system-info.js`, `list-dir.js`
- Usage documentation: `{{ haijunbot_src_dir }}/daemon/docs/js-plugin-usage.md`

## The Principles You Must Follow

### 1. Scripts are single-file pure JS with no module loader

**The requirements clarified:**

- **Must**: the script is a single `.js` file with normal JS syntax; goja has no module loader,
  so **you cannot** use `require` / `import` / `export`, and ES modules are not supported either.
- **Must**: access daemon capabilities through the global object `haijunbot` (see below).
- **Forbidden**: writing `import`/`export`/`require` in a script, or depending on any external module.
  **Example:**

```js
// read system information (the generic haijunbot.cap entry point)
const res = haijunbot.cap("linux.system.info", {});
if (res.success) {
  print("host name:", res.data.hostname);
  print("OS:", res.data.os_name, res.data.os_version, res.data.arch);
} else {
  console.error("failed to get system information:", res.error);
}
```

### 2. Use haijunbot.cap for explicit success/failure checks, use haijunbot.caps to throw exceptions

**The requirements clarified:**

- **Must**: `haijunbot.cap(name, params)` always returns `{success, data, error}` and **does not throw exceptions**,
  suitable for scenarios where the outcome needs to be explicitly checked.
- **Must**: `haijunbot.caps.<domain>.<action>(params)` returns `data` on success and **throws a JS exception on failure** (catchable with try/catch),
  suitable for scenarios where you want the execution to abort on failure.
- **Must**: capability names are split on `.` into nested objects — `linux.fs.read` → `haijunbot.caps.linux.fs.read`.
- **Forbidden**: mixing the success/failure semantics of the two (`haijunbot.caps` does not return `{success:false}` on failure; it throws an exception).
  **Example:**

```js
// method 1: haijunbot.cap returns an object, explicitly checked
const res = haijunbot.cap("linux.fs.list", { path: "/tmp" });
if (!res.success) {
  console.error("failed to list the directory:", res.error);
  throw new Error("directory listing failed: /tmp");
}
for (const entry of res.data.entries) {
  print(entry.is_dir ? "[D] " + entry.name : "    " + entry.name);
}
// method 2: haijunbot.caps nested calls, throwing on failure
try {
  const info = haijunbot.caps.linux.system.info({});
  print("CPU core count:", info.cpu_count);
} catch (e) {
  console.error("nested call failed:", e.message);
}
```

### 3. Use haijunbot.sleep for delays; setTimeout/setInterval are disabled

**The requirements clarified:**

- **Must**: goja has no macro-task event loop, so **there is no** `setTimeout` / `setInterval`;
  delays always use `haijunbot.sleep(ms)` (a synchronous blocking delay on the Go side).
- **Must**: if the top level of a script returns a Promise it will be awaited (async scripts are supported),
  but a Promise that does not resolve before the synchronous work completes (depending on macro tasks) will report an "unfinished Promise".
- **Forbidden**: writing `setTimeout`/`setInterval` in a script for delays or scheduling.
  **Example:**

```js
// wait 2 seconds before continuing (replaces setTimeout)
haijunbot.sleep(2000);
```

### 4. Scripts run with daemon privileges; write operations require caution

**The requirements clarified:**

- **Must**: scripts run with the daemon process's privileges and can call **all** registered capabilities (equivalent to shell privileges);
  the first version **does not do sandbox isolation** — do not run scripts of unknown origin.
- **Must**: **do not hardcode sensitive credentials** in scripts; `haijunbot.args` comes only from the CLI `--arg`, with no network input and no XSS injection surface.
- **Must**: for write operations (modifying files, killing processes, executing commands), state the intent first and clean up temporary files when the task is done.
- **Forbidden**: performing destructive operations (deleting files, terminating processes, modifying system configuration) without confirmation.

### 5. Capabilities vary by platform; call listCaps first

**The requirements clarified:**

- **Must**: available capabilities vary by platform (Linux sees `linux.*`, Windows sees `windows.*`, cross-platform sees `any.*`);
  `haijunbot.listCaps()` can be used before calling to confirm the capabilities actually available on the current platform.
- **Must**: capability names carry a platform prefix (such as `linux.fs.list`, `windows.script.exec`); confirm the platform matches before calling.
- **Forbidden**: calling unconfirmed capability names or parameters by guessing.
  **Example:**

```js
// list all available capabilities on the current platform
haijunbot.listCaps().forEach((c) => print(c.name, "-", c.description));
```

## The Operations You Must Execute

### Operation 1: Write a script

**Execution steps:**

1. First use `haijunbot.listCaps()` or run a probe script with `haijunbot-daemon run-script` to
   confirm the target capability name and parameters (the capability list differs across platforms/versions).
2. Write the script according to the API above: prefer `haijunbot.cap` for calls that need explicit success/failure checks,
   and use `haijunbot.caps` for calls that should abort on failure.
3. A non-`undefined` return value at the top level of a script is printed to stdout by `run-script` and can serve as the result output.
4. Use `node --check <file>` for a basic syntax check (goja has no standalone lint; this is the minimum guarantee).
   **Notes:**

- `print(...)` / `console.log()` output to stdout; `console.warn` / `console.error` output to stderr.
- Objects/arrays are serialized as JSON for output (similar to browser console behavior).
- Capability parameters are JS objects (automatically converted to `map[string]any`); passing `undefined`/`null` is treated as empty parameters.

### Operation 2: Run the script

**Execution steps:**

1. Use `haijunbot-daemon run-script <file.js>` to run a script file.
2. When parameterization is needed, use `--arg key=value` (repeatable); read `haijunbot.args.key` inside the script.
3. A non-`undefined` top-level return value is printed to stdout; errors go to stderr with the JS stack trace (file/line number).
   **Example:**

```bash
# run the example script
haijunbot-daemon run-script examples/system-info.js
# run a script with arguments (injecting haijunbot.args)
haijunbot-daemon run-script examples/list-dir.js --arg path=/tmp
```

**Notes:**

- Exit code: 0 on success; non-zero on script syntax errors/runtime errors/capability call failures.
- Inside a script, `haijunbot.args` is injected by `--arg key=value`; when absent it is an empty object and can be safely accessed.

### Operation 3: Debugging and verification

**Execution steps:**

1. Syntax error: `run-script` outputs a SyntaxError with a non-zero exit code; locate it by file/line number.
2. Runtime error: the script throws an exception; the error message plus a JS stack trace (file/line) is output with a non-zero exit code.
3. Capability call failure: `haijunbot.cap` returns `{success:false, error}`; `haijunbot.caps` throws an exception that can be caught with try/catch.
4. After a write operation, verify the result through an observable means (read back the file, check the process state, look at the command output); **do not** assume "it should have taken effect after the click".
   **Notes:**

- When a `haijunbot.caps` leaf-node call fails, the thrown exception's message contains the capability name and the error, and `e.message` is readable.
- Inside a script, `haijunbot.args` comes only from `--arg`, and capability parameters come from the script itself, with no network input and no XSS injection surface.

## Checklist

After completing the task, you must confirm:

- [ ] The script is a single-file pure JS with no `require`/`import`/`export`/ES modules
- [ ] Delays use `haijunbot.sleep(ms)`; `setTimeout`/`setInterval` were not used
- [ ] `haijunbot.listCaps()` was used to confirm the capability name and parameters before calling
- [ ] The success/failure semantics of `haijunbot.cap` and `haijunbot.caps` were used correctly
- [ ] Syntax was checked with `node --check`
- [ ] The script was actually run with `run-script` to confirm it is executable
- [ ] Write operations were verified as effective through an independent means, and temporary files were cleaned up
- [ ] No sensitive credentials were hardcoded in the script, and no scripts of unknown origin were run

## Related Resources

- daemon usage documentation: `{{ haijunbot_src_dir }}/daemon/docs/js-plugin-usage.md`
- daemon design document: `{{ haijunbot_src_dir }}/daemon/docs/js-plugin-design.md`
- Example scripts: `{{ haijunbot_src_dir }}/daemon/examples/system-info.js`, `list-dir.js`
- Windows desktop GUI operations: `{{ rule_file_dir }}/haijunbot_daemon_windows.md`
- Browser extension page scripts: `{{ rule_file_dir }}/browser_ext_script.md`
- General script generation specification: `{{ rule_file_dir }}/script-generation.md`
