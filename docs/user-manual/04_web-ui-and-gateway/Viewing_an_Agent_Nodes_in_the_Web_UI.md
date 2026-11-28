# Viewing an Agent's Node in the Web UI

## Use Cases

When you have enabled node mode, or need to confirm which node an Agent is actually running on, you can view node assignment through the Agent list and the current Agent info area in the Web UI. This helps you understand where requests are forwarded, and also makes it easy to troubleshoot whether a child node has properly connected to the master node.

## Steps

1. First make sure the current browser is connected to the master node Gateway.
2. In the Agent list on the left, look at the node label next to each Agent item.
3. After selecting an Agent, check the detailed info area of the current Agent as well.
4. If you just created or duplicated an Agent, you can check whether its node assignment matches expectations right after creation.

## Feedback You Will See

- In the Agent list, a node is usually shown as a separate label, e.g. a node tag with a 📍 icon.
- The current Agent area also shows the node the Agent belongs to.
- If an Agent does not explicitly show a child node, it generally runs on the master node, or the current interface treats it as the default master node.

## Notes

- Whether node information is visible depends on whether the current Gateway returns the Agent's `node_id`.
- In node mode, even if an Agent actually runs on a child node, the browser side usually still connects only to the master node; this is normal.
- If you expected an Agent to appear on a child node but the interface still shows the master node, first check whether a target node was selected at creation, and whether the master-child connection is healthy.
