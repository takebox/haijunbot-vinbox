# Duplicating, Renaming, and Deleting Agents

## Use Cases

When you want to quickly reuse the configuration of an existing Agent, change an Agent's display name, or clean up an Agent you no longer need, you can complete the duplicate, rename, and delete operations directly in the Agent list.

## Steps

### Duplicating an Agent

1. Find the target Agent in the Agent list on the left.
2. Click the duplicate button to the right of that Agent.
3. The system creates a copy based on the current Agent's type, working directory, model group, and other information.
4. If the current version supports node-aware duplication, the system tries to keep the original Agent's node assignment as well, or lets you choose the target node.
5. Duplication opens the "Create Agent" dialog prefilled with the original Agent's type, working directory, model group, node, and other settings; click "Create" after confirming to generate the copy. Once the copy joins the list, its switching behavior matches a newly created Agent (switches automatically when a panel is open, and appears as a pet when you are on the pet hall).

### Renaming an Agent

1. Find the target Agent in the Agent list.
2. Click the rename button on the right.
3. Enter a new name in the "Rename Agent" window.
4. To restore the default display, you can clear the name.
5. Click "Confirm" to finish the rename.

### Deleting an Agent

1. Find the target Agent in the Agent list.
2. Click the delete button on the right.
3. The page shows a confirmation prompt.
4. After you confirm, the system deletes the Agent and clears the related local history and file tree state.

### Bulk Duplication or Bulk Deletion

1. Click the bulk selection button at the top of the Agent list.
2. Check multiple Agents.
3. Click bulk duplicate or bulk delete as needed.
4. For bulk deletion, a confirmation prompt appears first.
5. After the bulk operation completes, the page shows the number of successes or failures and exits bulk mode.

## Feedback You Will See

- The rename window is titled "Rename Agent".
- After a successful rename, you will see a "Renamed successfully" message.
- Before deletion you will see a clear warning: the Agent cannot be recovered after deletion, and all history will be cleared.
- In node mode, duplicated Agent list items show the node they belong to, so you can confirm which node the copy landed on.
- If duplication, renaming, or deletion fails, the page shows the corresponding error message.
- After bulk duplicate and bulk delete finish, the page shows the number of successes and the number of failures.

## Notes

- Deletion cannot be undone; before confirming, check whether you still need to keep the Agent's history.
- After deletion, not just the list item disappears; the local history and some UI state related to the Agent are also cleaned up.
- Leaving the name empty during renaming is not an error; it restores the default display.
- In node mode, duplication may place the Agent on a remote child node, but your browser still accesses it through the master node, so you do not need to handle the forwarding chain manually.
- In bulk mode, clicking a list item is mainly for selection and does not switch the current Agent directly as in normal mode.
