# Using the Management Sidebar

## Use Cases

When you want to quickly see which scheduled tasks, background services (Daemons), or browser extensions in the current system have connected and reported their capabilities, you can use the management sidebar. It provides a read-only overview so you can understand the running state of the current environment.

## Steps

### Opening the Management Sidebar

1. In the left activity bar of the Web UI, find the "Enhanced Capabilities List" icon (grid-shaped) and the "Scheduled Tasks" icon (clock-shaped).
2. Click one of the icons to open the corresponding management sidebar tab on the left.
3. Click the same icon again to collapse the sidebar.

### Viewing Scheduled Tasks

1. Click the "Scheduled Tasks" icon (clock-shaped) in the activity bar.
2. The sidebar lists the scheduled tasks that have been created.
3. Each task shows its name, scheduling type, and scheduling information (e.g. the specified run time, delay in seconds, interval in seconds, or cron expression).
4. If there are no scheduled tasks, a "No scheduled tasks" message is shown.

### Viewing the Enhanced Capabilities List

1. Click the "Enhanced Capabilities List" icon (grid-shaped) in the activity bar.
2. The sidebar shows the connected capabilities by category:
   - **Daemon capabilities**: lists the current online background service (Daemon) sessions and the capabilities they report. Each capability can be expanded to view its name, description, parameters, and the platform it belongs to.
   - **Browser extension capabilities**: lists the current online browser extension sessions and the capabilities they report, also expandable for details.
   - **Custom scripts**: lists the installed scripts (gateway script library) and shows the number of scripts.
3. If a session reports no capabilities, "This session registered no capabilities" or "This extension reported no capabilities" is shown.
4. If there are no online Daemons, extensions, or scripts, "No capabilities available" is shown.

### Expanding or Collapsing Capability Details

1. In the capabilities list, click the arrow (▶/▼) to the left of a capability entry.
2. Once expanded, you can view the capability's description, parameter JSON, and the platform it belongs to.
3. Click the arrow again to collapse the details.

## Feedback You Will See

- The management sidebar is read-only; you can only view and expand/collapse content, not modify or delete scheduled tasks, capabilities, or scripts here.
- The "Enhanced Capabilities List" tab provides a manual refresh button to re-fetch the latest capabilities list.
- The scheduled tasks tab auto-refreshes periodically to show the latest task status.
- Daemon capabilities and browser extension capabilities have the same display format (name, description, parameters, platform); both are reported dynamically by the peers, so the front end does not need to adapt individually per capability.

## Notes

- The management sidebar shows sessions and capabilities that are "currently online"; if a Daemon or browser extension is not installed, not started, or not connected, it does not appear in the list.
- Scheduled tasks are managed uniformly by the backend scheduler, and the management sidebar only displays them; creating or deleting scheduled tasks must be done through other entries (such as the management panel or the API).
- The capabilities list only reflects the state at report time; after adding or removing capabilities, you need to refresh to see the latest results.
