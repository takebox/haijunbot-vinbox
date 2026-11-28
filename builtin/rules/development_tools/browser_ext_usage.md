---
name: browser_ext_usage
description: Triggered when there is a need to operate web pages in the user's local real browser. Triggered whenever the user mentions "browser_ext", "browser extension tool", "operate the user's browser", "reuse login state", "open a web page and click", or "real tab". Not triggered: merely starting a browser on the server side with hb/Playwright (use haijunbot_browser_cli); merely reading web page content (use read_webpage); merely viewing the list of available tools (use haijunbot_tool_usage).
---

# browser_ext Tool Usage Guide

## Rule Introduction

`browser_ext` drives the real, already-logged-in tabs in **the user's own browser** (through the HaijunBot Browser Bridge extension installed by the user);
it can reuse the login state and cookies, and is suitable for operating intranet sites that require login.
It complements `hb` (which starts a standalone browser via server-side Playwright): if you can use `browser_ext`, do not use `hb`.

**Core constraint**: each call can execute only one action; it operates on the user's real browser, and write operations may produce irreversible consequences.

## Principles You Must Follow

### 1. Create a Session First, Then Determine the Tab

**Clarification of requirements:**

- **Must**: before any operation, first call `list_sessions` to get a `session_id` (all actions except `list_sessions` require `session_id`).
- **Must**: when a specific page is needed, first call `list_tabs` to get a `tab_id`; when `tab_id` is not passed, most operations act on the **currently active tab**.
- **Forbidden**: guessing a `session_id` or `tab_id` out of thin air.

**Example:**

```text
browser_ext(action="list_sessions")
browser_ext(action="list_tabs", session_id="<sid>")
```

### 2. Prefer evaluate for Reading Values; Do Not Rely on the Return Value of execute_script

**Clarification of requirements:**

- **Must**: when a JS evaluation result is needed, use `evaluate` (going through CDP `Runtime.evaluate`, `returnByValue`),
  it is not restricted by the page's CSP, equivalent to typing an expression directly in the F12 Console.
- **Must**: `execute_script` is only used for "executing side effects"; its return value is **not passed through**, so do not use it to read values.
- **Forbidden**: using the return value of `execute_script` to make decisions.

### 3. Before Acting, First Inventory the Scripts Already Installed in the Extension

**Clarification of requirements:**

- **Must**: after receiving a browser operation task, **the first step** is to enumerate the scripts already installed in the extension, to see whether there is ready-made capability that can be directly reused.
  This is a shortcut to gaining "much stronger than raw DOM operations" capability: scripts run in the page's **main world** and can access the page's own JS objects
  (such as the site's built-in editor instance), and can bypass CSP, iframe isolation, and the fragility of coordinate clicking.
- **Must**: use `script_list` to get the script list (including `script_id`/`name`/`description`/`match`/`enabled`),
  then use `script_get` (passing `script_id`) to read the source code, and extract the **action names, desc, and params** exported by that script.
- **Must**: the script's `match` matches the target page URL and `enabled` is true for it to be usable; if it matches, prefer `script_run`,
  and do not repeatedly hand-roll the same logic with `click`/`type`/`evaluate`.
- **Forbidden**: directly hand-rolling low-level DOM operations without first inventorying the scripts; forbidden to guess actions by script name, you must base it on the `script_get` source code.

**Example:**

```text
browser_ext(action="script_list", session_id="<sid>")
browser_ext(action="script_get", session_id="<sid>", script_id="s-xxxxxxxx")
browser_ext(action="script_run", session_id="<sid>", script_id="s-xxxxxxxx", script_action="getEditor", script_args={}, tab_id=123)
```

> Alternative: if the tool is unavailable, you can also go directly through the gateway HTTP: `POST {master_url}/api/browser-ext/command`,
> body `{ session_id, action:"script.list"|"script.get"|"script.run", params, timeout }`,
> header `Authorization: Bearer $HAIJUNBOT_AUTH_TOKEN` (inside `script.run`'s `params` is `{id, action, args, tab_id}`).
> ⚠️ `{master_url}` must be **the master address reachable from the node where the Agent runs**, do **not** hardcode `127.0.0.1:8000`——
> when the Agent runs on a sub-node, `127.0.0.1` is the sub-node's local address, not the master, and it will fail to connect.
> You can use `gateway_manager(action="get_master_url")` to query the master address actually used by the current node.
> Prefer the `browser_ext` tool action above, since it already uses the correct master address internally.

### 4. Confirm the Target Before Write Operations

**Clarification of requirements:**

- **Must**: before clicking/typing, first use `query`, `get_text`, or `evaluate` to confirm the target element exists and its content is as expected.
- **Must**: for irreversible operations such as submit, delete, and send, first explain to the user what is about to be done.
- **Forbidden**: clearing content with coarse-grained operations like "select all + delete"; forbidden to blindly batch-click.

### 5. High-sensitivity actions must explicitly obtain user authorization

**Clarification of requirements:**

- **Must**: the following high-sensitivity actions must, before being called, **each time** explain to the user "what will be done, the scope of impact, and whether it is reversible", and only be executed after obtaining explicit consent:
  `cookie_get`/`cookie_get_all`/`cookie_set`/`cookie_remove`, `netrule_register`/`netrule_unregister`,
  `extmgr_set_enabled`/`extmgr_uninstall`, `native_send`, `proxy_set_settings`/`proxy_clear_settings`,
  `privacy_set`, `browsingdata_remove`, `contentsettings_set`/`contentsettings_clear`.
- **Must**: clearly inform the user of **irreversible** operations (`cookie_remove`, `netrule_unregister`, `extmgr_uninstall`,
  `browsingdata_remove`, `contentsettings_clear`, `history_remove`/`history_remove_range`,
  `bookmark_remove`/`bookmark_remove_tree`, `download_erase`, `script_uninstall`),
  and confirm before execution that the user has backed up or does not mind losing the data.
- **Must**: read-only high-sensitivity actions (`cookie_get`, `extmgr_list`, `proxy_get_settings`, `privacy_get`,
  `browsingdata_settings`) may be executed first to understand the current state, but the results may contain privacy data such as **login credentials, extension lists, and browsing traces**,
  and must not be written to logs, committed to repositories, or forwarded to third parties.
- **Forbidden**: calling any write-type high-sensitivity action without the user's explicit consent; forbidden to put high-sensitivity actions in a loop for batch execution.

### 6. Make Good Use of Waiting to Avoid Races

**Clarification of requirements:**

- **Must**: after a page navigation or asynchronous rendering, use `wait_for` to wait for the target element to appear before performing subsequent operations.
- **Must**: for long-running operations (such as network collection), explicitly increase `timeout`.
- **Forbidden**: directly clicking before the element has appeared and assuming success.

### 7. Clipboard Writes Require the Page to Be Truly Focused

**Clarification of requirements:**

- **Must**: `clipboard_write`/`clipboard_write_from_url` require the target page to **truly obtain focus**, otherwise `CLIPBOARD_WRITE_FAILED` is reported.
  When necessary, first use `activate_tab` to activate the tab, and use `click` to dispatch a real click to establish focus.
- **Must**: for `clipboard_write_from_url`'s `clipboard_url`, prefer passing the **complete absolute URL**;
  relative paths only support the `/uploads/` prefix (they will be completed with the connected gateway, and are error-prone in sub-node scenarios).

## Operations You Must Perform

### Operation 1: Standard Operating Procedure

**Execution steps:**

1. `list_sessions` → get `session_id` (an empty list means the extension is not connected, and the user needs to be prompted).
2. `script_list` → **first inventory the scripts already installed in the extension**, to see whether there is ready-made capability matching the current site/task (see "Operation 2").
3. `list_tabs` → get `tab_id`, confirm the target page is already open; if not open, use `navigate` or `new_tab`.
4. If there is a matching script, use `script_get` to read the source code to confirm the action and parameters, then call `script_run`; otherwise perform the target operation (`get_text`/`click`/`type`/`screenshot`, etc.).
5. Use read-only operations (`get_text`/`get_page_info`/`evaluate`, or the script's read-only actions) to verify the result.

**Notes:**

- `navigate` without `tab_id` will **create a new page**. By default (`new_window` is `true`) it will **prefer to create a new tab in a window that does not contain the HaijunBot frontend page**,
  so as not to mix the automated pages into the window the user is using to view HaijunBot; only when all windows contain the HaijunBot frontend page will a new window be opened.
  To open a new tab in the current window, pass `new_window=false`.
- When the page renders inside an iframe, the `selector` acts on the top-level document; you need to use `evaluate` to enter the iframe's `contentDocument` to operate.
- After changing the extension, you need to reload the extension at `edge://extensions/` for it to take effect.

### Operation 2: action Quick Reference

**Execution steps:** choose as needed, only one action each time.

#### Sessions and Tabs

| action                        | Required params       | Description                                       |
| ----------------------------- | --------------------- | ------------------------------------------------- |
| `list_sessions`               | None                  | List online sessions, returns a `session_id` list |
| `list_tabs`                   | `session_id`          | List tabs, returns `tab_id`/`url`/`title`         |
| `activate_tab`                | `session_id`,`tab_id` | Switch to the specified tab                       |
| `close_tab`                   | `session_id`,`tab_id` | Close the tab                                     |
| `new_tab`                     | `session_id`          | Create a new tab; optional `url`, `new_window` (default true) |
| `navigate`                    | `session_id`,`url`    | Navigate; optional `tab_id`, `new_window`         |
| `reload` / `back` / `forward` | `session_id`          | Reload / go back / go forward; optional `tab_id`  |

#### DOM Operations

| action               | Required params                     | Description                                                                |
| -------------------- | ----------------------------------- | -------------------------------------------------------------------------- |
| `get_text`           | `session_id`,`selector`             | Read element text                                                          |
| `get_html`           | `session_id`,`selector`             | Read element innerHTML                                                     |
| `query`              | `session_id`,`selector`             | Query element info; optional `all=true` returns all matches                |
| `click`              | `session_id`,`selector`             | Click the element                                                          |
| `type`               | `session_id`,`selector`,`text`      | Type text                                                                  |
| `hover`              | `session_id`,`selector`             | Hover                                                                      |
| `select`             | `session_id`,`selector`,`value`     | Select a dropdown option                                                   |
| `press_key`          | `session_id`,`key`                  | Press a key (e.g., Enter/Escape/Tab/ArrowDown); optional `selector` to focus first |
| `scroll`             | `session_id`                        | Scroll; `selector` scrolls to the element, or `x`/`y` pixel offset; optional `behavior` |
| `wait_for`           | `session_id`,`selector`             | Wait for an element; optional `state` (visible/hidden/attached, default visible), `timeout` |
| `upload_file`        | `session_id`,`selector`,`file_path` | Upload a local file (requires debugger permission)                         |
| `get_computed_style` | `session_id`,`selector`             | Computed style; optional `props` (array of kebab-case property names)      |

#### Information and Debugging (equivalent to the F12 panels)

| action                 | Required params           | Description                                                                          |
| ---------------------- | ------------------------- | ------------------------------------------------------------------------------------ |
| `get_page_info`        | `session_id`              | Basic page info (url/title/ready_state/viewport/scroll/document)                     |
| `get_console_logs`     | `session_id`              | console logs; optional `limit` (default 100), `clear`. The first call installs a hook, and the page needs to produce new logs |
| `evaluate`             | `session_id`,`expression` | Evaluate an arbitrary expression via CDP; optional `await_promise` (default true)    |
| `send_cdp_command`     | `session_id`,`method`     | Pass through an arbitrary CDP command; optional `cdp_params`                         |
| `get_network_requests` | `session_id`              | Collect network requests; optional `duration_ms` (default 3000), `limit`, `filter`. **Will block for the collection duration** |

#### Installed Scripts (Tampermonkey-like, prefer reuse)

The extension supports installing "user scripts", each script exporting several `action`s, executed in the page's **main world**, able to access the page's own JS objects.
**The capability is far stronger than raw DOM operations, so be sure to inventory them before acting.**

| action        | Required params                          | Description                                                                                 |
| ------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------- |
| `script_list` | `session_id`                             | List installed script metadata: `script_id`/`name`/`description`/`match`/`enabled`/`version` |
| `script_get`  | `session_id`,`script_id`                 | Read a single script (**including source code**, from which you learn what actions, params, and behaviors exist) |
| `script_run`  | `session_id`,`script_id`,`script_action` | Execute an action of the script in the target page's main world; optional `script_args` (object), `tab_id` (default current active page) |

**Notes:**

- `script_id` is in the form `s-xxxxxxxx`, **not the script name**; first use `script_list` to get the `script_id`, then `script_run`.
- In `script_run`: `script_action` is the **action name within the script** to execute (taken from the `script_get` source code),
  and `script_args` is the arguments object passed to it. Do not confuse these two with the tool's own `action` field.
- The script must have `enabled` as true, and the target page URL must match its `match`, otherwise `script_run` reports an error.
- The target page must be within the extension's host permissions, otherwise `PROTECTED_PAGE` is reported (such as `edge://`, unauthorized domains).
- The return value of a script action is passed through after JSON serialization (DOM/functions/circular references will be lost);
  write-type actions will really change the page/server-side data, so explain to the user before calling.
- Only when no script matches should you fall back to low-level operations such as `click`/`type`/`evaluate`.
- Installing/uninstalling/enabling/disabling/exporting scripts are already exposed as tool actions, see the "Script Management" table below;
  when lower-level control is needed, you can also go through the gateway HTTP: `POST {master_url}/api/browser-ext/command`, passing `script.install` etc. as `action` and the corresponding fields as `params`.
  Similarly, `{master_url}` must use the master address reachable from the node where the Agent runs, and must not hardcode `127.0.0.1:8000`,
  and can be queried with `gateway_manager(action="get_master_url")`.

#### Script Management (install/uninstall/enable/disable/export/gateway directory relay)

| action                    | Required params                            | Description                                                                                                             |
| ------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `script_install`          | `session_id`,`script_name`,`script_source` | Install a script; optional `script_description`/`script_match`/`script_version`. Same name overwrites and keeps the original `id` |
| `script_install_from_url` | `session_id`,`script_url`                  | Download and install a script from a URL; optional `script_name`/`script_description`/`script_match`/`script_version`. **Source code is not transmitted through the conversation** |
| `script_uninstall`        | `session_id`,`script_id`                   | Uninstall a script (**irreversible**, the source code is also lost, it is recommended to back up first with `script_export` or `script_save` before uninstalling) |
| `script_set_enabled`      | `session_id`,`script_id`,`script_enabled`  | Enable/disable a script                                                                                                  |
| `script_export`           | `session_id`,`script_id`                   | Export the script source code for backup or migration (**will return the source code verbatim to the Agent**, use with caution for large scripts) |
| `script_save`             | `session_id`,`script_id`                   | Save the script from the extension to the gateway data directory `{data_dir}/browser_scripts/`; optional `script_name` (saved file name). **Only returns the path and byte count** |
| `script_load_from_file`   | `session_id`,`script_name`                 | Read a script from the gateway data directory and install it into the extension; optional `script_description`/`script_match`/`script_version`. **Only returns the install metadata** |

**Avoid bringing the script text into the context (important)**:
`script_export` returns the script source code verbatim to the Agent, and a large script will quickly fill the context. **When backing up/migrating scripts, prefer
the `script_save` + `script_load_from_file` pair**: the former writes the source code to the gateway directory, and the latter reads it back from the directory and installs it,
both only return the path/metadata, and the source code never enters the conversation.

**Installing from a URL (`script_install_from_url`)**:

- The source code is downloaded by the extension background `fetch`, **without going through the conversation context**, suitable for hosting the script in any HTTP static directory and distributing it by URL.
- The gateway's `/uploads/` directory is already mounted as a static service (`{data_dir}/uploads` → `{master_url}/uploads/<file>`);
  putting a `.js` in that directory allows direct installation by URL (**only for gateways reachable from the public internet**, see below for the reason).
- **Security restrictions (SSRF protection)**: the extension side rejects non-http(s) protocols such as `file:`/`data:`,
  and rejects loopback and intranet addresses (`127.0.0.1`, `localhost`, `10.x`, `172.16-31.x`, `192.168.x`, `169.254.x`, `::1`, `fe80::`, etc.).
  Therefore **local/intranet gateways cannot be installed from a URL**; in that case use `script_save`/`script_load_from_file` instead (through the gateway API with a Token, not subject to this restriction).
- The script name can be automatically derived from the last segment of the URL (`.../my-script.js` → `my-script`); if it cannot be derived, `script_name` must be passed explicitly.

#### Clipboard

| action                     | Required params              | Description                                                                 |
| -------------------------- | ---------------------------- | --------------------------------------------------------------------------- |
| `clipboard_write`          | `session_id`                 | Write to the clipboard; choose one of `clipboard_text` or `clipboard_base64`. Requires the page to be truly focused |
| `clipboard_write_from_url` | `session_id`,`clipboard_url` | Fetch content from a URL and write it to the clipboard; optional `clipboard_mime`. Requires the page to be truly focused |

#### Bookmarks and History

| action                 | Required params               | Description                                                                                         |
| ---------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------- |
| `bookmark_list`        | `session_id`                  | List the bookmark tree; optional `bookmark_id` to specify a subtree                                 |
| `bookmark_search`      | `session_id`,`bookmark_query` | Search bookmarks by title/URL keyword                                                               |
| `bookmark_create`      | `session_id`,`url`            | Create a bookmark; optional `bookmark_title`, `bookmark_parent_id`, `bookmark_index`                |
| `bookmark_remove`      | `session_id`,`bookmark_id`    | Delete a single bookmark (**irreversible**)                                                         |
| `bookmark_remove_tree` | `session_id`,`bookmark_id`    | Delete a bookmark and its entire subtree (**irreversible**, will also delete all bookmarks in the folder) |
| `history_search`       | `session_id`                  | Search history; optional `history_query`, `history_start_time`, `history_end_time`, `history_max_results` |
| `history_recent`       | `session_id`                  | Recent history; optional `history_max_results`                                                      |
| `history_remove`       | `session_id`,`history_url`    | Delete the history record of a URL (**irreversible**)                                               |
| `history_remove_range` | `session_id`                  | Batch-delete history by time range (**irreversible**); optional `history_start_time`, `history_end_time`, clears all if not passed |

#### Downloads, Sessions and Sites

| action               | Required params               | Description                                                             |
| -------------------- | ----------------------------- | ----------------------------------------------------------------------- |
| `download_list`      | `session_id`                  | List downloads; optional `download_limit`                               |
| `download_search`    | `session_id`,`download_query` | Search downloads by file name/URL                                       |
| `download_start`     | `session_id`,`url`            | Start a download; optional `download_filename`, `download_save_as`      |
| `download_erase`     | `session_id`,`download_id`    | Erase a record from the download list (**irreversible**, does not delete the disk file) |
| `download_pause`     | `session_id`,`download_id`    | Pause the download                                                      |
| `download_resume`    | `session_id`,`download_id`    | Resume the download                                                     |
| `download_cancel`    | `session_id`,`download_id`    | Cancel the download                                                     |
| `download_open`      | `session_id`,`download_id`    | Open the downloaded file                                                |
| `session_recent`     | `session_id`                  | Recently closed tabs/windows; optional `session_max_results`            |
| `session_restore`    | `session_id`,`session_key`    | Restore the specified session                                           |
| `topsite_list`       | `session_id`                  | List of most visited sites                                              |
| `readinglist_list`   | `session_id`                  | Reading list                                                            |
| `readinglist_add`    | `session_id`,`url`            | Add to the reading list; optional `readinglist_title`, `readinglist_has_been_read` |
| `readinglist_remove` | `session_id`,`url`            | Remove from the reading list (**irreversible**)                         |
| `readinglist_update` | `session_id`,`url`            | Update a reading list entry; optional `readinglist_title`, `readinglist_has_been_read` |

#### UI and Events

| action                   | Required params                | Description                                                                           |
| ------------------------ | ------------------------------ | ------------------------------------------------------------------------------------- |
| `contextmenu_create`     | `session_id`,`menu_id`,`text`  | Create a context menu item; optional `contextmenu_contexts`, `contextmenu_url_patterns` |
| `contextmenu_remove`     | `session_id`,`menu_id`         | Remove a context menu item                                                            |
| `contextmenu_remove_all` | `session_id`                   | Remove all context menu items                                                         |
| `contextmenu_list`       | `session_id`                   | List the context menu items created by this extension                                 |
| `alarm_create`           | `session_id`,`alarm_name`      | Create a timer; optional `alarm_delay_minutes`, `alarm_period_minutes` (use the latter for periodic tasks) |
| `alarm_list`             | `session_id`                   | List timers                                                                           |
| `alarm_clear`            | `session_id`,`alarm_name`      | Clear the specified timer                                                             |
| `alarm_clear_all`        | `session_id`                   | Clear all timers                                                                      |
| `notification_create`    | `session_id`,`text`            | Send a system notification (`text` is the notification title); optional `notification_message`, `notification_icon_url` |
| `notification_list`      | `session_id`                   | List notifications                                                                    |
| `notification_clear`     | `session_id`,`notification_id` | Close the specified notification                                                      |
| `notification_clear_all` | `session_id`                   | Close all notifications                                                               |
| `search_query`           | `session_id`,`search_query`    | Search in the default search engine; optional `search_disposition`, `search_tab_id`   |

#### System State

| action                  | Required params                           | Description                                                               |
| ----------------------- | ----------------------------------------- | ------------------------------------------------------------------------- |
| `idle_query_state`      | `session_id`                              | Query the idle state                                                      |
| `idle_set_interval`     | `session_id`,`detection_interval_seconds` | Set the idle detection interval (seconds)                                 |
| `idle_get_interval`     | `session_id`                              | Read the idle detection interval                                          |
| `favicon_get_url`       | `session_id`,`page_url`                   | Get the site favicon URL                                                  |
| `webnav_get_all_frames` | `session_id`,`tab_id`                     | List all frames in the tab                                                |
| `webnav_get_frame`      | `session_id`,`tab_id`,`frame_id`          | Read the details of the specified frame                                   |
| `tabgroup_list`         | `session_id`                              | List tab groups                                                           |
| `tabgroup_get`          | `session_id`,`group_id`                   | Read tab group details                                                    |
| `tabgroup_query`        | `session_id`                              | Query tab groups by condition; optional `tabgroup_collapsed`, `tabgroup_title` |
| `tabgroup_update`       | `session_id`,`group_id`                   | Update a tab group; optional `tabgroup_title`, `tabgroup_color`, `tabgroup_collapsed` |

#### Other

| action           | Required params     | Description                                                                       |
| ---------------- | ------------------- | --------------------------------------------------------------------------------- |
| `screenshot`     | `session_id`        | Screenshot; optional `full_page`. Returns the saved PNG path and dimensions        |
| `execute_script` | `session_id`,`code` | Execute JS in the page (high risk); optional `world` (ISOLATED/MAIN, default MAIN). **Return value is not passed through** |

#### High-sensitivity actions (must obtain explicit user authorization before calling)

The following actions involve **credentials, system settings, extension management, or irreversible deletion**, and must be explained to the user and consented to each time before use.

| action                  | Required params                                            | Description                                                                                                                          |
| ----------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `cookie_get`            | `session_id`,`url`,`cookie_name`                           | Read the specified cookie (contains **login credentials**, which is privacy data)                                                    |
| `cookie_get_all`        | `session_id`                                               | Read all cookies; optional `cookie_url`, `cookie_name`                                                                               |
| `cookie_set`            | `session_id`,`url`,`cookie_name`                           | Write/overwrite a cookie; optional `cookie_value`, `cookie_domain`, `cookie_path`, `cookie_secure`, `cookie_http_only`, `cookie_expiration_date` |
| `cookie_remove`         | `session_id`,`url`,`cookie_name`                           | Delete a cookie (**irreversible**, will log out of the corresponding site)                                                           |
| `netrule_list`          | `session_id`                                               | List registered network rules                                                                                                        |
| `netrule_register`      | `session_id`,`rule_id`,`url_filter`                        | Register a network intercept/modify rule; optional `netrule_types`, `netrule_blocking`, `netrule_extra_headers`, `netrule_redirect_url` |
| `netrule_unregister`    | `session_id`,`rule_id`                                     | Unregister a network rule (**irreversible**)                                                                                         |
| `extmgr_list`           | `session_id`                                               | List installed extensions (contains other extension info, which is privacy data)                                                     |
| `extmgr_get`            | `session_id`,`extension_id`                                | Read extension details                                                                                                               |
| `extmgr_launch_app`     | `session_id`,`extension_id`                                | Launch the extension app                                                                                                             |
| `extmgr_set_enabled`    | `session_id`,`extension_id`,`enabled`                      | Enable/disable **other extensions** (affects the user's browser functionality)                                                       |
| `extmgr_uninstall`      | `session_id`,`extension_id`                                | Uninstall **other extensions** (**irreversible**)                                                                                    |
| `native_send`           | `session_id`,`native_host`                                 | Communicate with a native program on this machine; optional `native_message`. **Can execute arbitrary local capabilities, highest risk** |
| `proxy_get_settings`    | `session_id`                                               | Read proxy settings                                                                                                                  |
| `proxy_set_settings`    | `session_id`,`proxy_mode`                                  | Modify proxy settings; optional `proxy_pac_url`, `proxy_rules`, `proxy_bypass_list`                                                  |
| `proxy_clear_settings`  | `session_id`                                               | Clear proxy settings (**irreversible**)                                                                                              |
| `privacy_get`           | `session_id`,`privacy_area`,`privacy_name`                 | Read a privacy setting item                                                                                                          |
| `privacy_set`           | `session_id`,`privacy_area`,`privacy_name`,`privacy_value` | Modify a privacy setting item                                                                                                        |
| `browsingdata_settings` | `session_id`                                               | Read the clearable data types and sizes                                                                                              |
| `browsingdata_remove`   | `session_id`,`data_types`                                  | Clear browsing data (**irreversible**, may clear all the user's history/passwords/cache)                                            |
| `contentsettings_get`   | `session_id`,`content_type`                                | Read a content setting                                                                                                               |
| `contentsettings_set`   | `session_id`,`content_type`,`content_setting`              | Modify a content setting; optional `content_pattern`                                                                                 |
| `contentsettings_clear` | `session_id`,`content_type`                                | Clear a content setting (**irreversible**)                                                                                           |

### Operation 3: Troubleshooting

**Execution steps:**

1. `list_sessions` returns empty → the user has not installed the extension or the extension is not connected; prompt the user to connect the extension in the browser.
2. Error `master_url is not set` → the Agent was not started with `--master-url`.
3. Error `Cannot connect to gateway` → the gateway is not running.
4. Error `unknown action` → the action name is misspelled; compare it with the table above.
5. Element not found → first use `wait_for` to wait, or use `evaluate` to check the actual DOM structure (it may be inside another iframe/Shadow DOM).

**Notes:**

- The return format is uniformly `{success, stdout, stderr}`; `stdout` is the formatted text (objects are indented JSON text).
- `screenshot` saves the base64 as a temporary PNG, and `stdout` only gives the path and dimensions, which can be viewed directly with `add_images`.
- `get_network_requests` blocks for `duration_ms`, so it is recommended to **trigger the page action first, then call it**.

## Checklist

After completing the task, you must confirm:

- [ ] A valid `session_id` has been obtained through `list_sessions`
- [ ] **`script_list` has been used to inventory the scripts already installed in the extension**, and if matched, they are reused first (`script_run`)
- [ ] When a specific page is needed, a `tab_id` has been obtained through `list_tabs`
- [ ] Reading values uses `evaluate`, not the `execute_script` return value
- [ ] Before write operations, the target element has been confirmed, and irreversible actions have been explained to the user
- [ ] Before calling high-sensitivity actions, explicit user authorization has been obtained, and the scope of impact and whether it is reversible have been communicated
- [ ] Asynchronous/navigation scenarios have used `wait_for` to wait
- [ ] Long-running operations have increased `timeout`
- [ ] The result has been verified using read-only operations

## Related Resources

- Tool source code: `{{ haijunbot_src_dir }}/src/haijunbot/haijunbot_tools/browser_ext.py`
- Extension documentation: `{{ haijunbot_src_dir }}/browser_extension/README.md`
- Extension script authoring: `{{ rule_file_dir }}/browser_ext_script.md`
- Server-side browser automation: `{{ rule_file_dir }}/haijunbot_browser_cli.md`
- View the tool list: `{{ rule_file_dir }}/haijunbot_tool_usage.md`
