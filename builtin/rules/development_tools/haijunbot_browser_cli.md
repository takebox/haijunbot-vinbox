---
name: haijunbot_browser_cli
description: Triggered when there is a need to use a browser for automation operations. Triggered whenever the user mentions "browser automation", "web testing", "hb", "haijunbot-browser", "Playwright", "web crawler", or "data collection". Not triggered: only manually browsing web pages; only reading web page content (use read_webpage); API calls that do not involve a browser.
---

# HaijunBot Browser CLI (hb) Usage Guide

## Overview

`hb` (or `haijunbot-browser`) is a Playwright-based browser automation command-line tool that supports a daemon mode, allowing a browser session to be maintained across multiple CLI invocations.

## Quick Start

```bash
# 1. Start the daemon (runs in the background)
hb daemon

# 2. Launch the browser
hb launch --browser-id demo

# 3. Navigate to a page
hb navigate --url https://example.com --browser-id demo

# 4. Get the page text
hb gettext --selector 'h1' --browser-id demo

# 5. Take a screenshot
hb screenshot --browser-id demo --path /tmp/screenshot.png
```

## Common Parameters

All commands support the following optional parameter:

- `--browser-id TEXT`: browser session ID (default: `default`)

## Command List

### 1. Daemon Management

#### daemon - Start the daemon

Start the background daemon, used to persist browser sessions. The daemon detaches from the terminal and keeps running, and does not exit even if the terminal is closed.

**Parameters:**

None (the socket is fixed at `~/.haijunbot/playwright_daemon.sock`)

**Example:**

```bash
hb daemon
hb daemon-stop   # shut down the daemon
```

**Notes:**

- The daemon checks whether it is already running, and will not start a duplicate if it is already running
- Uses the double-fork method to implement a true background daemon
- If there are no requests within 30 minutes, the daemon automatically exits to save resources
- The run log is written to `~/.haijunbot/logs/browser_daemon/daemon.log`, containing records of various browser operations (such as launch, navigate, click, etc.)

#### daemon-stop - Shut down the daemon

Gracefully shut down the daemon; all browser sessions will be closed.

**Parameters:** None

**Example:**

```bash
hb daemon-stop
```

### 2. Browser Management

#### launch - Launch the browser

Launch a new browser instance.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Notes:**

- Prioritizes launching in headed (UI) mode; if it fails, automatically falls back to headless mode.

**Example:**

```bash
hb launch --browser-id demo
```

#### close - Close the browser

Close the specified browser instance.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb close --browser-id demo
```

#### list - List browsers

List all active browser sessions.

**Parameters:**

None

**Example:**

```bash
hb list
```

### 3. Page Navigation

#### navigate - Navigate to a URL

Navigate the browser to the specified URL.

**Parameters:**

- `-u, --url TEXT`: the URL to navigate to (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb navigate --url https://example.com --browser-id demo
```

#### goback - Go back

Navigate to the previous page.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb goback --browser-id demo
```

#### goforward - Go forward

Navigate to the next page.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb goforward --browser-id demo
```

### 4. Element Interaction

#### click - Click an element

Click an element. Supports a CSS selector or the index from list-interactables.

**Parameters:**

- `-s, --selector TEXT`: CSS selector (choose one of --selector or --index)
- `-i, --index INT`: interactable element index (choose one of --selector or --index)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb click --selector '#submit-button' --browser-id demo
hb click --index 3 --browser-id demo   # click the 3rd element in list-interactables
```

#### type - Enter text

Enter text into an element. Supports a CSS selector or the index from list-interactables.

**Parameters:**

- `-s, --selector TEXT`: CSS selector (choose one of --selector or --index)
- `-i, --index INT`: interactable element index (choose one of --selector or --index)
- `-t, --text TEXT`: the text to enter (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb type --selector '#username' --text 'myuser' --browser-id demo
hb type --index 5 --text 'user@example.com' --browser-id demo
```

#### hover - Hover

Move the mouse over the matching element.

**Parameters:**

- `-s, --selector TEXT`: CSS selector (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb hover --selector '.menu-item' --browser-id demo
```

#### drag - Drag

Drag the source element to the target element.

**Parameters:**

- `-s, --selector TEXT`: CSS selector of the source element (required)
- `-t, --target-selector TEXT`: CSS selector of the target element (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb drag --selector '#draggable' --target-selector '#dropzone' --browser-id demo
```

#### doubleclick - Double-click

Double-click the matching element.

**Parameters:**

- `-s, --selector TEXT`: CSS selector (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb doubleclick --selector '.file' --browser-id demo
```

#### presskey - Press a key

Press the specified keyboard key.

**Parameters:**

- `-k, --key TEXT`: the key to press (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb presskey --key 'Enter' --browser-id demo
hb presskey --key 'Escape' --browser-id demo
```

### 5. Information Retrieval

#### screenshot - Page screenshot

Capture a screenshot of the current page.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)
- `-p, --path TEXT`: screenshot path (default: `/tmp/screenshot.png`)

**Example:**

```bash
hb screenshot --browser-id demo --path /tmp/my_screenshot.png
```

#### gettext - Get text

Get the text content from the matching element.

**Parameters:**

- `-s, --selector TEXT`: CSS selector (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb gettext --selector 'h1' --browser-id demo
hb gettext --selector '.title' --browser-id demo
```

#### getattribute - Get attribute

Get an attribute value from the selected element.

**Parameters:**

- `-s, --selector TEXT`: CSS selector (required)
- `-a, --attribute TEXT`: attribute name (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb getattribute --selector '#link' --attribute 'href' --browser-id demo
hb getattribute --selector 'img' --attribute 'src' --browser-id demo
```

#### getelementinfo - Get element info

Get detailed information about the selected element.

**Parameters:**

- `-s, --selector TEXT`: CSS selector (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb getelementinfo --selector '#main-content' --browser-id demo
```

#### get-markdown - Get page Markdown

Convert the current page's HTML content into Markdown format.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb get-markdown --browser-id demo
```

**Notes:**

- Uses the markdownify library to convert the page HTML into Markdown
- Suitable for extracting the structured content of a page
- The returned Markdown format can be used directly for document generation or content analysis

#### list-interactables - List interactable controls

List all interactable elements on the page (buttons, input boxes, links, etc.). The returned `selector` is consistent with commands such as click and type, and can be used directly for subsequent operations.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)
- `-f, --filter TEXT`: filter by element type (optional: `button`, `input`, `link`, `checkbox`, `radio`, `select`, `file`)

**Example:**

```bash
# List all interactable controls
hb list-interactables --browser-id demo

# List only buttons
hb list-interactables --browser-id demo --filter button

# List only input boxes
hb list-interactables --browser-id demo --filter input

# List only links
hb list-interactables --browser-id demo --filter link
```

**Notes:**

- Supported element types include:
  - `button`: buttons, submit buttons, reset buttons, etc.
  - `input`: text input boxes, password boxes, email boxes, number input boxes, text areas
  - `link`: links with an href attribute
  - `checkbox`: checkboxes
  - `radio`: radio buttons
  - `select`: dropdown select boxes
  - `file`: file upload input boxes
- The information returned for each element includes: index, type, selector, text content
- click, type, gettext, hover, doubleclick, getelementinfo, getattribute, elementscreenshot support the `--index` parameter, so you can operate directly by index
- **selector generation priority**: `#id` > `[name]` > `[placeholder]` > `[aria-label]` > `[data-testid]` > `a[href]` > `.class:nth-of-type(n)` > `tag:nth-of-type(n)`, trying to ensure uniqueness
- Returns at most 100 elements to avoid an excessive amount of data
- Element text content is limited to 100 characters

#### elementscreenshot - Element screenshot

Capture a screenshot of the specified element.

**Parameters:**

- `-s, --selector TEXT`: CSS selector of the element (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb elementscreenshot --selector '.header' --browser-id demo --path /tmp/element.png
```

#### console - Get console logs

Get the console logs from the browser session.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)
- `--clear-logs`: clear the logs after reading

**Example:**

```bash
hb console --browser-id demo
hb console --browser-id demo --clear-logs
```

#### eval - Execute JavaScript

Execute JavaScript code in the browser context.

**Parameters:**

- `-c, --code TEXT`: the JavaScript code to execute (required)
- `--browser-id TEXT`: browser ID (default: `default`)
- `--save-result`: save the result to a file

**Example:**

```bash
hb eval --code 'document.title' --browser-id demo
hb eval --code 'window.scrollY' --browser-id demo
hb eval --code 'document.querySelectorAll("a").length' --browser-id demo
```

#### getperformancemetrics - Get performance metrics

Get the performance metrics of the current page.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb getperformancemetrics --browser-id demo
```

### 6. Wait Operations

#### waitforselector - Wait for a selector

Wait for an element to reach the specified state.

**Parameters:**

- `-s, --selector TEXT`: CSS selector (required)
- `--browser-id TEXT`: browser ID (default: `default`)
- `--wait-state TEXT`: wait state (visible, hidden, attached, detached) (default: `visible`)
- `-t, --timeout FLOAT`: timeout (seconds) (default: 30.0)

**Example:**

```bash
hb waitforselector --selector '#content' --browser-id demo
hb waitforselector --selector '.loading' --wait-state hidden --browser-id demo
hb waitforselector --selector '#button' --timeout 10 --browser-id demo
```

#### waitfortext - Wait for text

Wait for text to appear on the page.

**Parameters:**

- `-t, --text TEXT`: the text to wait for (required)
- `--browser-id TEXT`: browser ID (default: `default`)
- `-s, --selector TEXT`: CSS selector (default: `*`)
- `--timeout FLOAT`: timeout (seconds) (default: 30.0)

**Example:**

```bash
hb waitfortext --text 'Loading complete' --browser-id demo
hb waitfortext --text 'Success' --selector '#status' --browser-id demo
```

### 7. Form Operations

#### fillform - Fill a form

Fill multiple form fields with values.

**Parameters:**

- `-f, --fields TEXT`: form fields (in JSON string format) (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb fillform --fields '{"#username":"john","#password":"secret","#email":"john@example.com"}' --browser-id demo
```

#### submitform - Submit a form

Submit the specified form.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)
- `--form-selector TEXT`: form selector (default: `form`)

**Example:**

```bash
hb submitform --browser-id demo
hb submitform --form-selector '#login-form' --browser-id demo
```

#### clearform - Clear a form

Clear all fields in the specified form.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)
- `--form-selector TEXT`: form selector (default: `form`)

**Example:**

```bash
hb clearform --browser-id demo
hb clearform --form-selector '#contact-form' --browser-id demo
```

### 8. File Operations

#### uploadfile - Upload a file

Upload a file to the specified input element.

**Parameters:**

- `-s, --selector TEXT`: CSS selector (required)
- `-f, --file-path TEXT`: path of the file to upload (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb uploadfile --selector '#file-input' --file-path /tmp/document.pdf --browser-id demo
```

#### downloadfile - Download a file

Download a file from the current page.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)
- `-s, --selector TEXT`: CSS selector of the download button/link

**Example:**

```bash
hb downloadfile --browser-id demo
hb downloadfile --selector '#download-btn' --browser-id demo
```

### 9. Tab Management

#### newtab - Create a new tab

Create a new tab in the browser.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb newtab --browser-id demo
```

#### switchtab - Switch tabs

Switch to the specified tab.

**Parameters:**

- `-p, --page-id TEXT`: the page ID to switch to (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb switchtab --page-id 2 --browser-id demo
```

#### closetab - Close a tab

Close the specified tab.

**Parameters:**

- `-p, --page-id TEXT`: the page ID to close (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb closetab --page-id 1 --browser-id demo
```

### 10. Scroll Operations

#### scrollto - Scroll to a position

Scroll to the specified position on the page.

**Parameters:**

- `-x, --scroll-x INTEGER`: the X coordinate to scroll to (default: 0)
- `-y, --scroll-y INTEGER`: the Y coordinate to scroll to (default: 0)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb scrollto --scroll-x 0 --scroll-y 500 --browser-id demo
```

#### scrolldown - Scroll down

Scroll the page down by the specified amount.

**Parameters:**

- `-a, --scroll-amount INTEGER`: number of pixels to scroll down (default: 300)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb scrolldown --scroll-amount 500 --browser-id demo
hb scrolldown --browser-id demo  # use the default value
```

#### scrollup - Scroll up

Scroll the page up by the specified amount.

**Parameters:**

- `-a, --scroll-amount INTEGER`: number of pixels to scroll up (default: 300)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb scrollup --scroll-amount 500 --browser-id demo
```

### 11. Cookie Management

#### getcookies - Get cookies

Get all cookies of the browser.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb getcookies --browser-id demo
```

#### setcookies - Set cookies

Set cookies from a JSON string.

**Parameters:**

- `-c, --cookies TEXT`: cookies (in JSON list format) (required)
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb setcookies --cookies '[{"name":"session","value":"abc123","domain":"example.com"}]' --browser-id demo
```

#### clearcookies - Clear cookies

Clear all cookies of the browser.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb clearcookies --browser-id demo
```

### 12. LocalStorage Management

#### getlocalstorage - Get LocalStorage

Get all LocalStorage data of the page.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb getlocalstorage --browser-id demo
```

#### setlocalstorage - Set LocalStorage

Set LocalStorage from a JSON string.

**Parameters:**

- `-d, --data TEXT`: storage data (in JSON dictionary format) (required)
- `--clear`: clear all LocalStorage before setting
- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb setlocalstorage --data '{"user":"john","token":"abc123"}' --browser-id demo
hb setlocalstorage --data '{"key":"value"}' --clear --browser-id demo
```

### 13. Network Monitoring

#### startnetworkmonitor - Start network monitoring

Start monitoring network requests.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb startnetworkmonitor --browser-id demo
```

#### getnetworkrequests - Get network requests

Get all recorded network requests.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb getnetworkrequests --browser-id demo
```

### 14. PDF Export

#### exportpdf - Export PDF

Export the current page as PDF.

**Parameters:**

- `--browser-id TEXT`: browser ID (default: `default`)

**Example:**

```bash
hb exportpdf --browser-id demo
```

## Complete Usage Examples

### Web Automation Example

```bash
# 1. Start the daemon
hb daemon

# 2. Launch the browser
hb launch --browser-id mybrowser

# 3. Navigate to the login page
hb navigate --url https://example.com/login --browser-id mybrowser

# 4. Fill in the login form
hb fillform --fields '{"#username":"myuser","#password":"mypass"}' --browser-id mybrowser

# 5. Submit the form
hb submitform --browser-id mybrowser

# 6. Wait for a successful login
hb waitfortext --text "Welcome" --browser-id mybrowser

# 7. Take a screenshot
hb screenshot --path /tmp/after_login.png --browser-id mybrowser

# 8. Close the browser
hb close --browser-id mybrowser
```

### Data Scraping Example

```bash
# 1. Start the daemon and browser
hb daemon
hb launch --browser-id scraper

# 2. Navigate to the target page
hb navigate --url https://example.com/articles --browser-id scraper

# 3. Wait for the content to load
hb waitforselector --selector '.article-list' --browser-id scraper

# 4. Get all article titles
hb eval --code 'Array.from(document.querySelectorAll(".article-title")).map(el => el.textContent)' --browser-id scraper

# 5. Take a screenshot
hb screenshot --path /tmp/articles.png --browser-id scraper
# 6. Export PDF
hb exportpdf --browser-id scraper
```

### Form Testing Example

```bash
# 1. Start the daemon and browser
hb daemon
hb launch --browser-id form_test

# 2. Navigate to the form page
hb navigate --url https://example.com/contact --browser-id form_test

# 3. Fill in the form
hb type --selector '#name' --text 'John Doe' --browser-id form_test
hb type --selector '#email' --text 'john@example.com' --browser-id form_test
hb type --selector '#message' --text 'Hello, this is a test message.' --browser-id form_test

# 4. Take a screenshot
hb screenshot --path /tmp/filled_form.png --browser-id form_test

# 5. Submit the form
hb click --selector '#submit' --browser-id form_test

# 6. Wait for confirmation
hb waitforselector --selector '.success-message' --browser-id form_test

# 7. Get the success message
hb gettext --selector '.success-message' --browser-id form_test
```

## Best Practices

### 1. Always use a browser ID

Use different browser IDs for different tasks to avoid conflicts:

```bash
hb launch --browser-id task1
hb launch --browser-id task2
```

### 2. Use waits instead of sleeps

Do not use a fixed wait time; use `waitforselector` or `waitfortext`:

```bash
# Not recommended
sleep 5
hb click --selector '#button' --browser-id demo

# Recommended
hb waitforselector --selector '#button' --browser-id demo
hb click --selector '#button' --browser-id demo
```

### 3. Use CSS selectors

Prioritize stable CSS selectors to avoid fragile selectors:

```bash
# Fragile (depends on position)
hb click --selector 'div:nth-child(3)' --browser-id demo

# Stable (based on semantics)
hb click --selector '#submit-button' --browser-id demo
```

### 4. Prefer Index over selector

For element operations, **it is recommended to prefer the `--index` parameter over `--selector`**. Get the element index via the `list-interactables` command, then operate using the index:

```bash
# First list the interactable elements
hb list-interactables --browser-id demo

# Operate using index (recommended)
hb click --index 3 --browser-id demo
hb type --index 5 --text 'user@example.com' --browser-id demo

# Instead of using a selector (not recommended, unless necessary)
hb click --selector 'div.form:nth-child(2) > button.submit' --browser-id demo
```

**Advantages:**

- **More stable and reliable**: `list-interactables` intelligently chooses the most suitable selector (priority: `#id` > `[name]` > `[placeholder]` > `[aria-label]` > `[data-testid]`, etc.), which is more accurate than manually constructing a selector
- **Avoid fragile selectors**: no need to write complex CSS/XPath selectors that may change with the page structure
- **Easier to debug**: the index is clear and intuitive, making it easy to see the operated element
- **Fewer errors**: avoids the problem of an element not being found due to a selector writing error

**When to use selectors:**

- When a clear `id` or stable attribute is known (such as `#submit-button`)
- When the element is not in the interactable list
- When you need to wait for an element to appear and then operate (combined with `waitforselector`)

### 5. Error handling

All commands return a response in JSON format:

```json
{
  "success": true,
  "stdout": "operation output",
  "stderr": "error message"
}
```

### 6. Debugging techniques

Use `getelementinfo` and `console` to debug:

```bash
# Check the element state
hb getelementinfo --selector '#element' --browser-id demo

# Check the console logs
hb console --browser-id demo

# Execute debugging JavaScript
hb eval --code 'console.log("debug"); document.title' --browser-id demo
```

### 7. Performance optimization

For large pages, consider using headless mode:

```bash
hb launch --browser-id demo
```

### 8. Session management

Check active sessions periodically:

```bash
hb list
```

Close the browser after finishing work:

```bash
hb close --browser-id demo
```

## Troubleshooting

### The daemon is not running

**Error:** `Daemon not running at ~/.haijunbot/playwright_daemon.sock`

**Solution:**

```bash
# Check whether the daemon is running
ps aux | grep 'hb daemon'

# Restart the daemon
hb daemon
```

### Socket file conflict

**Error:** `Address already in use`

**Solution:**

```bash
# Clean up the old socket file
rm -f ~/.haijunbot/playwright_daemon.sock

# Restart the daemon
hb daemon
```

### Element not found

**Error:** `Element not found`

**Solution:**

```bash
# 1. Wait for the element to appear
hb waitforselector --selector '#element' --browser-id demo

# 2. Check whether the selector is correct
hb getelementinfo --selector '#element' --browser-id demo
# 3. Check the page source
hb eval --code 'document.body.innerHTML' --browser-id demo
```

### Timeout error

**Error:** `Timeout waiting for element`

**Solution:**

```bash
# Increase the timeout
hb waitforselector --selector '#element' --timeout 60 --browser-id demo

# Or wait for a different state
hb waitforselector --selector '#loading' --wait-state hidden --browser-id demo
```

## Command Cheat Sheet

| Command               | Description       | Key parameters                                            |
| --------------------- | ----------------- | --------------------------------------------------------- |
| daemon                | Start the daemon  | none                           |
| daemon-stop           | Shut down the daemon | none                                                        |
| launch                | Launch the browser | --browser-id                                              |
| close                 | Close the browser | --browser-id                                              |
| list                  | List browsers     | none                                                        |
| navigate              | Navigate to URL   | --url (required), --browser-id                                |
| click                 | Click an element  | --selector (required), --browser-id                           |
| type                  | Enter text        | --selector (required), --text (required), --browser-id            |
| screenshot            | Page screenshot   | --path, --browser-id       |
| gettext               | Get text          | --selector (required), --browser-id                           |
| getelementinfo        | Element info      | --selector (required), --browser-id                           |
| getattribute          | Get attribute     | --selector (required), --attribute (required), --browser-id       |
| waitforselector       | Wait for selector | --selector (required), --wait-state, --timeout, --browser-id  |
| waitfortext           | Wait for text     | --text (required), --selector, --timeout, --browser-id        |
| hover                 | Hover             | --selector (required), --browser-id                           |
| drag                  | Drag              | --selector (required), --target-selector (required), --browser-id |
| doubleclick           | Double-click      | --selector (required), --browser-id                           |
| presskey              | Press a key       | --key (required), --browser-id                                |
| fillform              | Fill a form       | --fields (required), --browser-id                             |
| submitform            | Submit a form     | --form-selector, --browser-id                 |
| clearform             | Clear a form      | --form-selector, --browser-id                             |
| uploadfile            | Upload a file     | --selector (required), --file-path (required), --browser-id       |
| downloadfile          | Download a file   | --selector, --browser-id                                  |
| newtab                | New tab           | --browser-id                                              |
| switchtab             | Switch tabs       | --page-id (required), --browser-id                            |
| closetab              | Close a tab       | --page-id (required), --browser-id                            |
| goback                | Go back           | --browser-id                                              |
| goforward             | Go forward        | --browser-id                                              |
| scrollto              | Scroll to a position | --scroll-x, --scroll-y, --browser-id                      |
| scrolldown            | Scroll down       | --scroll-amount, --browser-id                             |
| scrollup              | Scroll up         | --scroll-amount, --browser-id                          |
| getcookies            | Get cookies       | --browser-id                                              |
| setcookies            | Set cookies       | --cookies (required), --browser-id                            |
| clearcookies          | Clear cookies     | --browser-id                                              |
| getlocalstorage       | Get LocalStorage  | --browser-id                                              |
| setlocalstorage       | Set LocalStorage  | --data (required), --clear, --browser-id                      |
| startnetworkmonitor   | Start network monitoring | --browser-id                                              |
| getnetworkrequests    | Get network requests | --browser-id                                              |
| elementscreenshot     | Element screenshot | --selector (required), --browser-id      |
| exportpdf             | Export PDF        | --browser-id                                              |
| console               | Get console logs  | --browser-id, --clear-logs                                |
| eval                  | Execute JavaScript | --code (required), --save-result, --browser-id                |
| getperformancemetrics | Performance metrics | --browser-id                                              |

## Related Documentation

- [Playwright documentation](https://playwright.dev/python/)
- [CSS selector reference](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Selectors)
- [Typer documentation](https://typer.tiangolo.com/)

## Version Information

- Tool name: HaijunBot Browser CLI
- Commands: hb, haijunbot-browser
- Daemon: supports continuous background running
- Output format: JSON
