# Node Mode Deployment and Integration Handbook

## Use Cases

When you are ready to deploy HaijunBot Web Gateway in a master node / child node layout and want to verify that the browser and the web front end can create and access Agents per node, you can use this handbook to complete a minimal deployment and integration.

## Deployment Goals

- Start one master node Gateway
- Start one or more child node Gateways
- Have the child nodes successfully connect to the master node
- View the node list through the master node
- Create Agents per node through the web front end
- Verify that access to Agents on remote child nodes is forwarded by the master node

## Steps

### 1. Start the Master Node

1. Run the Web Gateway on the master node machine.
2. Example: `haijunbot-service run --node-mode master`
3. For long-running operation, install it as a systemd service with `haijunbot-service install --node-mode master`, then start the service with `haijunbot-service start master`.

### 2. Start a Child Node

1. Run the Web Gateway on the child node machine.
2. Example: `haijunbot-service run --node-mode child --node-id worker-01 --master-url ws://master-host:8000 --node-secret your_secret`
3. For long-running operation, install it as a systemd service with `haijunbot-service install --node-mode child --node-id worker-01 --master-url ws://master-host:8000 --node-secret your_secret`, then start the service with `haijunbot-service start child`.

### 3. Verify Child Node Registration

1. Confirm the child node appears via the node status API provided by the master node, or through the front-end node list.
2. If the master node cannot see the child node, first check:
   - Whether the master and child node networks can reach each other
   - Whether the child node has successfully logged in to the master node
   - Whether the master node and child node run compatible versions

### 3.1 Viewing the Version of Each Node

Each child node reports its own actual running HaijunBot version in its heartbeat; after the master node aggregates this, you can view it as follows:

- **API**: `GET /api/node/status` (requires authentication); each node in the returned `data.nodes` contains a `version` field;
  the `master` version is filled in by the master node itself, and `data.version` is the master node's own version.
- **Front end**: the lobby page shows the node version below each node enclosure.
  If a node's version differs from `master`, the version number is highlighted in **red**, indicating that this node has not been updated to the same version.

> Note: the version number comes from the `haijunbot.__version__` actually running on each node. When an older child node does not report a version,
> its `version` is empty, the front end shows no version number, and it will not be misjudged as a "version mismatch".

### 4. Integration with the Web Front End

1. Connect the browser to the master node.
2. Open the Create Agent dialog.
3. Select a child node in "Target Node".
4. After creating the Agent, confirm that the node label appears in the list.
5. Open that Agent and keep sending messages to confirm normal interaction.

## Feedback You Will See

- The master node shows the registered child node information.
- Agents created on a child node show the corresponding `node_id`.
- The browser only needs to connect to the master node, but can access Agents on child nodes transparently.

## Integration Checklist

- Whether the master node started successfully
- Whether the child node started successfully
- Whether the child node appears in the master node's node list
- Whether the web front end can select a target node

- Whether an Agent created on a child node shows the correct node assignment
- Whether message interaction with a child node's Agent works normally
- Whether node assignment after duplicating an Agent matches expectations

## Notes

- In single-node mode, you can continue to treat the current node as the master node.
- If a child node cannot connect, the client side usually only sees Agents on the master node.
- Token alignment and the master-child long connection are internal system mechanisms and usually need no manual intervention in everyday use.
- If real end-to-end integration has not been performed yet, mark the result as "Documentation and static adaptation complete, pending on-device integration verification".
