# Using Shortcuts for Quick Operations

## Use Cases

When you frequently switch panels, operate Agents, open the editor, or manage nodes in the Web UI, shortcuts are faster than mouse clicks. This page summarizes two kinds of shortcuts:

- **Space Leader sequences**: press Space and then type two letters in order to trigger the corresponding action; suitable for high-frequency operations.
- **Standard two-key shortcuts**: similar to VS Code's `Ctrl+P`, `Ctrl+S`, etc.; suitable for quickly opening panels or the editor.

## Steps

### Using Space Leader Sequences

1. Press the Space key (`Space`) once on the page to enter "Leader mode".
2. Then type the two letters, a "domain key" followed by an "action key".
3. Once matched, the page executes the corresponding action and exits Leader mode automatically.

For example, press `Space` → `a` → `f` to refresh the Agent list.

> Note: Space Leader sequences use single unmodified letters to avoid conflicts with combos intercepted by the system or the browser. When an input box, editor, or terminal has focus, the Space key does not enter Leader mode.

### Domain Key Overview

| Domain key | Meaning   | Covered content                     |
| ---------- | --------- | ----------------------------------- |
| `p`        | Panel     | Close panels, split windows         |
| `a`        | Agent     | View/operate the current Agent      |
| `v`        | View      | Open panels, editor, search         |
| `n`        | New       | Create an Agent, create a terminal  |
| `m`        | Manage    | Manage groups, panels, docs, restart nodes/gateway |

### Panel (`Space p`)

| Action key | Function            |
| ---------- | ------------------- |
| `x`        | Close the current panel |
| `s`        | Split left/right    |
| `h`        | Split top/bottom    |

### Agent (`Space a`)

| Action key | Function                          |
| ---------- | --------------------------------- |
| `d`        | View changes                      |
| `r`        | View rules                        |
| `t`        | View tools                        |
| `i`        | Intervene                         |
| `k`        | Interrupt                         |
| `o`        | Hide/show output                  |
| `v`        | Auto-read aloud                   |
| `s`        | Auto-scroll                       |
| `c`        | Copy                              |
| `e`        | Permission management             |
| `g`        | Lossless regeneration             |
| `x`        | Exit non-interactive mode         |
| `n`        | Rename                            |
| `y`        | Sync status                       |
| `f`        | Refresh the Agent list            |
| `w`        | Go to the Agent waiting for input |
| `z`        | Delete the current Agent          |

### View (`Space v`)

| Action key | Function                       |
| ---------- | ------------------------------ |
| `a`        | Open the Agent list            |
| `g`        | Open the Git view              |
| `e`        | Open the workspace             |
| `t`        | Open/close the terminal        |
| `c`        | Open/close the chat            |
| `s`        | Open settings                  |
| `u`        | Open the network topology      |
| `p`        | Open the command palette       |
| `l`        | Open the Agent list (command palette) |
| `f`        | File search                    |
| `r`        | Open the directory tree        |
| `b`        | Content search                 |
| `n`        | File name search               |
| `w`        | Save the current file          |
| `d`        | Ask the Agent to analyze the selected code |
| `o`        | Hide/show the pet              |

### New (`Space n`)

| Action key | Function              |
| ---------- | --------------------- |
| `a`        | Create a new Agent    |
| `q`        | Create with one sentence |
| `t`        | Create a terminal     |

### Manage (`Space m`)

| Action key | Function              |
| ---------- | --------------------- |
| `g`        | Manage groups         |
| `a`        | Open the management panel |
| `h`        | Open the user documentation |
| `r`        | Restart all nodes     |
| `q`        | Restart the gateway   |

### Standard Two-Key Shortcuts

| Shortcut                    | Function                               |
| --------------------------- | -------------------------------------- |
| `Ctrl/Cmd + P`              | Open the command palette               |
| `Ctrl/Cmd + A`              | Open the command palette and show the Agent list |
| `Ctrl/Cmd + F`              | Open the command palette and enter file search |
| `Ctrl/Cmd + L`              | Open the command palette and show the Agent list |
| `Ctrl/Cmd + N`              | Create an Agent                        |
| `Ctrl/Cmd + E`              | Open/hide the editor panel             |
| `Ctrl/Cmd + S`              | Save the current editor tab            |
| `Ctrl/Cmd + Shift + F`      | Editor content search                  |
| `Ctrl/Cmd + Shift + P`      | Editor file name search                |
| `Ctrl/Cmd + Shift + E`      | Editor directory tree                  |
| `Ctrl + \``                 | Open/hide the terminal panel           |
| `Ctrl/Cmd + \`              | Split the current panel left/right     |
| `Ctrl/Cmd + -`              | Split the current panel top/bottom     |
| `Ctrl/Cmd + W`              | Close the current focused panel        |
| `Ctrl + Alt + Enter`        | Send buffer content                    |
| `F2`                        | Rename the current Agent (or the selected node) |
| `Delete`                    | Delete the selected Agent in the pet hall (requires confirmation) |
| `Ctrl + Alt + Arrow keys`   | Select an Agent by direction in the hall, or switch the focused area |
| `Ctrl + Alt + Shift + Arrow keys` | Select a node by direction in the hall |
| `Esc`                       | Close the current dialog or exit Leader mode |

## Feedback You Will See

- After pressing Space to enter Leader mode, the page shows the available actions for the current domain so you can see the keys.
- After matching an action, the page executes it and exits Leader mode.
- Some actions have prerequisites, e.g. "Delete the current Agent" requires a selected Agent, and "Restart all nodes" requires administrator permission; if the condition is not met, the action does nothing.
- Dangerous operations (such as deleting an Agent, restarting all nodes, or restarting the gateway) show a confirmation prompt and require you to confirm again before running.

## Notes

- Space Leader sequences do not trigger when an input box, the online editor, or the terminal has focus, so normal input is not affected.
- `Ctrl/Cmd + P`, `Ctrl/Cmd + A`, and `Ctrl/Cmd + F` yield to the editor's native behavior (such as find or select all) when the editor or input box has focus, so they do not interrupt your editing.
- Standard two-key shortcuts follow what the page actually does; if your environment has system-level shortcut interception, some combos may not trigger, and you can switch to Space Leader sequences instead.
- The shortcut list on this page matches the current version; if a later version changes the keys, follow the shortcuts shown in the page's command palette.
