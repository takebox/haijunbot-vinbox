# Restoring Agent Sessions

## Use Cases

When you switch to an Agent and want to continue an existing but not-yet-restored history session, you can use the session restore feature in the web page instead of starting over from scratch.

## Steps

1. Click the Agent you want to switch to in the Agent list on the left.
2. After the page switches to that Agent, if the system detects that the Agent has restorable sessions but the current history messages are empty, the "Select Session Restore" window pops up automatically.
3. Select the session you want to restore from the list.
4. If there are many restorable sessions, type a keyword in the search box at the top of the window to filter by session name, session time, or file name, and quickly locate the target session.
5. Click "Restore Session" to complete the restore.
6. If you do not want to restore, you can also click "Skip" to go directly into the current Agent's history view or a new session state.

> Note: the current version of the Web UI has disabled the "auto-popup session restore window" behavior (it previously popped up a selection list unexpectedly and hurt the experience). So normally switching Agents does not pop that window up automatically, and the related UI only appears after it is re-enabled.

## Feedback You Will See

- The session restore window is titled "Select Session Restore".
- When restorable sessions exist, a search box appears at the top of the window (placeholder "Search session name..."); typing a keyword filters the session list in real time, matching session name, session time, or file name, case-insensitively.
- Each restorable session shows:
  - Session name
  - Session time

- If there are no restorable sessions, the window shows "No restorable sessions".
- If no sessions match the search, the window shows "No sessions match the keyword".
- After a successful restore, the window closes and the Agent's history messages reload.
- When restore fails, the page shows a "Session restore failed" message.

## Notes

- The restore window does not appear every time you switch Agents; it only pops up when the restorable condition is met.
- You can choose to skip the restore; restoring an old session is never forced.
- Session restore depends on the current page being connected successfully and the current Agent being able to access the relevant data.
- If restore fails, first check the gateway connection status and whether the current Agent is still available.
