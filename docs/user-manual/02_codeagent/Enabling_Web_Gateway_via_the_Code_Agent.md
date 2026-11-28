# Enabling the Web Gateway Service via the Code Agent

## When to Use

When you want to also open a local Web Gateway entry when starting the code agent, letting external pages or other local clients connect to the current session via WebSocket, you can enable this service at startup.

## Steps

1. Open a terminal in the project directory.
2. Enter the following command, then press Enter:

   `hca --web-gateway`

3. If you want to specify the listening port, you can change it to:

   `hca --web-gateway --web-gateway-port 8001`

4. If you need to set a login password for the gateway, you can first set the admin initial password with the environment variable `HAIJUNBOT_ADMIN_PASSWORD`, then start it:

   ```bash
   export HAIJUNBOT_ADMIN_PASSWORD='<your-password>'
   hca --web-gateway
   ```

   On first startup an `admin` account is automatically created, and its initial password is the value of this environment variable (if it is not set, a random password is generated and printed to the log; see "Configuring the Gateway Authentication Password and Access Policy When No Password Is Set").

5. After startup is complete, the system first prepares the code agent environment, then starts the Web Gateway service on the local machine.
6. After that, you can let a local client that supports this entry connect to the WebSocket address shown in the terminal.

## Prompts and Feedback You Will See

- After the service starts successfully, the terminal shows a local connection address like `ws://127.0.0.1:port/ws`.
- If you set authentication information, the system enables the corresponding authentication according to the current startup method.
- If the gateway fails to start, the terminal shows a warning message, and the code agent continues to run or end according to the original flow, depending on where the failure occurred this time.
- After enabling, a local status query entry is also provided, used to view the current execution status.

## Notes

- This is a local listening address, and by default it is not a public address open to the external network.
- If the port is already in use, or the local environment does not meet the startup conditions, the gateway may not start normally.
- `--web-gateway` only additionally starts a service and does not replace your current terminal interaction method; you can still run tasks in the terminal as usual.
- If you do not have a clear Web access requirement, you usually do not need to additionally enable this option.
