# Login Methods for Headless Hosts: the `login` Subcommand and the Web Login Service

This document describes how to let `haijunbot-daemon` obtain gateway credentials and establish a connection
on a host without a graphical interface (typically a Linux server without a desktop).

Background: normally credentials are pushed to the local daemon by the **browser extension** (on page load, the JWT
is handed to `127.0.0.1:17800` via `POST /api/auth`). A headless host has no browser, so this path does not work,
therefore two alternative paths are provided:

| Method                    | Use case                         | Entry                                 |
| ----------------------- | -------------------------------- | ------------------------------------ |
| `login` subcommand          | Can SSH into the host, interactive input possible    | `haijunbot-daemon login`                |
| Web login service (`webui`) | Can only be accessed from the browser of **another machine** | `http://<host IP>:17801/` (default port) |

Both paths ultimately use the **same "write credentials + initiate connection"** logic, fully equivalent to the browser extension push.

---

## 1. The `haijunbot-daemon login` subcommand

### 1.1 Usage

```bash
haijunbot-daemon login [-gateway <gateway address>] [-u <username>] [-listen <local listen address>] [-config <config file>]
```

- `-gateway`: gateway address, overrides `gateway:` in the config file. Errors if left empty and not set in the config either.
- `-u`: login username. When left empty, prompts interactively.
- `-listen`: local API listen address, overrides `listen:` in the config file; falls back to
  `127.0.0.1:17800` when both are empty. Credentials are pushed to this address.
- `-config`: config file path, defaults to `~/.haijunbot/daemon/config.yaml`.

**The password is always obtained via interactive hidden input; no command-line argument such as `-p` is provided**—to avoid the password
entering the shell history, the process command line (visible via `ps`), and logs.

### 1.2 Interactive flow

```text
$ haijunbot-daemon login -gateway http://gateway.example.com:8000
Username: admin
Password:            # not echoed while typing
[daemon] Logging in to gateway http://gateway.example.com:8000 ...
[daemon] Login successful: admin (token e2e1...efgh)
[daemon] Credentials pushed to local background service (127.0.0.1:17800); the daemon will connect to the gateway
```

- The token is printed only in **masked** form (first and last 4 characters, middle omitted); the full credentials are not logged.
- After a successful login, `{gateway, token, name}` is pushed to `POST http://<listen>/api/auth`;
  `name` is passed as an empty string, meaning to keep the daemon's existing terminal name under that gateway.

### 1.3 Error messages

| Situation             | Output                                                                    |
| ---------------- | ----------------------------------------------------------------------- |
| Incorrect username or password | `Login rejected: Invalid username or password` (gateway original text)                  |
| Gateway unreachable       | `Login request failed (...): connection refused`                               |
| Gateway not configured       | `Gateway address not specified; specify it with -gateway, or configure gateway in the config file ... first` |
| Local service not running   | Push fails with a hint (the login itself has already completed)                                    |

### 1.4 Implementation location

- `daemon/internal/login/login.go`: `Login()` / `PushAuth()` / `NormalizeGateway()` / `MaskToken()`.
- `daemon/internal/login/password_{linux,windows,other}.go`: platform implementations of hidden input
  (Linux uses `ioctl` to turn off `ECHO`; Windows uses `SetConsoleMode` to turn off `ENABLE_ECHO_INPUT`).
- `cmdLogin()` in `daemon/cmd/haijunbot-daemon/main.go`.

---

## 2. Web Login Service (`webui`)

### 2.1 Purpose

When the operator **cannot SSH** into the target host (or does not want to use the command line), they can access
the Web login page on the target host from another machine's browser, enter "gateway address + username + password" on the page, and the daemon
logs in to the gateway on their behalf and establishes the connection directly.

### 2.2 Configuration

| Config item                                    | Default          | Description                 |
| ----------------------------------------- | --------------- | -------------------- |
| `web_listen` (config file)                  | `0.0.0.0:17801` | Web login service listen address |
| `-web-listen` (command line, shared by run/install) | Same as left            | Overrides the config file         |

**Passing an empty string to `-web-listen` disables this service** (different from "providing the argument": when not provided, the value
in the config file is used). Example:

```bash
# Disable the Web login service
haijunbot-daemon run -web-listen ""

# Listen only on loopback (accessible only from the local browser)
haijunbot-daemon run -web-listen 127.0.0.1:17801
```

On startup, if bound to a non-loopback address, the log prints a security warning:

```text
[daemon] Web login page: http://0.0.0.0:17801/ (bound to a non-loopback address, use only on trusted internal networks)
```

### 2.3 API

| Method | Path         | Description                                                          |
| ---- | ------------ | ------------------------------------------------------------- |
| GET  | `/`          | Embedded login page (`Cache-Control: no-store`; any non-root path returns 404)     |
| POST | `/api/login` | Request body `{gateway, username, password, name?}`, logs in on their behalf and connects |

`POST /api/login` returns on success:

```json
{
  "success": true,
  "message": "Login successful; the daemon has connected to the gateway and this page can be closed",
  "user": "admin"
}
```

On failure it returns 400 with a readable error (e.g., `Please fill in the gateway address` / `Please fill in the username` /
`Please fill in the password` / the original login error returned by the gateway), **the error message does not contain the password**.

Request body limit 64 KiB (`http.MaxBytesReader`).

### 2.4 Implementation location

- `daemon/internal/webui/server.go`: `Server` / `New()` / `Handler()`.
- `daemon/internal/webui/index_html.go`: embedded login page.
- `daemon/cmd/haijunbot-daemon/main.go`: started in `runDaemon()` according to `cfg.WebListen`
  (independent of the local API service, sharing the same `auth.Store` and `wsclient.Manager`).

---

## 3. ⚠️ Security Warning (must read)

The Web login service is **Scheme A**: login only, no additional protection. Known risks:

1. **Plaintext transmission**: the page and API use HTTP, so the password is transmitted in plaintext within the LAN.
2. **No authentication**: anyone who can connect to the port can attempt to log in (and may brute-force the password).
3. **Listens externally by default**: defaults to `0.0.0.0:17801`, i.e., listening on all network interfaces.

Therefore:

- **Should only be used on a trusted internal network**, together with a firewall restricting the source subnet;
- When this feature is not needed, disable it with `-web-listen ""` or by leaving `web_listen` empty;
- If only used locally, switch to listening on `127.0.0.1:17801`.

> Per the user's request, **no authentication was added** this round; do not enable it on an untrusted network.

---

## 4. Credential Storage and Lifecycle

- Credentials (JWT) are **memory-only, never persisted to disk** (`daemon/internal/auth/store.go`),
  they become invalid when the process exits, and after a restart a new login is required (or a re-push by the browser extension).
- Multiple gateways coexist: `Store` is keyed by gateway address, so logging in to a new gateway does not overwrite existing ones.
- On the gateway side, the JWT has **no expiration time** by default (`HAIJUNBOT_JWT_EXPIRE_HOURS` defaults to `0`),
  to meet the daemon's need for long-term connections.

---

## 5. Known Limitations and Unverified Items

- **Not verified**: the **HTTPS** scenario with a real gateway (only end-to-end verified with an HTTP mock).
- **Not verified**: the actual behavior of hidden password input on Windows (only cross-compilation passed).
- Both the `login` subcommand and the Web login service depend on **the local daemon already running** (the push target);
  if the local service is not started, the login succeeds but the push fails.
