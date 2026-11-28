# Starting the Web Gateway Service

## Use Cases

When you want to use the HaijunBot Web UI through a browser instead of only operating in the terminal, you need to start the Web Gateway service first. This service provides the browser access entry and forwards the subsequent web connections, authentication, and operation requests.

## Steps

1. In the terminal, type the following command and press Enter: `haijunbot-service run`
2. To use the default config, simply run it; by default it listens on the local address `127.0.0.1` and port `8000`.
3. To change the listening address or port, use a command like: `haijunbot-service run --host 0.0.0.0 --port 9000`
4. If you want login to be required before the browser connects, set the initial admin password via the environment variable `HAIJUNBOT_ADMIN_PASSWORD` first, for example:

   ```bash
   export HAIJUNBOT_ADMIN_PASSWORD='your_password'
   haijunbot-service run
   ```

   On first startup, the `admin` account is created automatically, and its initial password is the value of this environment variable (when not set, a random password is generated and printed to the log; see "Configuring the Gateway Authentication Password and the Access Policy When No Password Is Set" for details).

5. After submitting the command, keep this terminal window open so the Web Gateway service keeps running.
6. Once the service is running, open the corresponding web page in a browser, log in with a username + password, and connect.

## Feedback You Will See

- On startup, the terminal shows:
  - The Gateway listening address and port
  - The Frontend listening address and port
  - The current Node mode

- After a successful start, the service keeps running in the current terminal and does not exit immediately.
- When the browser connects, you need to enter a username (initially `admin`) and a password to complete the login.

## Additional Node Mode Notes

If you are using multi-node deployment, you can add the `--node-mode` parameter when starting the Gateway so that the current Gateway runs as a master node or a child node.

### Starting as a Master Node

- Example command: `haijunbot-service run --node-mode master`
- Typical use: the current node provides the unified external entry, and browsers and web clients all connect to this master node.
- After startup, the master node not only manages local Agents but also maintains the registered child node information.

### Starting as a Child Node

- Example command: `haijunbot-service run --node-mode child --node-id worker-01 --master-url ws://master-host:8000 --node-secret your_secret`
- Typical use: the current node is not the unified access entry; instead it connects to a master node and hosts remote Agents.
- After a child node starts, it establishes a long-lived connection with the master node, and the master node exposes the Agent capabilities uniformly.

### Recommendations

- For single-node deployment, continue starting the old way; if the current version requires an explicit mode, use `--node-mode master`.
- For multi-node deployment, start the master node first, then start child nodes and confirm they have connected successfully.
- Browsers and web clients usually connect to the master node, not directly to child nodes.

## Notes

- This is a terminal startup step, not an operation inside the browser page.
- When `HAIJUNBOT_ADMIN_PASSWORD` is not set, the system generates a random admin password and prints it to the service log; use it for the browser login, and change it right after the first login.
- While the Web Gateway is running, the terminal process must stay alive; if you close the terminal that started it, browser connections are usually interrupted too.
- If you only listen on `127.0.0.1`, it is usually suitable only for local access.
- In node mode, the master node and child nodes must be network-reachable; if a child node cannot connect to the master node, the browser side will not see the Agents on that node.
