---
name: haijunbot_daemon_windows
description: Triggered when there is a need to operate desktop programs on the user's real Windows machine through the windows.* capabilities of haijunbot-daemon. Triggered whenever the user mentions "operate Windows programs", "control desktop apps", "windows.window", "windows.input", "daemon capabilities", "real machine automation", "click a window", or "type text into an app". Not triggered: using the hw/haijunbot-windows CLI (pywinauto) (use haijunbot_windows_cli); Linux/macOS desktop operations; only executing command-line scripts without touching GUI; web page automation (use haijunbot_browser_cli or browser_ext_usage).
---

# haijunbot-daemon Windows Capability Operation Guide

## Rule Introduction

`haijunbot-daemon` is a resident daemon running on the user's real machine. It exposes `windows.*` capabilities through the `daemon` tool, and can start/operate desktop programs, simulate mouse and keyboard input, read/write files and the clipboard, and execute PowerShell scripts on **the user's own Windows machine**.

It and `hw` (haijunbot-windows, a Python CLI based on pywinauto) are **two independent paths**:

- `daemon`: a Go-implemented daemon; capabilities are invoked through the `daemon` tool, **does not depend on pywinauto**, and can operate the real machine (including the desktop session the user has logged into).
- `hw`: a Python CLI that needs to run commands directly on Windows.

**Use `daemon` whenever possible instead of `hw`** (daemon is real-machine oriented, requires no extra installation, and has fuller capabilities).

## Principles You Must Follow

### 1. Discover first, then invoke

**Must**:

- Before any operation, first call `daemon(action="list_sessions")` to get the `session_id` (required for all calls except `list_sessions`).
- Call `daemon(action="list_capabilities", session_id=...)` to confirm **which capabilities and their parameters are actually registered** on the target machine -- the capability list differs by platform/version.
- **Forbidden**: directly calling an unconfirmed capability name or parameter based on guesswork.

**Example:**

```text
daemon(action="list_sessions")
daemon(action="list_capabilities", session_id="<sid>")
daemon(action="call", session_id="<sid>", name="windows.window.list", params={})
```

### 2. You are operating the user's real machine; be cautious with write operations

**Must**:

- Clearly inform the user of the write operations to be performed (click, type, start/stop a program, change the clipboard, write files).
- For high-risk operations (closing a window, killing a process, writing system files, changing services), explain the intent before executing.

**Forbidden**:

- Killing a user process or closing a user window without confirmation.
- Leaving temporary files on the user's machine -- **must be cleaned up when the task ends** (see section 6 of "Operations You Must Perform").

### 3. Verify with facts, do not guess the UI state

**Must**:

- After each operation, verify the result with observable means (window title, window list, clipboard content, process state, OCR text).
- When verification is impossible, honestly state "unverified"; **forbidden** to claim it is done.

**Forbidden**:

- Assuming "it should take effect after clicking" without double-checking.
- Equating "the tool returned success" with "the business goal was achieved".

### 4. Platform-specific conventions

**Must**:

- Capability names carry a platform prefix (`windows.*`); confirm the platform matches before calling.
- Capabilities involving a graphical environment (GUI class) fail without a desktop session; you must first confirm a usable desktop exists.

## Operations You Must Perform

### 1. Establish the session and capability list

```text
# 1) Get the session_id (contains system_info: hostname/os/user/exe_path/commit)
daemon(action="list_sessions")

# 2) See which capabilities and parameters this machine has
daemon(action="list_capabilities", session_id="<sid>")
```

From `list_sessions`'s `system_info`, confirm: hostname, OS version, current user, and whether it is an administrator (`isAdmin` must be checked separately).

### 2. Choose a capability by task

| Goal                              | Capability                                              | Key parameters                                                                       |
| --------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| List windows (get window_id/pid/title) | `windows.window.list`                                    | `filter` (**matches title, not process name**)                                       |
| Focus a window                   | `windows.window.focus`                                   | `window_id` (**a hexadecimal HWND string**) or `title`                               |
| Close a window                   | `windows.window.close`                                   | `window_id`                                                                           |
| Click                             | `windows.input.click`                                    | `x`/`y` (**absolute screen coordinates**), `button`, `count`                         |
| Double-click / right-click / hover | `windows.input.double-click` / `.right-click` / `.hover` | `x`/`y`, `button` (double-click/right-click), `delay_ms`                              |
| Drag                              | `windows.input.drag`                                     | `from_x`/`from_y`/`to_x`/`to_y`, `button`, `steps` (default 20)                       |
| Key combinations                  | `windows.input.keys`                                     | `keys` (e.g., `ctrl+f`, `Return`, `ctrl+alt+Right`)                                   |
| Type text                         | `windows.input.type`                                     | `text`, `delay_ms`                                                                    |
| Clipboard read/write              | `windows.clipboard.get` / `.set`                         | `text`                                                                                |
| Run PowerShell/cmd                | `windows.script.exec`                                    | `script`, `interpreter`, `timeout_ms`                                                 |
| List processes                    | `windows.process.list`                                   | `filter` (matches process name or PID)                                                |
| Kill a process                    | `windows.process.kill`                                   | `pid`, `force`                                                                        |
| List installed apps               | `windows.app.list`                                       | `filter` (name or publisher)                                                          |
| Start an app                      | `windows.app.start`                                      | `path` (absolute path of the executable), `args`, `wait`                              |
| File read/write/list              | `windows.fs.read` / `.write` / `.list`                   | `path`, etc.                                                                          |
| Cross-machine file transfer (daemon to node) | `fs.transfer.push` / `fs.transfer.pull`                  | `gateway`, `node_id`, `local_path`, `remote_path` (see the `daemon_file_transfer` rule) |
| Service management                | `windows.service.*`                                      | `unit` (requires administrator privileges to start/stop)                              |
| Screenshot                        | `windows.screenshot`                                     | `path` (**only captures the primary screen; the return body does not contain the image**) |
| System information                | `windows.system.info`                                    | none                                                                                  |
| Enumerate the control tree        | `windows.ui.tree`                                        | `window_id`/`title`, `max_depth` (default 10), `max_controls` (default 200)           |
| Operate menu items                | `windows.ui.menu`                                        | `window_id`/`title`, `path` (e.g., `File->Open`)                                      |
| System configuration              | `windows.config.*`                                       | theme / power plan / proxy / screen timeout / remote desktop / startup (see below)    |

### 3. File read/write and cross-machine transfer

For **local read/write** use `windows.fs.read` / `.write` / `.list`:

- `windows.fs.read`: reads file content, single-call limit 8 MiB; binary is automatically base64 (`is_binary=true`).
- `windows.fs.write`: writes a file, supports overwrite/append and automatic parent directory creation; when `encoding=base64`, decodes and writes as base64.
- `windows.fs.list`: lists a directory, supports recursion and depth limits.

> These three capabilities are for "viewing content / writing small files" and are **unsuitable for moving large files** (the content must pass through the Agent's context).

For **cross-machine file transfer** use `fs.transfer.push` / `fs.transfer.pull` (common to Linux/Windows, no platform prefix):

- The data path is **daemon ↔ agent node** (`/api/node/{node_id}/file-transfer/*`); the `node_id` must be an agent node registered with the gateway, **not the daemon's client_id**.
- Transferring files between daemon and daemon requires a relay through the agent node (source machine push → target machine pull).
- Single-call limit 512 MiB; `chunk_size` is limited by the gateway nginx 1 MB body limit, so **you must explicitly pass 524288**.

Full usage, parameters, and all known pitfalls (502 / 413 / credentials / timeout) are in the **`daemon_file_transfer` rule**; not repeated here.

### 4. Locating UI elements (core methodology)

Degrade through the following order -- do not blindly click coordinates from the start.

#### ① Use `windows.ui.tree` to enumerate the control tree (first choice)

Directly call the `windows.ui.tree` capability (internally uses .NET UIAutomation, no handwritten PowerShell needed):

```text
daemon(action="call", session_id="<sid>", name="windows.ui.tree",
       params={"window_id": "0x003A0BB0", "max_depth": 10, "max_controls": 200})
```

Each control's `type`/`name`/`automation_id`/`rect` (including `depth`) is returned; use `depth` to restore the hierarchy. After getting the control's `Name`/`AutomationId`/`BoundingRectangle`, use `input.click` to click its center.

> If a handwritten UIA script is needed (e.g., custom filtering), refer to: `Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes` + `FromHandle([IntPtr]0xXXXX)` + `FindAll` (see the explanation in ② below).

#### ② CEF/Electron apps: UIA is ineffective; use Windows OCR instead

If UIA only returns 3~5 empty `Pane`s (`CefBrowserWindow` / `Chrome_WidgetWin_0` / `Chrome_RenderWidgetHostHWND`), it is **CEF/Chromium rendering**, and UIA cannot get the internal controls. In this case use the **system OCR** to perform text recognition on a window screenshot, obtaining "text + bounding box coordinates":

```powershell
# Prerequisite: the system has the Chinese OCR language pack installed; first check:
[Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages

# Screenshot the window region → WinRT OCR recognition → output each line of text and its coordinates
# Key point: WinRT async must be bridged with AsTask; force-cast the BoundingRect field to [double]
```

After getting the OCR line's `x/y/x2/y2` (**window-relative coordinates**), add the window origin to get screen coordinates, then use `input.click`.

#### ③ Coordinate probing (fallback)

When the first two are not feasible, verify whether an input box was hit using "click → type → Ctrl+A/Ctrl+C → read clipboard"; use window title/process state changes to judge whether an operation took effect. **Change only one variable at a time**; avoid multi-point rapid clicking.

### 5. System configuration and menu operations

`windows.config.*` is used to change system settings, and `windows.ui.menu` is used to operate an app's menu bar:

- **`windows.config.theme`**: switches between dark/light themes (modifies the registry `Personalize\AppsUseLightTheme`).
- **`windows.config.power-plan`**: switches the power plan (`powercfg /setactive`); pass the plan GUID as `plan_id`.
- **`windows.config.proxy`**: sets/clears the system proxy (`proxy` passes `http://host:port`, `enabled` controls the switch).
- **`windows.config.screen-timeout`**: screen timeout (minutes); `on_ac` specifies AC/battery.
- **`windows.config.remote-desktop`**: enables/disables remote desktop (modifies the registry `fDenyTSConnections`, requires an administrator).
- **`windows.config.startup`**: startup items (`name`+`path` to add/remove, the registry `Run` key).

`windows.ui.menu` expands the menu level by level by `path` (`File->Open` means first click `File`, then click `Open`; internally uses `ExpandCollapsePattern`/`InvokePattern`). Menu item paths are separated by `->`, and the segment names must match the actual menu text; if an item is not visible (e.g., a submenu not expanded), an error is returned; in that case expand the parent menu first and try again.

> These capabilities mostly require administrator privileges (`remote-desktop`/`startup`, etc.). On failure, first confirm whether the daemon runs as an administrator.

### 6. Verifying operation results

Common criteria:

- **Window title change**: many players/editors write the "current document/song" into the title, making it the most inexpensive criterion.
- **`windows.window.list`**: confirm that a window appears/disappears/its title changes (note that `filter` matches the **title**).
- **Clipboard**: after `input.type`, use `ctrl+a`/`ctrl+c` + `clipboard.get` to read back and verify whether the input really went into the target control.
- **Process**: `windows.process.list` confirms start/exit.
- **OCR**: take a new screenshot and OCR it to see whether the on-screen text matches expectations.

### 7. Cleaning up temporary artifacts

**Must**: delete all temporary files produced on the user's machine this time when the task ends (screenshots, scripts, temporary data).

```powershell
Remove-Item 'D:\haijunbot-*.png','D:\haijunbot-*.ps1' -Force -ErrorAction SilentlyContinue
```

## Practical Guidance

### Common pitfalls (all measured on real machines)

1. **Window title ≠ app name**: a player/browser title is the "current content"; for example, the NetEase Cloud Music title is the currently playing song name and does not contain "NetEase Cloud Music". Use `window.list` to list everything, then find by `pid` or title characteristics; **do not** use the app name to `filter`.
2. **`window_id` is an HWND, not a PID**: passing a PID reports "window does not exist". Use a hexadecimal string for the HWND (e.g., `0x003A0BB0`).
3. **`input.type` works for CEF**: it goes through `keybd_event` + Unicode scan codes and can correctly enter Chinese into Chromium apps. **But it must first click the real input box** -- otherwise the text goes somewhere else.
4. **Shortcuts may be intercepted by the app**: CEF apps often swallow system-level shortcuts such as `Ctrl+F`; **prefer "click the input box" over shortcuts**.
5. **Do not use "screenshot + trying to read the image" to locate the UI**: `windows.screenshot`'s return body contains no image content, and `fs.read` reading back base64 cannot be understood directly either. **A screenshot is only input for OCR**; do not expect to look at the image directly.
6. **UIA is ineffective for CEF**: see "Locating UI" ②.
7. **`Get-Process`'s `MainWindowTitle` gives only one main window**: with multiple windows, the app may return the wrong one (e.g., "SystemHint" instead of the player window). `windows.window.list` is more reliable.
8. **`$pid` is a read-only variable in PowerShell**: do not use `$pid` as a variable name when writing scripts.
9. **WinRT calls need AsTask bridging**: when calling WinRT APIs such as `Windows.Media.Ocr` from PowerShell, async operations must use the `AsTask` generic method + `.Wait()` to get the result.
10. **`service.start/stop/restart` requires an administrator**: it fails in a non-administrator session; this is an environment limitation, **do not mark it as "capability verified"**.
11. **`windows.app.list` only covers registry desktop apps** (not UWP); `screenshot` only captures the primary screen; `fs.*` has no path sandbox.

### Finding an app's install path

When `windows.app.list` cannot get the path, read the registry Uninstall entries:

```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
                 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
                 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' |
  Where-Object DisplayName -like '*keyword*' |
  Select-Object DisplayName,DisplayIcon,InstallLocation,UninstallString
```

## Self-Checklist

- [ ] Was `session_id` obtained via `list_sessions` first, and were capabilities confirmed via `list_capabilities`?
- [ ] Were UI elements located in the UIA → OCR → coordinate probing order, rather than blind clicking?
- [ ] After each operation, was the result verified with observable means (title/window list/clipboard/process/OCR)?
- [ ] Was the intent explained to the user before write operations?
- [ ] Were the temporary files produced on the user's machine this time cleaned up?
- [ ] Did the report honestly distinguish "verified" from "unverified" items?
