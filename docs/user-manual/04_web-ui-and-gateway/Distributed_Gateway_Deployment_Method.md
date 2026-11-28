# Distributed Gateway Deployment Method

## Use Cases

When you need to deploy HaijunBot Web Gateway across multiple machines and access the Agents on all nodes through a single entry point, you can use the distributed gateway deployment mode. This mode suits the following scenarios:

- **Leveraging multiple machines**: spread computing tasks across multiple machines to make full use of cluster resources
- **Remote collaboration**: team members at different locations access a unified HaijunBot service entry point
- **Load sharing**: assign different types of Agents to run on different nodes
- **Environment isolation**: different nodes can be configured with different runtimes or tool sets

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                          Client Layer                           │
│  ┌──────────────┐   ┌──────────────┐                            │
│  │ Web Browser  │   │ Other Clients│                            │
│  └──────┬───────┘   └──────┬───────┘                            │
└─────────┼───────────────────┼───────────────────────────────────┘
          │                   │
          └────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Master Node (Master)                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    HaijunBot Web Gateway                    │   │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │   │  Agent Mgmt  │  │  Node Reg.   │  │  Routing     │   │   │
│  │   └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│    Child 1    │   │    Child 2    │   │    Child N    │
│  (Child 1)   │   │  (Child 2)   │   │  (Child N)   │
│ ┌──────────┐ │   │ ┌──────────┐ │   │ ┌──────────┐ │
│ │  Agent 1 │ │   │ │  Agent 3 │ │   │ │  Agent 5 │ │
│ │  Agent 2 │ │   │ │  Agent 4 │ │   │ │  Agent 6 │ │
│ └──────────┘ │   │ └──────────┘ │   │ └──────────┘ │
└──────────────┘   └──────────────┘   └──────────────┘
```

**How it works**:

- The master node provides the unified external access entry and maintains the registration information of all child nodes
- Child nodes connect to the master node over a WebSocket long connection and report their own status
- Clients only need to connect to the master node; it forwards requests automatically according to the node an Agent belongs to
- When creating an Agent you can specify a target node, and the Agent will run on that node

## Prerequisites

- All nodes (master and child) must have HaijunBot installed and an LLM platform configured
- The master node must be reachable by both clients and child nodes (network accessible)
- It is recommended to configure the same node secret (`--node-secret`) on all nodes to ensure secure communication

## Steps

### 1. Start the Master Node

Run the following on the master node machine:

```bash
export HAIJUNBOT_ADMIN_PASSWORD='your_password'
haijunbot-service run --node-mode master --host 0.0.0.0 --port 8000
```

**Parameter notes**:

- `--node-mode master`: run in master node mode
- `--host 0.0.0.0`: listen on all network interfaces (use `127.0.0.1` for local-only access)
- `--port 8000`: the listening port
- `HAIJUNBOT_ADMIN_PASSWORD` (environment variable): optional; sets the initial admin password (the `admin` account is created automatically on first startup; when not set, a random password is generated and printed to the log; see "Configuring the Gateway Authentication Password and the Access Policy When No Password Is Set")
- `--node-secret`: optional; sets the shared secret for inter-node communication

**Getting the node secret**:

The master node generates a node secret automatically on startup and saves it to `~/.haijunbot/node_mode/master_node_secret`. After the first startup, you can view the secret as follows:

```bash
# View the generated node secret
cat ~/.haijunbot/node_mode/master_node_secret
```

Child nodes must use the same secret when starting. If the master node does not specify the `--node-secret` parameter, the system generates one automatically; if specified, the given secret is used.

### 2. Start a Child Node

Run the following on each child node machine:

```bash
haijunbot-service run --node-mode child \
    --node-id worker-01 \
    --master-url ws://master-host:8000 \
    --node-secret your_secret_key
```

**Parameter notes**:

- `--node-mode child`: run in child node mode
- `--node-id worker-01`: the unique ID of the child node (required)
- `--master-url`: the WebSocket address of the master node (required)
  - Format: `ws://host:port` or `wss://host:port` (when using HTTPS)
  - Example: `ws://192.168.1.100:8000`
- `--node-secret`: the shared secret for inter-node communication (required)

**Example of starting multiple child nodes**:

```bash
# Child node 1
haijunbot-service run --node-mode child --node-id worker-01 --master-url ws://192.168.1.100:8000 --node-secret my_secret

# Child node 2
haijunbot-service run --node-mode child --node-id worker-02 --master-url ws://192.168.1.100:8000 --node-secret my_secret

# Child node 3 (use a different port to avoid conflicts)
haijunbot-service run --node-mode child --node-id worker-03 --master-url ws://192.168.1.100:8000 --node-secret my_secret --port 8001
```

### 3. Verify Node Registration

After starting a child node, you can verify its registration status as follows:

1. **Check the master node logs**: successful registration shows the child node information
2. **Check through the Web UI**:
   - Connect to the master node and open the "Create Agent" dialog
   - The "Target Node" dropdown should show all registered child nodes

### 4. Create and Run a Distributed Agent

#### Through the Web UI

1. Open the master node address in a browser (e.g. `http://master-host:8000`)
2. Click "Create Agent"
3. In the "Target Node" dropdown, select the child node where the Agent should run
4. After creation completes, the Agent runs on the specified child node

### 5. Managing Agents on Child Nodes

- **View running status**: in the master node's Web UI, you can see the list of Agents on all nodes, and each Agent shows the node it belongs to
- **Communication**: when interacting with an Agent on a child node, messages are automatically forwarded through the master node to the corresponding child node
- **Session restore**: Agent sessions on child nodes also support session restore

## Feedback You Will See

### When the master node starts

```text
🚀 Starting HaijunBot Web Gateway

  Gateway: http://0.0.0.0:8000 (PID: ...)
  Frontend: http://0.0.0.0:8000 (PID: ...)
  Node mode: master
```

### When a child node starts

```text
🚀 Starting HaijunBot Web Gateway

  Gateway: http://127.0.0.1:8000 (PID: ...)
  Frontend: not started in child mode
  Node mode: child
```

After a child node successfully connects to the master node, a successful connection message is shown.

### Node labels in the Web UI

- In the Agent list, each Agent shows the label of the node it belongs to (e.g. `master`, `worker-01`, etc.)
- When creating an Agent, the node picker lists all available nodes

## Config-File Deployment Method (recommended for production)

For production deployment, it is recommended to use config files together with process management tools such as systemd/supervisor.

### Master Node Config Example

Create the startup script `/opt/haijunbot/start-master.sh`:

```bash
#!/bin/bash
export HAIJUNBOT_ADMIN_PASSWORD="your_secure_password"
export HAIJUNBOT_NODE_SECRET="your_secret_key"
haijunbot-service run --node-mode master --host 0.0.0.0 --port 8000
```

### Child Node Config Example

Create the startup script `/opt/haijunbot/start-worker.sh`:

```bash
#!/bin/bash
export HAIJUNBOT_NODE_SECRET="your_secret_key"
haijunbot-service run --node-mode child \
    --node-id "$(hostname)" \
    --master-url "ws://master-host:8000" \
    --node-secret "${HAIJUNBOT_NODE_SECRET}" \
    --port 8000
```

### Managing with systemd (Linux)

**Master node service file** `/etc/systemd/system/haijunbot-master.service`:

```ini
[Unit]
Description=HaijunBot Web Gateway Master
After=network.target

[Service]
Type=simple
User=haijunbot
Environment="HAIJUNBOT_ADMIN_PASSWORD=your_password"
Environment="HAIJUNBOT_NODE_SECRET=your_secret_key"
ExecStart=/usr/local/bin/haijunbot-service run --node-mode master --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Child node service file** `/etc/systemd/system/haijunbot-worker.service`:

```ini
[Unit]
Description=HaijunBot Web Gateway Worker
After=network.target

[Service]
Type=simple
User=haijunbot
Environment="HAIJUNBOT_NODE_SECRET=your_secret_key"
ExecStart=/usr/local/bin/haijunbot-service run --node-mode child --node-id %H --master-url ws://master-host:8000 --node-secret ${HAIJUNBOT_NODE_SECRET}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enabling the services**:

```bash
# Master node
sudo systemctl enable haijunbot-master
sudo systemctl start haijunbot-master

# Child node
sudo systemctl enable haijunbot-worker
sudo systemctl start haijunbot-worker
```

## Deploying with Docker Compose

For containerized deployment, you can use Docker Compose:

**`docker-compose.master.yml`** (master node):

```yaml
version: "3.8"
services:
  haijunbot-master:
    image: ghcr.io/takebox/haijunbot:latest
    ports:
      - "8000:8000"
    environment:
      - HAIJUNBOT_ADMIN_PASSWORD=${HAIJUNBOT_ADMIN_PASSWORD}
      - HAIJUNBOT_NODE_SECRET=${HAIJUNBOT_NODE_SECRET}
    command: >
      haijunbot-service run --node-mode master
          --host 0.0.0.0
          --port 8000
          --node-secret ${HAIJUNBOT_NODE_SECRET}
    volumes:
      - ~/.haijunbot:/home/haijunbot/.haijunbot
```

**`docker-compose.worker.yml`** (child node):

```yaml
version: "3.8"
services:
  haijunbot-worker:
    image: ghcr.io/takebox/haijunbot:latest
    environment:
      - HAIJUNBOT_NODE_SECRET=${HAIJUNBOT_NODE_SECRET}
      - NODE_ID=${NODE_ID}
      - MASTER_URL=${MASTER_URL}
    command: >
      haijunbot-service run --node-mode child
          --node-id ${NODE_ID}
          --master-url ${MASTER_URL}
          --node-secret ${HAIJUNBOT_NODE_SECRET}
    volumes:
      - ~/.haijunbot:/home/haijunbot/.haijunbot
```

**Startup commands**:

```bash
# Master node
docker-compose -f docker-compose.master.yml up -d

# Child node
export NODE_ID=worker-01
export MASTER_URL=ws://master-host:8000
docker-compose -f docker-compose.worker.yml up -d
```

## Notes

### Security

1. **Password protection**: in production, set an admin login password (environment variable `HAIJUNBOT_ADMIN_PASSWORD`) to prevent unauthorized access
2. **Node secret**: all nodes should be configured with the same `--node-secret` for secure inter-node communication
3. **Network security**: ensure the network between the master and child nodes is secure; use a VPN or private network if necessary
4. **HTTPS/WSS**: if deploying on the public internet, it is recommended to use a reverse proxy (e.g. Nginx) to enable HTTPS/WSS

### Network Requirements

1. **Open ports**: make sure the master node's listening port is open to clients and child nodes
2. **Firewall configuration**: check the firewall rules to allow WebSocket communication between nodes
3. **Long-lived connections**: child nodes keep a WebSocket long connection to the master node; unstable networks may cause disconnects and reconnects

### High Availability

1. **Current limitation**: only a single-master architecture is supported, and the master node is a single point of failure
2. **Failure recovery**: child nodes reconnect automatically after disconnecting, and Agent state is re-synced
3. **Data persistence**: it is recommended to configure persistent storage to save Agent session data

### Version Compatibility

1. The master and child nodes should use the same version of HaijunBot
2. Version mismatches may cause communication protocol incompatibility

### Resource Management

1. Each child node can host multiple Agents, but allocate them reasonably according to machine resources
2. Monitor the CPU and memory usage of child nodes
3. Large tasks are best assigned to nodes with more abundant resources

## Troubleshooting

### A Child Node Cannot Connect to the Master Node

1. Check whether the master node address and port are correct
2. Confirm the master node firewall allows the child node IP to access it
3. Check whether `--node-secret` is consistent across all nodes
4. Review the log output of the master and child nodes

### Agent Creation Fails

1. Confirm the target child node has successfully registered with the master node
2. Check whether the child node has enough resources to create a new Agent
3. Check the child node logs for detailed error information

### Message Forwarding Fails

1. Check the connection status between the child node and the master node
2. Confirm the mapping between Agent IDs and node IDs is correct
3. Restart the relevant services to try to recover

## Related Documents

- [Start the Web Gateway Service](./Starting_the_Web_Gateway_Service.md)
- [Node Mode Deployment and Integration Handbook](./Node_Mode_Deployment_and_Integration_Handbook.md)
- [View an Agent's Node in the Web UI](./Viewing_an_Agent_Nodes_in_the_Web_UI.md)
