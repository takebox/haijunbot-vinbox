# Opening Settings and Managing Connections, History, and Config Backups

## Use Cases

Once you are in the Web UI and want to change your login password, disconnect, view and clear the history saved in the current browser, or export a node's config as a backup and restore it from a backup file, you can use the settings dialog.

## Steps

1. Open the "Settings" dialog in the Web UI.
2. In the dialog, view or modify the following as needed:
   - The "Change Password" area (change the login password)
   - History message count and storage space information
   - The "Disconnect" button (closes all WebSocket connections and refreshes the page)
   - Other interface preference toggles (auto-login, notifications, hide working directory, node display name, etc.)

3. To clear the currently saved history, click "Clear History".
4. To back up or restore a node's config, use the "Config Backup and Restore" area:
   - **Export Config**: first select the target node in the dropdown, then click "Export Config"; the system pulls the node's current config and downloads it as a JSON file.
   - **Import Config**: first select the target node in the dropdown, then click "Import Config" and choose a previously exported JSON backup file; the system validates the format and applies the config to the node.

5. To change the gateway address, username, or connection password, operate in the **connection dialog** and reconnect (this information is not in the settings dialog).
6. If you are done for now, click "Close" or the close button at the top-right to leave the settings dialog.

## Feedback You Will See

- The settings dialog is titled "Settings".
- The history message area shows "History message count" and "Storage space".
- When there is no local history, the "Clear History" button is disabled.
- The "Connection Management" area shows a "Disconnect" button and notes that it disconnects all WebSocket connections and refreshes the page.
- The "Config Backup and Restore" area shows "Export Config" and "Import Config" buttons together with a node dropdown.
- After a successful export, the browser downloads a `haijunbot-config-node-date.json` file.
- After a successful import, the number of imported config items is shown; before importing, the system automatically backs up the existing config.

## Notes

- Changing the login password is done in the settings dialog; changing the gateway address, username, or connection password must be done in the connection dialog, followed by a reconnect.
- "Disconnect" closes all WebSocket connections and refreshes the page, so confirm before operating.
- History statistics and cleanup target the data saved in the current browser; after switching browsers or devices, the history count you see may differ.
- Config export/import requires the `admin:config` permission; without it, the operation fails with an insufficient permission message.
- Importing a config overwrites the corresponding config items on the target node; before importing, the system automatically backs up the existing config so you can roll back if needed.
- Before importing, make sure the selected JSON file format is correct (it should be a config object); otherwise the import is rejected.
