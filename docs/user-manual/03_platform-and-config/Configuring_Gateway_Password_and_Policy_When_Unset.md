# Configuring the Gateway Auth Password and the Access Policy When No Password Is Set

## Use Cases

The HaijunBot Web Gateway authenticates using a **username + password** account system. On first startup it automatically creates an `admin` administrator account whose initial password comes from the environment variable `HAIJUNBOT_ADMIN_PASSWORD`. If you want to customize the initial password, understand the behavior when no password is set, or manage multiple users, you can refer to this document.

## Steps

### 1. Set the admin initial password

Before starting the Web Gateway service, first set the environment variable:

```bash
export HAIJUNBOT_ADMIN_PASSWORD='your-strong-password'
```

Then start the service (for example `haijunbot-service run` or the corresponding systemd/docker service).

### 2. First login

1. Open the Web interface and fill in the connection dialog:
   - Username: `admin`
   - Password: the `HAIJUNBOT_ADMIN_PASSWORD` set above
   - Gateway address: `ws://your-domain:8000` or `wss://example.com:8000`
2. After a successful login, you can enter the main interface.
3. **After the first login, it is recommended to change the admin password immediately**: change it in "Settings → Change Password"; an administrator can also reset any user's password in the top bar "Manage → User Management".

### 3. Manage multiple users (optional)

An administrator can, in the top bar "Manage → User Management":

- Create a new user (you can specify whether they are an administrator)
- Assign permission groups to users
- Reset user passwords
- Edit or delete users

## Behavior When No Password Is Set

- If `HAIJUNBOT_ADMIN_PASSWORD` is **not set** at startup, the system **automatically generates a random password** and prints it to the service log.
- How to view it (taking a systemd user service as an example):

  ```bash
  journalctl --user -u haijunbot-master -f
  ```

- You will see a prompt in the log like: `No HAIJUNBOT_ADMIN_PASSWORD set, generated random admin password: xxxxxxxx`, where `xxxxxxxx` is the admin initial password for this run.

## Prompts and Feedback You Will See

- On login, if the username or password is wrong, the interface returns an authentication failure prompt.
- After a successful login, the front end stores the session credential, and subsequent requests automatically carry the authentication information.
- Failed logins are counted (`login_fail_count`), but the system **does not automatically lock** the account; to lock it, an administrator can manually change the user's status to "Locked" or "Disabled" in "Manage → User Management".

## Notes

- The authentication method is a user account system based on `users.json` (stored under `auth/` in the HaijunBot data directory), and is **not** some switch in the config file.
- `HAIJUNBOT_ADMIN_PASSWORD` only takes effect when the **admin user is first created**; if admin already exists, changing the environment variable does not automatically override the existing password — reset it via "Change Password" or "User Management".
- Please use a strong password and keep it safe; do not run in production with a default/random password for a long time.
- Capabilities such as multiple users and permission groups are provided by the "Manage" entry in the Web interface; refer to the current version's interface for specifics.
