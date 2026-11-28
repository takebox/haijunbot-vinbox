# Viewing Version and About Info

## Use Cases

When you want to confirm the current HaijunBot Web Gateway version, view the open-source license and author information, or learn which version each connected node, background service (Daemon), and browser extension is running, you can use the "About" dialog.

## Steps

### Opening the "About" Dialog

1. In the activity bar on the left of the Web UI, find the "About" icon (circular exclamation-mark shape).
2. Click the icon to open the "About" dialog.
3. Click the same icon again, click the close button (×) at the top-right of the dialog, or press `Esc` to close it.

### Viewing Software Information

The top of the dialog shows the following:

- **Software name**: HaijunBot Web Gateway
- **Version**: the frontend version; if the backend version differs from the frontend, "/ Backend <version>" is shown additionally
- **Open-source license**: MIT
- **Author**: skyfire

### Viewing Component Versions

The dialog lists the component versions in the current environment by category:

- **Node versions**: lists the nodes under the current gateway with their version numbers and online status.
- **Background service (daemon) versions**: lists the current online background services with their version numbers and the platforms they belong to.
- **Browser extension versions**: lists the current online browser extensions with their version numbers and browser information.

If a category has no online components at the moment, the corresponding empty-state message is shown (e.g. "No node information", "No online background services", "No online browser extensions").

## Feedback You Will See

- The "About" dialog is read-only; you can only view information and cannot modify the version or config here.
- Version information comes from the version number built into the frontend, as well as data returned by the backend `/api/node/status`, `/api/daemon/sessions`, and `/api/browser-ext/sessions`.
- Only "currently online" nodes, background services, or browser extensions appear in the corresponding lists; components that are not installed, not started, or not connected are not shown.

## Notes

- The "About" dialog shows the state when it was opened; if a component comes online or goes offline while the dialog is open, you need to close and reopen it to see the latest results.
- The frontend version number syncs automatically with releases; when the backend version matches the frontend, it is not shown again.
