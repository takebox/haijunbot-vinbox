# Managing History and Reconnecting

## Use Cases

When you want to see how many history messages are saved in the current browser, clear history, change your login password, or modify the gateway connection info and reconnect to the gateway, you can do all of this in the web settings or the connection dialog.

## Steps

### Viewing History Statistics

1. Click the "Settings" button at the top of the page.
2. In the settings window, view the history message statistics.
3. This section shows the current number of history messages and the space they occupy.

### Clearing History

1. In the settings window, click "Clear History".
2. Confirm again according to the page prompt.
3. After clearing, the current Agent's message area and history pagination state update accordingly.

### Changing the Login Password

1. In the "Change Password" area of the settings window, enter the old password, the new password, and confirm it again.
2. Click the "Change Password" button to submit.
3. After a successful change, use the new password the next time you log in.

### Disconnecting

1. In the "Connection Management" area of the settings window, click "Disconnect".
2. The page closes all WebSocket connections and refreshes the page.

### Modifying Gateway Connection Info and Reconnecting

The gateway address, username, and connection password are filled in the **connection dialog**, not in the settings dialog:

1. Disconnect the current connection, or refresh the page directly to return to the connection dialog.
2. In the connection dialog, modify the gateway address, username, and password.
3. Click "Connect" to establish a new connection with the new information.
4. If the connection succeeds, the page continues into the normal state; if it fails, the connection window or an error message appears again.

## Feedback You Will See

- The settings window is titled "Settings".
- The history message area shows:
  - The number of history messages
  - Storage space

- If there is no history, the "Clear History" button is disabled.
- Clearing history has a confirmation step because it cannot be undone.
- After changing the password successfully there is a confirmation; changing the password does not affect the current established connection.
- After disconnecting, the connection status at the top changes to "Not Connected" and the page refreshes.

## Notes

- History is stored locally in the current browser, not as server-side global history.
- Clearing history cannot be undone; before confirming, decide whether you still need to keep the current browsing records.
- Changing the login password happens in the settings dialog; changing the gateway address, username, or connection password must be done in the connection dialog, followed by a reconnect.
- If reconnecting fails, first check the gateway address format, whether the gateway service is running, and whether the password is correct.
