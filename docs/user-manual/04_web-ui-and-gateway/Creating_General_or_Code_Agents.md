# Creating a General or Code Agent

## Use Cases

When you want to create a new task-capable Agent in the Web UI and specify its working directory, model group, and type, you can use the Create Agent dialog. It is suitable for starting a new general task or a code task.

## Steps

1. First make sure the current page is already connected to the Web Gateway.
2. Click "+" at the top of the Agent list on the left.
3. In the "Create Agent" dialog, configure the following in order:
   - Agent type: General Agent or Code Agent
   - Agent name (optional)
   - Working directory
   - Model group
   - Target node (optional)

4. If the current Gateway has node mode enabled and the master node has discovered available child nodes, you can also choose which node the Agent is created on from the "Target Node" dropdown.
5. If you chose a Code Agent, you can additionally decide whether to enable worktree.
6. There are two ways to fill in the working directory:
   - Type the path manually
   - Click "Choose Directory" and browse to confirm it in the directory picker window

7. In the directory picker window, you can use:
   - Refresh the current directory
   - Go up to the parent directory
   - Search for a directory
   - Click or double-click a directory to enter it
   - Finally click "Confirm" to select the working directory

8. Once all required fields are ready, click "Create".
9. After creation succeeds, the new Agent is added to the list; if a panel is already open, it automatically opens in a new panel and switches to the new Agent; if you are still on the pet hall (no panels open), the new Agent appears as a pet in the hall without automatically opening a panel.

## Feedback You Will See

- The creation dialog is titled "Create Agent".
- The Agent type shows two descriptions:
  - General Agent: suitable for everyday tasks and general operations
  - Code Agent: focused on code analysis and development tasks

- If the working directory is empty, the "Create" button stays disabled.
- If node mode is enabled, an additional "Target Node" dropdown appears in the creation dialog.
- After creation succeeds, the new Agent appears in the list on the left; if a panel is already open it switches to the new Agent automatically; if you are on the pet hall, it appears as a pet in the hall.
- After creation succeeds, the list shows the node information of that Agent.
- If creation fails, the page shows a failure message.

## Notes

- The working directory is required; you cannot create an Agent without it.
- The worktree toggle only applies to Code Agents; General Agents do not use this setting.
- Model groups come from the list of available model groups returned by the current gateway, so you need a successful connection before you can select them normally.
- The target node list comes from the node status returned by the current master node; if you are in single-node mode or there are no available child nodes, you may only see the default master node.
- In node mode, after you create an Agent on a child node, subsequent access is still forwarded through the current master node, so the client does not need to switch to the child node's address manually.
- On mobile and desktop, the focusing and interaction details in the directory picker differ slightly, but the core flow is the same.
