# Viewing and Switching Agents in the Web UI

## Use Cases

When you have already created multiple Agents in the web page and want to quickly see which Agents exist, what working directory and model group each uses, or switch the current working target between them, you can use the Agent list on the left directly.

## Steps

1. First make sure the current page is already connected to the Web Gateway.
2. Look at the "Agent List" area on the left.
3. In each Agent entry, you can directly see:
   - Agent name or type icon
   - Current status
   - Model group
   - Whether worktree is enabled
   - Working directory

4. To switch the current Agent, simply click that Agent's list item.
5. After switching, the main message area, the bottom input area, the current Agent info at the top, and that Agent's own history messages all switch to the corresponding content.
6. If you are using mobile, the sidebar collapses automatically after clicking an Agent, giving the main content area more space.
7. To browse an Agent's working directory instead of immediately switching to it, click the working directory text below that Agent (in the editor file tree panel, the working directory text under the Agent node can also be clicked to expand the file tree).
8. When expanding the file tree for the first time, clicking the working directory text starts reading the directory content automatically; if there is nothing to display in the directory, "No content to display in the current working directory" is shown.

## Feedback You Will See

- The left area title shows "Agent List".
- If there are no Agents yet, "No Agents yet, click + to create" is shown.
- The Agent currently in use is highlighted in the list.
- After clicking the working directory text, the corresponding Agent's file tree expands and shows the content under that working directory.
- If the current Agent has lost its live connection but can still be restored, the page tries to reconnect automatically; when creating a new Agent or switching to a just-started Agent, this process may involve a short wait.
- If the current Agent has already completed, the page still switches to it and shows the history content, but may not establish a live connection.

## Notes

- In normal mode, clicking a list item switches the current Agent; in bulk mode, clicking a list item is mainly for selection and does not switch directly.
- When switching Agents, the page clears content that was typed in the input box but not yet sent; if you want to keep that text, send it first, or organize it into the buffer manually before switching.
- Some Agents need a little startup time right after creation; after switching to them, the page may load history first, then wait for the connection to stabilize.
- If there are no live messages after switching but history can still be seen, this usually means the current Agent has completed and can be treated as a history session.
