---
name: haijunbot_windows_cli
description: Triggered when there is a need for desktop program automation or GUI testing on the Windows platform. Triggered whenever the user mentions "Windows automation", "desktop program operations", "GUI testing", "pywinauto", or "window operations". Not triggered: Linux/Mac platform operations; web page automation (use browser_cli); command-line scripts that do not involve GUI.
---

# HaijunBot Windows CLI (hw) Usage Guide

## Overview

`hw` (or `haijunbot-windows`) is a pywinauto-based Windows desktop program automation command-line tool. It supports launching applications, connecting to existing windows, performing clicks, typing, screenshots, retrieving the control tree, listing windows, and modifying common system configurations (theme, power, proxy, etc.). **Supported on the Windows platform only**.

> **⚠️ Important reminder**
>
> 1. **Screenshot feature limitation**: unless the user explicitly requests it, do not use the `screenshot` command. Screenshots are mainly for debugging and validation purposes, not the default behavior.
> 2. **Output integrity**: every `hw` command returns a complete JSON result (including the `success`, `stdout`, `stderr` fields). **Under no circumstances are you allowed to filter, truncate, or modify the results of commands executed by hw in any form**; you must fully return the raw JSON output so the user can accurately determine whether the operation succeeded.

Connection information is persisted through `~/.haijunbot/jw_sessions.json`, and subsequent commands can reuse the saved session.

## Quick Start

```bash
# 1. launch Notepad
hw start --path notepad.exe

# 2. connect to the already running Notepad (if not started with start)
hw connect --title "Untitled - Notepad"

# 3. type text
hw type --text "Hello World"

# 4. take a screenshot
hw screenshot

# 5. close the session
hw close
```

## Common Parameters

Most commands support the following optional parameters:

- `--app-id TEXT`: application session ID (default: `default`)
- `--process TEXT`: process name or path (overrides the session)
- `--title TEXT`: window title (overrides the session, supports regex)
- `--pid INT`: process ID (overrides the session)
- `--backend TEXT`: pywinauto backend, `uia` (default) or `win32`

## Command List

### 1. Application Management

#### start - Launch an application

Launches an application and registers the session.

**Parameters:**

- `-p, --path TEXT`: executable file path (required)
- `-a, --args TEXT`: launch arguments
- `--app-id TEXT`: session ID (default: `default`)
- `--backend TEXT`: backend (default: `uia`)
- `-t, --timeout INT`: launch timeout in seconds (default: 30)

**Examples:**

```bash
hw start --path notepad.exe
hw start --path "C:\Program Files\app\app.exe" --args "C:\file.txt"
```

#### connect - Connect to a running window

Connects to a running window and saves the session.

**Parameters:**

- `--process TEXT`: process name or path, e.g. `notepad.exe`
- `-t, --title TEXT`: window title (supports regex matching)
- `--pid INT`: process ID
- `--app-id TEXT`: session ID (default: `default`)

At least one of `--process`, `--title`, or `--pid` is required.

**Examples:**

```bash
hw connect --process notepad.exe
hw connect --title "Untitled - Notepad"
hw connect --pid 12345
```

#### list - List sessions

Lists all registered application sessions.

**Parameters:**

- `--app-id TEXT`: filter by session ID

**Examples:**

```bash
hw list
```

#### list-windows - List windows

Lists the currently visible top-level windows, making it easy to choose a target for connect.

**Parameters:**

- `--backend TEXT`: uia (default) or win32
- `-t, --title TEXT`: filter by window title (substring matching)
- `-n, --limit INT`: maximum number to list (default 50)

**Examples:**

```bash
hw list-windows              # list all visible windows
hw list-windows --title Cursor   # filter windows whose title contains Cursor
```

Each returned item contains `title`, `pid`, `handle`, and can be used with `hw connect --pid <pid>` or `hw connect --title "<title>"`.

#### close - Close/disconnect a session

Disconnects an application session, optionally forcibly terminating the process.

**Parameters:**

- `--app-id TEXT`: session ID (default: `default`)
- `-k, --kill / --no-kill`: whether to terminate the process (default: kill). `--no-kill` only disconnects the session without terminating the process

**Examples:**

```bash
hw close            # close the session and terminate the process
hw close --no-kill  # only disconnect the session, the process keeps running
```

### 2. Mouse and Clicks

#### click - Click

Clicks a control or performs a menu selection.

**Parameters:**

- `-c, --control TEXT`: control title, AutomationId, or `title_regex=pattern`
- `-m, --menu TEXT`: menu path, e.g. `File(&F)->Open(&O)`
- `-i, --index INT`: index among controls of the same type (starting from 0)

**Examples:**

```bash
hw click --control "OK"
hw click --control "Edit"
hw click --menu "File(&F)->Save As(&A)"
```

#### double-click - Double click

Double-clicks a control.

**Parameters:**

- `-c, --control TEXT`: control identifier (required)
- `-i, --index INT`: control index

**Examples:**

```bash
hw double-click --control "File name"
```

#### right-click - Right click

Right-clicks a control or the window.

**Parameters:**

- `-c, --control TEXT`: control identifier (optional; if not specified, right-clicks the window)

**Examples:**

```bash
hw right-click
hw right-click --control "Edit area"
```

#### hover - Move the mouse

Moves the mouse to the center of a control or to specified screen coordinates.

**Parameters:**

- `-c, --control TEXT`: move to the center of the control
- `--x INT`: screen X coordinate (use either this or --control)
- `--y INT`: screen Y coordinate (use either this or --control)

**Examples:**

```bash
hw hover --control "OK"
hw hover --x 100 --y 200
```

#### drag - Drag

Drags the mouse from a start point to an end point.

**Parameters:**

- `--from-control TEXT`: start control
- `--from-x INT`, `--from-y INT`: start screen coordinates
- `--to-control TEXT`: target control
- `--to-x INT`, `--to-y INT`: target screen coordinates
- `-b, --button TEXT`: mouse button (default: `left`, optional `right`, `middle`)

**Examples:**

```bash
hw drag --from-control "Item 1" --to-control "Target area"
hw drag --to-x 200 --to-y 200
```

### 3. Keyboard Input

#### type - Type text

Types text into a control (clearing it first).

**Parameters:**

- `-t, --text TEXT`: the text to type (required)
- `-c, --control TEXT`: target control (optional; if not specified, uses the current focus)

**Examples:**

```bash
hw type --text "Hello World"
hw type --control "Edit" --text "content"
```

#### type-keys - Send a key sequence

Sends a keyboard key sequence, supporting pywinauto's `type_keys` syntax.

**Parameters:**

- `-k, --keys TEXT`: key sequence (required), e.g. `^a` (Ctrl+A), `{ENTER}`

**Examples:**

```bash
hw type-keys --keys "^a"
hw type-keys --keys "{ENTER}"
```

### 4. Screenshots and the Control Tree

#### screenshot - Take a screenshot

Captures a window screenshot.

**Parameters:**

- `-p, --path TEXT`: save path (optional; defaults to `~/.haijunbot/`)

**Examples:**

```bash
hw screenshot
hw screenshot --path C:\temp\capture.png
```

#### get-tree - Get the control tree

Gets the window control tree structure, used to generate selectors. The sequence number #N can be used with click/type's `--control #N` or `--index N`.

**Parameters:**

- `-d, --depth INT`: traversal depth (default: 99, the full tree)
- `-c, --control TEXT`: start from a specified control (optional), can be #N

**Examples:**

```bash
hw get-tree
hw get-tree --depth 5 --control "Panel"
```

#### menu - Execute a menu

Performs a menu selection.

**Parameters:**

- `-p, --path TEXT`: menu path (required), e.g. `File(&F)->Open(&O)`

**Examples:**

```bash
hw menu --path "Edit(&E)->Paste(&P)"
```

### 5. System Configuration (config)

Modifies common Windows system configurations (via PowerShell/registry, no pywinauto session required).

#### config theme - Theme switching

Switches the system/application dark or light theme.

```bash
hw config theme dark      # dark
hw config theme light     # light
hw config theme toggle    # toggle
```

#### config power-plan - Power plan

```bash
hw config power-plan list              # list power plans
hw config power-plan set --id <GUID>    # switch (the GUID is obtained from list)
```

#### config proxy - System proxy

```bash
hw config proxy get                    # view the current proxy
hw config proxy enable --server 127.0.0.1:7890
hw config proxy disable
hw config proxy set --server 127.0.0.1:8080 --bypass "localhost;127.*"
```

#### config screen-timeout - Screen timeout

```bash
hw config screen-timeout get
hw config screen-timeout set --minutes 10   # turn off the screen after 10 minutes; 0 means never
```

#### config remote-desktop - Remote desktop

Administrator privileges are required.

```bash
hw config remote-desktop get
hw config remote-desktop enable
hw config remote-desktop disable
```

#### config startup - Startup items

Manages the startup items in the current user's Startup folder (by renaming to add/remove the .disabled suffix).

```bash
hw config startup list
hw config startup disable --name "MyApp.lnk"
hw config startup enable --name "MyApp.lnk"
```

## Complete Usage Examples

### Notepad automation

```bash
# 1. launch Notepad
hw start --path notepad.exe

# 2. type text
hw type --text "Hello from HaijunBot"

# 3. save the file
hw menu --path "File(&F)->Save As(&A)"
hw type --control "Edit" --text "C:\\Users\\test\\demo.txt"
hw click --control "Save"

# 4. take a screenshot
hw screenshot --path C:\temp\notepad.png

# 5. close
hw close --kill
```

### Operating on an existing connected window

```bash
# 1. list the windows and find the target
hw list-windows --title Notepad

# 2. connect to the already open Notepad
hw connect --title "Untitled - Notepad"

# 3. view the control tree
hw get-tree

# 4. double-click the edit area (or use "--control #N" for the sequence number obtained from get-tree)
hw double-click --control "Edit"

# 5. select all and copy
hw type-keys --keys "^a"
hw type-keys --keys "^c"
```

### Modifying system configuration

```bash
# switch to dark mode
hw config theme dark

# set the screen to turn off after 10 minutes
hw config screen-timeout set --minutes 10

# enable the proxy
hw config proxy enable --server 127.0.0.1:7890

# list startup items
hw config startup list
```

## Best Practices

### 1. Use list-windows to find a window

When unsure which window to connect to, first list the visible windows:

```bash
hw list-windows              # list all
hw list-windows --title Cursor   # filter by title
```

Use the returned `title` or `pid` with `hw connect --title "..."` or `hw connect --pid <pid>`.

### 2. Use get-tree to locate controls

When the control identifier is unclear, first use `get-tree` to view the structure; the sequence number #N can be used with click/type:

```bash
hw connect --title "application title"
hw get-tree
```

### 3. Session persistence

After a successful `connect` or `start`, the session is saved to `~/.haijunbot/jw_sessions.json`, and subsequent commands can directly use `--app-id` without re-specifying `--process`/`--title`.

### 4. Control identification methods

- **Title text**: `--control "OK"`
- **AutomationId**: `--control "submitButton"`
- **Regex matching**: `--control "title_regex=.*Notepad.*"`
- **get-tree sequence number**: `--control "#5"` or `--index 5`

### 5. Error handling

All commands return JSON format:

```json
{
  "success": true,
  "stdout": "operation result",
  "stderr": ""
}
```

On failure, `success` is `false` and `stderr` contains the error description.

## Troubleshooting

### Non-Windows platform

**Error:** `haijunbot-windows (hw) requires Windows`

**Description:** This tool only supports Windows; please use it on Windows.

### pywinauto not installed

**Error:** `pywinauto not installed. Run: pip install pywinauto`

**Solution:**

```bash
pip install pywinauto
# or install HaijunBot (includes pywinauto)
pip install haijunbot-ai-assistant
```

### Window not found

**Error:** `Connect failed` or `Control not found`

**Solution:**

```bash
# 1. use list-windows to confirm the target window exists
hw list-windows
hw list-windows --title "partial title"

# 2. connect using the returned title or pid
hw connect --title "full or partial title"
hw connect --pid 12345

# 3. use get-tree to inspect the control structure
hw get-tree

# 4. try a different backend
hw connect --title "title" --backend win32
```

## Command Quick Reference

| Command                | Description                | Key parameters                        |
| ---------------------- | -------------------------- | ------------------------------------- |
| start                  | Launch an application      | --path (required), --args             |
| connect                | Connect to a window        | at least one of --process / --title / --pid |
| list                   | List sessions              | --app-id                              |
| list-windows           | List visible windows       | --title filter, --limit               |
| close                  | Close a session            | --app-id, --kill/--no-kill            |
| click                  | Click                      | --control, --menu, --index            |
| double-click           | Double click               | --control (required), --index         |
| right-click            | Right click                | --control                             |
| hover                  | Move the mouse             | --control or --x --y                  |
| drag                   | Drag                       | --from-control, --to-control or coordinates |
| type                   | Type text                  | --text (required), --control          |
| type-keys              | Send keys                  | --keys (required)                     |
| screenshot             | Take a screenshot          | --path                                |
| get-tree               | Get the control tree       | --depth (default 99), --control       |
| menu                   | Execute a menu             | --path (required)                     |
| config theme           | Theme switching            | dark / light / toggle                 |
| config power-plan      | Power plan                 | list / set --id                       |
| config proxy           | System proxy               | get / enable / disable / set          |
| config screen-timeout  | Screen timeout             | get / set --minutes                   |
| config remote-desktop  | Remote desktop             | enable / disable / get                |
| config startup         | Startup items              | list / enable / disable --name        |

## Related Documentation

- [pywinauto documentation](https://pywinauto.readthedocs.io/)
- [Windows App Tool specification]({{ haijunbot_src_dir }}/.haijunbot/spec/windows_app_tool_spec.md)
