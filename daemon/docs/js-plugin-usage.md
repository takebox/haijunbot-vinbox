# HaijunBot JS Plugin System Usage Guide

HaijunBot daemon has a built-in JS runtime (based on [goja](https://github.com/dop251/goja), pure Go, zero cgo),
You can write JS scripts to call the daemon's capabilities for local automation, such as reading system info, operating on files,
executing commands, managing processes, etc.

## 1. Quick Start

```bash
# Run the example script
haijunbot-daemon run-script examples/system-info.js

# Run the script and pass arguments (inject haijunbot.args)
haijunbot-daemon run-script examples/list-dir.js --arg path=/tmp
```

Within scripts, capabilities are called through the global object `haijunbot`; `print()` / `console.log()` output to stdout,
`console.error()` outputs to stderr, and the script's top-level return value is printed to stdout.

## 2. haijunbot API

Global objects available within scripts:

| API                               | Description                                                              |
| --------------------------------- | ----------------------------------------------------------------- |
| `haijunbot.cap(name, params)`        | General call entry, calls by capability name, returns `{success, data, error}`         |
| `haijunbot.caps.<domain>.<action>(params)` | Nested namespace call, returns `data` on success, throws a JS exception on failure (can try/catch) |
| `haijunbot.listCaps()`               | List all capabilities available on the current platform (name/description/parameters/platform)                   |
| `haijunbot.sleep(ms)`                | Synchronous delay (milliseconds), replaces `setTimeout` (goja has no macrotask event loop)      |
| `haijunbot.args`                     | Script argument object (injected by `--arg key=value`)                         |

### 2.1 haijunbot.cap general call

```js
const res = haijunbot.cap("linux.system.info", {});
if (res.success) {
  print("hostname:", res.data.hostname);
} else {
  console.error("failed:", res.error);
}
```

`haijunbot.cap` always returns `{success, data, error}` and does not throw, suitable for scenarios needing explicit success/failure checks.

### 2.2 haijunbot.caps nested namespace

```js
// Equivalent to haijunbot.cap("linux.fs.list", {path: "/tmp"}), but throws on failure
try {
  const files = haijunbot.caps.linux.fs.list({ path: "/tmp" });
  print("total", files.count, "entries");
} catch (e) {
  console.error("call failed:", e.message);
}
```

Capability names are split by `.` into nested objects: `linux.fs.read` → `haijunbot.caps.linux.fs.read`.

### 2.3 Viewing the capability list

```js
const caps = haijunbot.listCaps();
caps.forEach((c) => print(c.name, "-", c.description));
```

### 2.4 Script arguments

```bash
haijunbot-daemon run-script my-script.js --arg name=world --arg count=3
```

```js
print("hello", haijunbot.args.name); // hello world
```

## 3. Example Scripts

`examples/` directory:

- `system-info.js` — read system info (demonstrates the two calling styles `haijunbot.cap` and `haijunbot.caps`)
- `list-dir.js` — list directory contents (demonstrates `haijunbot.args` parameter injection and iterating over a returned array)

## 4. Capability List

Available capabilities vary by platform (Linux / Windows); use `haijunbot.listCaps()` or
`haijunbot-daemon run-script` to execute the script below to view them:

```js
haijunbot.listCaps().forEach((c) => print(c.name));
```

Common capability domains (using Linux as an example):

- `linux.system.info` — system info
- `linux.fs.read` / `linux.fs.write` / `linux.fs.list` — file read/write and directory listing
- `linux.script.exec` — execute shell commands
- `linux.process.list` / `linux.process.kill` — process management
- `linux.clipboard` / `linux.input` / `linux.window` — clipboard / input / window
- `linux.screenshot` / `ocr.recognize` — screenshot and OCR
- `browser.ext.*` — browser extension management
- `fs.transfer.push` / `fs.transfer.pull` — cross-machine direct file transfer

## 5. Error Handling

- **Syntax error**: the script cannot compile; `run-script` outputs a SyntaxError with a non-zero exit code.
- **Runtime error**: the script throws an exception; outputs the error message + JS stack (file/line number), with a non-zero exit code.
- **Capability call failure**: `haijunbot.cap` returns `{success:false, error}`; `haijunbot.caps` throws and can be caught with try/catch.

## 6. Security Notes

> ⚠️ **Script permissions are equivalent to daemon permissions**.

JS scripts run with the permissions of the daemon process and can invoke **all** registered capabilities (equivalent to shell script permissions).
This plugin system is positioned as a "local automation tool" and does **no sandbox isolation** in the first version. Please do not run scripts of unknown origin,
and do not hardcode sensitive credentials in scripts.

`haijunbot.args` comes only from CLI `--arg` or the `args` of the script management capability; capability parameters come from the script itself;
there is no network input and no XSS injection surface.

## 7. Limitations

- The goja core has no `setTimeout` / `setInterval` macrotask event loop; for delays use `haijunbot.sleep(ms)`.
- `require` / `import` are not available within scripts (no module loader); scripts are single-file.
- ES modules (`import`/`export`) are not supported; use ordinary JS syntax.
