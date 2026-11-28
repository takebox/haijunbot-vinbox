# haijunbot-daemon Auto-Update Protocol Design (v1)

Scope: **Windows and Linux only** (macOS excluded).

## 1. Goals

1. The daemon reports its **version number** and **architecture** (GOOS/GOARCH) to the gateway.
2. The gateway compares the reported information with the "latest release version" to determine whether an update is needed.
3. When an update is needed, the gateway sends the daemon a GitHub release download link (including sha256).
4. The daemon silently downloads, verifies, atomically replaces its own executable, and restarts the service.
5. After restart, the **Token must be preserved**.

## 2. Current Facts (research findings, with evidence)

- Daemon hello frame already reports: `extension_version` (version number, `daemon/internal/wsclient/client.go:278`),
  `system_info` (`client.go:286-292`), `build_info` (`client.go:308-309`).
- `build_info` already contains `version`/`os`/`arch`/`go_version`/`exe_path`/`exe_mtime`/`commit`/`pid`
  (`daemon/internal/buildinfo/buildinfo.go:135-152`)——**the architecture is already reported in `build_info.os` / `build_info.arch`**.
- The gateway-side session already stores `daemon_version` (taken from `extension_version`), `build_info`, `system_info`, `platform`
  (`src/haijunbot/haijunbot_web_gateway/daemon_capability_manager.py:184-186`).
- The gateway daemon `hello_ack` currently **only returns** `{type, session_id, heartbeat_interval}` (`daemon_capability_manager.py:208-214`),
  without any version comparison result.
- The daemon's `OnHelloAck` callback already exists but `latest` is always empty (`client.go:374-377`).
- Daemon WS message dispatch: `client.go:359-388`, already recognizes `pong`/`hello_ack`/`command`/`capability.list`/`capability.call`.
- Gateway daemon WS message loop: `daemon_capability_manager.py:217-242`, already recognizes
  `capability.list.result`/`capability.call.result`/`ping`/`hello`.
- **Token is memory-only, never persisted to disk** (`daemon/internal/auth/store.go:1-15`); it becomes invalid when the process exits.
- Service restart capability is already available: `internal/service/service.go:44-57` (`Restart()`),
  implemented in `systemd_linux.go:161` / `task_windows.go:142`.
- Fixed install path: `internal/service/install_dir.go` (`~/.haijunbot/bin/haijunbot-daemon[.exe]`).
- GitHub Release artifact naming (`.github/workflows/release-daemon.yml:100-107`):
  - `haijunbot-daemon_linux_amd64.tar.gz`
  - `haijunbot-daemon_linux_arm64.tar.gz`
  - `haijunbot-daemon_windows_amd64.zip`
  - `haijunbot-daemon_windows_arm64.zip`
  - Download URL: `https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>`

## 3. Protocol Design (v1)

### 3.1 Reuse the existing hello, add no new reporting frame

Architecture and version **are already reported in hello**, so no new field or new message type is needed. The gateway side only needs to read
`build_info.os` / `build_info.arch` (falling back to `platform` and `system_info` when missing).

> Compatibility: when an old daemon's `build_info` is empty, the gateway treats it as "no architecture information → skip update determination",
> without affecting the connection or existing capabilities.

### 3.2 Send the update determination result with hello_ack (reusing the existing frame)

Add an optional field to `hello_ack` (**add only, no modification**, old daemons can just ignore it):

```jsonc
{
  "type": "hello_ack",
  "session_id": "...",
  "heartbeat_interval": 20,
  // added (optional):
  "daemon_update": {
    "available": true, // whether an update is needed
    "latest_version": "v1.2.0", // latest version (tag)
    "current_version": "v1.1.0",
    "url": "https://github.com/<owner>/<repo>/releases/download/v1.2.0/haijunbot-daemon_linux_amd64.tar.gz",
    "sha256": "…64-digit lowercase hex…", // optional; when missing the daemon skips verification and logs a warning
    "size": 12345678, // optional; byte count, used for progress/verification
    "asset": "haijunbot-daemon_linux_amd64.tar.gz",
    "note": "…", // optional; release notes summary
  },
}
```

- `available=false` or the field missing → the daemon does nothing (equivalent to current behavior).
- Platform/architecture mismatch (no corresponding artifact) → the gateway returns `available=false` and explains the reason in `note`.

### 3.3 Update status receipt (new message type, one-way)

After performing the update, the daemon sends a receipt to the gateway (**optional**, for the gateway/frontend to display progress; the gateway does not wait or block):

```jsonc
// daemon → gateway
{
  "type": "daemon.update.status",
  "state": "downloading" | "verifying" | "applying" | "restarting" | "failed",
  "version": "v1.2.0",
  "error": ""            // fill in the reason when state=failed
}
```

The gateway adds an `elif msg_type == "daemon.update.status":` branch in the `daemon_capability_manager.py` message loop,
only logging / updating session fields, **without replying**. Old gateways only debug-ignore unknown types (`daemon_capability_manager.py:241-242`),
so it is naturally compatible.

### 3.4 Download and verification

- Download: `net/http` GET `url`, with `User-Agent: haijunbot-daemon/<version>`, timeout (e.g., 5 minutes).
- Verification: if `sha256` is non-empty, compute sha256 on the fly and compare; mismatch → discard and report `failed`.
- Unpack: `.tar.gz` (Linux) / `.zip` (Windows) using the standard library `archive/tar`+`compress/gzip` / `archive/zip` to extract
  `haijunbot-daemon[.exe]`.

### 3.5 Atomic replacement and restart

1. Write the extracted new binary to a **temporary file in the same directory** (`~/.haijunbot/bin/.haijunbot-daemon.new-<pid>`), `Chmod 0755`.
2. Verify the temporary file is executable (optional: `--version` probe).
3. Atomically replace the current executable:
   - Linux: `os.Rename(tmp, target)` (same directory, same filesystem, atomic).
   - Windows: a running exe cannot be overwritten/renamed, so the **helper process** approach is used—
     start a detached child process (`haijunbot-daemon self-update-apply --src <tmp> --dst <target> --restart`);
     after the parent process exits, the helper completes the replacement and calls `service.Restart()`.
4. Restart: `service.New().Restart()` (Linux systemd --user / Windows scheduled task).
   - If it is currently **not running as a service** (no service definition), it degrades to: after replacing the file, the helper re-launches
     the `run` subcommand (preserving the original command-line arguments).

### 3.6 Token preservation scheme (key)

The Token is currently **memory-only, not persisted to disk** (`auth/store.go:1-15`). After a restart the Token is lost.

**Scheme (recommended, secure default)**: before updating, the daemon **temporarily persists** the current credentials to
`~/.haijunbot/daemon/update-token.json` (permissions 0600), with fields:

```jsonc
{ "gateway": "https://hjb-ai.cn", "token": "…", "name": "…", "expires_at": 0 }
```

- After restart, the daemon reads this file on startup: if it exists and has not expired, it uses it to restore the `store` and actively calls `manager.Connect`,
  then **immediately deletes the file** (single-use, avoiding long-term persistence).
- If the file does not exist / has expired / fails to parse → use the existing path (wait for the frontend to push).
- This file exists only within the "self-update" window; it is a **temporary credential relay**, not long-term persistence;
  if the user does not accept persisting to disk, auto-update can be disabled (see 3.7), in which case this file is not produced.

> Alternative (zero disk persistence): after the update, rely on the frontend being online to re-push (`App.vue:16924` re-push on page load, `:16898` push on token change).
> Drawback: when the frontend is offline, the daemon remains unauthenticated until the user next opens the web page.
> **Decision: use the temporary disk persistence scheme by default**, ensuring the daemon stays online after "silent update + restart"; and clearly inform in the docs and logs.

### 3.7 Unconditional update and deduplication

- **No switch**: the daemon must stay on the same version as the gateway; `daemon_update.available=true` means execute the update;
  no `auto_update_daemon` setting is provided (user's position: unconditional, synchronized with the gateway's own version).
- **Deduplication** (triggered on every WS handshake; without a constraint, a failed update would retry infinitely with reconnects):
  1. **No retry for same-version failures + exponential backoff**: consecutive failures back off 1min → 5min → 30min,
     skipped within the backoff window; the counter resets when the target version changes.
  2. **Circuit breaker across restarts**: before updating, write "updating to version X" to
     `~/.haijunbot/daemon/update-attempt.json` (0600, `in_progress=true`); if the new version
     fails to start after replacement, the new process reads this marker on startup and its own version is still the old one → judged as a restart loop, trip the circuit breaker for auto-update and alert;
     it recovers automatically after the gateway releases an updated version (target version changes). Delete the file after a successful update.
  3. See `internal/selfupdate/attempt_state.go` for the implementation (`ShouldSkipUpdate` / `BackoffFor` /
     `NormalizeVersion`), and `maybeAutoUpdateDaemon` in `cmd/haijunbot-daemon/main.go` for the wiring.
- Version comparison must be **normalized** (strip leading `v`/`V` + trim): the gateway version comes from `haijunbot.__version__` (e.g., `6.0.0`),
  and the daemon version is build-injected (e.g., `v5.0.5`); without normalization they would be misjudged as different versions → infinite restart loop.
- Only allow downloads from **HTTPS** GitHub domains (whitelist `github.com` / `objects.githubusercontent.com`),
  preventing SSRF / man-in-the-middle.
- An update failure is only logged and never affects the current connection and capabilities.

## 4. Gateway-side "latest version" data source

v1 uses a **config-driven** approach (zero new dependencies, works offline):

- The gateway config file (or environment variables) provides:
  - `daemon.latest_version` (e.g., `v1.2.0`)
  - `daemon.release_base_url` (default `https://github.com/<owner>/<repo>/releases/download`)
  - `daemon.assets` (optional, explicit mapping `os/arch → {asset, sha256}`; assembled by naming rules when absent)
- Later it can be extended to "fetch GitHub releases/latest and cache", but this is **out of scope for v1** (requires external network and a caching strategy).

Comparison rule: `current_version != latest_version` is considered to need an update (simple string comparison;
if semantic comparison is later needed, introduce `packaging` or a custom implementation).

## 5. Implementation Task Breakdown

| Task | Content                                                                        | Status                                                        |
| ---- | --------------------------------------------------------------------------- | ----------------------------------------------------------- |
| T1   | daemon side: unconditional auto-update (no switch) + deduplication (backoff + cross-restart circuit breaker)            | ✅ Implemented                                                   |
| T2   | daemon side: parse `hello_ack.daemon_update`, implement download/verify/unpack/atomic replacement/restart | ✅ Implemented                                                   |
| T3   | daemon side: Windows helper subcommand `self-update-apply`                        | ✅ Implemented (not verified on real hardware)                                     |
| T4   | daemon side: Token temporary disk persistence and startup recovery (single-use)                               | ✅ Implemented                                                   |
| T5   | gateway side: `hello_ack` sends `daemon_update`; add `daemon.update.status` branch  | ✅ Implemented                                                   |
| T6   | end-to-end verification (httptest simulated download + fake service restart) and docs                          | 🔶 Partial (httptest covered; fake service restart and Windows real hardware not verified) |

### 5.1 Daemon-side implementation highlights (corresponding to T1–T4)

- Update core: `internal/selfupdate/` (`ParseUpdateInfo` / `ValidateDownloadURL` whitelist /
  `Download` streaming sha256 / `ExtractBinary` / `Apply` / platform `restart_*.go`).
- Deduplication: `internal/selfupdate/attempt_state.go` (`ShouldSkipUpdate` centrally determines backoff and circuit breaking,
  state persisted to `~/.haijunbot/daemon/update-attempt.json`).
- Upper-layer wiring: `internal/wsclient/client.go` parses `hello_ack.daemon_update` and invokes the
  `Options.OnDaemonUpdate` callback; `manager.go` provides `OnGatewayDaemonUpdate` with a gateway dimension;
  `maybeAutoUpdateDaemon` in `cmd/haijunbot-daemon/main.go` executes unconditionally (only constrained by deduplication).
- helper: the `self-update-apply` subcommand of `cmd/haijunbot-daemon` (on Windows it polls and replaces after the parent process exits).
- Token relay: `internal/selfupdate/token.go`, writes `~/.haijunbot/daemon/update-token.json` (0600) before updating,
  reads it on startup and **immediately deletes** it, then actively reconnects via `manager.ConnectWithName`.
- Scope: **Windows and Linux only**; macOS is not implemented (`restart_other.go` / `apply_other.go` only ensure it compiles).

## 6. Open Items / Risks

- Replacing a running exe on Windows must rely on the helper process, **not verified on real hardware** (this machine is Linux; only cross-compilation passed).
- Temporary Token disk persistence is in tension with the "no disk persistence" principle and needs user confirmation (see 3.6).
- The gateway "latest version" source in v1 is config-driven and requires manually updating the config after a release.
- The `daemon.update.status` receipt (T5) is not yet wired up: the `selfupdate.Options.Report` hook is ready,
  and the send logic will be injected by `main.go` once gateway-side support is available.
