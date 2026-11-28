---
name: daemon_windows_hot_replace
description: Triggered when there is a need to replace the running haijunbot-daemon executable on a real Windows machine (hot replacement/temporary version deployment/swap in a newly compiled artifact). Triggered whenever the user mentions "replace the daemon", "swap the daemon exe", "update the daemon binary", "hot-replace the service", "temporary version deployment", "self-update-apply", or "helper replacement". Not triggered: daemon replacement on Linux/macOS (can rename directly); only compiling the daemon without replacement; only restarting the daemon service; using the daemon's windows.* capabilities to operate desktop programs (use the haijunbot_daemon_windows rule).
---

# Hot-replacing the haijunbot-daemon executable on Windows

## Rule Introduction

On a **real Windows machine**, swap the running `haijunbot-daemon.exe` for a new version (newly compiled artifact, temporary version, rolled-back version) **without interrupting the service**. The core difficulty: **Windows does not allow overwriting or renaming a running exe** (the file is exclusively locked), so you must use a helper child process that "acts after the parent process exits" to complete the replacement.

This rule follows **only one path**: **the target machine's daemon executes `fs.transfer.pull` to pull the compiled artifact from the gateway node (the node where the Agent runs)**.

| Path                             | New exe source           | Trigger/execution method                              | Applicable scenario                                          |
| -------------------------------- | ------------------------ | ----------------------------------------------------- | ------------------------------------------------------------ |
| **Target machine daemon pulls from the gateway node** | **Compiled artifact on the gateway node** | Target machine daemon executes `fs.transfer.pull` to pull from the gateway node | Agent compiles the exe on this node (the gateway node), and the target machine is another remote machine |

**Why use only this path**:

- The artifact is originally on the gateway node, **naturally reachable**, with no need to spin up an extra HTTP service or expose a URL.
- In `pull`, the daemon internally chunks the transfer in a loop; **the bytes do not pass through your context**, and only a summary is returned (path/size/sha256), which you can use to verify.
- Only daemon capabilities are used throughout, without depending on child nodes/WSL/SSH.
- It does not depend on GitHub Release (official release self-update) or a bypass channel (WSL/SSH directly writing to the filesystem) -- those are all unavailable in the "compiled on this node, target machine remote" scenario.

**Clarification of key concepts (easily confused)**:

- **`fs.transfer.pull` is "designated remote node → initiator's local machine"**, **`fs.transfer.push` is "initiator's local machine → designated remote node"**. Both are **from the perspective of the daemon executing the command**, and both require **the executor's local daemon to be authenticated with the gateway**.
- **When updating the daemon itself, `pull`/`push` are not an "update means" but a "file delivery means"**: what actually replaces the exe is always the "spawn helper + self-terminate" approach (see the steps below).
- In this scenario the artifact is on the **gateway node** and needs to be delivered to the **target machine**, so the **target machine** initiates the `pull` (`node_id` points to the gateway node).

**Not applicable to Linux/macOS**: Linux allows directly `rename`-ing a running binary for an atomic replacement, without a helper.

## Principles You Must Follow

### 1. Establish that "the new exe comes from the gateway node"

**Must** first confirm: **the compiled artifact has been placed under `~/.haijunbot/transfers/` on the gateway node (source node)**, and the target machine's daemon has connected to the gateway.

**Forbidden**:

- **Forbidden to use `windows.fs.write` to manually base64-chunk-feed the exe** -- `fs.transfer.pull` already exists to do cross-machine direct transfer specifically; manual chunking is both clumsy and pollutes the context.
- **Forbidden to treat `fs.transfer.pull` as a "means of updating the daemon"** -- it is only file delivery; the replacement must go through the helper.
- **Forbidden to apply "cp the file in WSL + schtasks" when "the local machine and the target machine do not share a filesystem"** -- WSL is only usable when it is **on the same machine** as the target machine.

### 2. Then establish "who is running it, where the exe is, and how it was started"

**Must**:

- First confirm the **real path** of the target exe (usually the fixed install path `%USERPROFILE%\.haijunbot\bin\haijunbot-daemon.exe`, see `daemon/internal/service/install_dir.go`).
- Confirm **who starts the daemon**: the scheduled task (schtasks) installed by `haijunbot-daemon install`, or a service. This determines the restart method.
- Confirm the currently running version and PID (the daemon's `build_info` reports version/commit/pid).

**Forbidden**: assuming the path or startup method from memory.

### 3. The helper must be started from the "new file"

**This is the most easily hit pitfall**: the old exe is running and locked, so it **cannot be executed**. Therefore the helper itself must be started from a copy of the new version file:

```text
<target>.helper.exe   ← the helper runs from this "new file" copy
```

The daemon's built-in implementation (`SpawnApplyHelper` in `daemon/internal/selfupdate/apply_windows.go`) does exactly this: it first copies the new file to `<target>.helper.exe`, then executes it.

### 4. Do not call `restartService()` in the replacement flow

**Key lesson (hit on a real machine)**: do not use `service.New().Restart()` to "stop yourself and then restart".

Reason: if the daemon is started by `schtasks /Run`, it **does not write a PID file** (only `service start` writes one). `Restart()`'s `Stop()` reads the PID file → reads a stale PID → mistakenly judges "the service is not running" → does not kill this process → `Start()` spawns a new process again → the new process fails to grab port 17800 → **the old process keeps holding the exe, and the helper times out after 60s and the replacement fails**.

Correct approach: **the parent process directly does `os.Exit(0)`** (`exitForHelperReplacement()`), handing off "replace + restart" entirely to the helper (the helper side's `--restart` → `restartServiceForHelper()`).

### 5. Explain intent before write operations, clean up afterward

**Must**:

- Before replacement, inform the user which file will be replaced, the target version, and whether it will restart.
- After replacement, clean up residue: `.new`, `.helper.exe`, temporary scripts, logs.
- Honestly distinguish "verified" from "unverified".

## Operations You Must Perform

### Path: The target machine's daemon pulls from the gateway node

**Applicable**: **the compiled artifact is on the gateway node** (typically: the Agent compiles the exe on this node), and the target machine is **another remote machine** that this node cannot reach the filesystem of. In this case, have **the target machine's daemon execute `fs.transfer.pull`** to pull the artifact over from the gateway node.

**Prerequisites**:

1. The target machine's daemon **has connected to the gateway** (has a valid token) -- `pull` initiates using the daemon's gateway credentials.
2. The artifact must first be placed **under `~/.haijunbot/transfers/` on the gateway node (source node)** -- `remote_path` will be constrained by the gateway to that directory (absolute paths are stripped of their root while retaining the structure; `_resolve_transfer_path` in `app.py`).
3. `node_id` should be the node_id of the **source node** (that is, the gateway node/master).

**Steps:**

```text
# 1) Find the target daemon session and PID
daemon(action="list_sessions")          # record the target machine's session_id and build_info.pid
daemon(action="list_capabilities", session_id="<target sid>")

# 2) Put the compiled artifact under ~/.haijunbot/transfers/ on the gateway node (source node)
#    (if this node is the gateway node, just cp directly; otherwise send it over first via node direct transfer, etc.)

# 3) Target machine daemon executes pull: pull the artifact from the gateway node to the target machine
daemon(action="call", session_id="<target sid>", name="fs.transfer.pull",
       params={"gateway": "https://<gateway>", "node_id": "<source node ID, usually master>",
               "remote_path": "haijunbot-daemon-new.exe",   # relative path under the source node's transfers/
               "local_path": "C:\\Users\\<user>\\.haijunbot\\bin\\haijunbot-daemon-new.exe",
               "mode": "file",
               "chunk_size": 524288})   # see the "chunk_size required" note below
# the sha256 in the returned summary should match the source node artifact's sha256; verify accordingly

# 4) Copy to .helper.exe → start helper (helper must run from the new file)
daemon(action="call", session_id="<target sid>", name="windows.script.exec",
       params={"interpreter": "powershell", "script":
         "$bin='C:\\Users\\<user>\\.haijunbot\\bin'; $new=Join-Path $bin 'haijunbot-daemon-new.exe';\n" +
         "$helper=Join-Path $bin 'haijunbot-daemon.exe.helper.exe';\n" +
         "Copy-Item $new $helper -Force;\n" +
         "Start-Process -FilePath $helper -ArgumentList 'self-update-apply','--src',$helper,'--dst',(Join-Path $bin 'haijunbot-daemon.exe'),'--restart' -WindowStyle Hidden"})

# 5) Let the old daemon self-terminate (helper will wait for it to exit, then replace + restart)
daemon(action="call", session_id="<target sid>", name="windows.process.kill",
       params={"pid": <old daemon pid>, "force": true})
```

**Direction clarification (be sure to distinguish)**:

- `fs.transfer.pull` = **"designated remote node → initiator's local machine"**; `fs.transfer.push` = **"initiator's local machine → designated remote node"**.
- In this scenario the artifact is on the **gateway node** and needs to be delivered to the **target machine**, so the **target machine** initiates the `pull` (`node_id` points to the gateway node).
- Only if the artifact is on the **executor's local machine** and needs to be sent to another node do you use `push`.

**chunk_size required (otherwise most likely HTTP 413)**:

- The transfer chunks by base64 (a 4/3 size expansion). The gateway nginx defaults to `client_max_body_size 1M`, while the daemon default `chunk_size` is 1MiB → the actual request body is about 1.33MB → rejected by nginx, reporting **HTTP 413**.
- Therefore you **must explicitly pass `chunk_size: 524288` (512KiB)**, and pass it for both push/pull. The daemon side allows 1MiB~8MiB (`NormalizeTransferChunkSize`), but limited by nginx, 512KiB is a safe value.
- Large file transfers take a long time, and the `daemon(action="call")` default 30s will time out (the actual transfer may still be continuing); increase `timeout` to over 120s.

**helper subcommand signature (exact):**

```text
haijunbot-daemon self-update-apply --src <new exe path> --dst <target path> [--restart]
```

- `--src`: the path of the new version executable (the helper itself runs from this copy).
- `--dst`: the final path to replace (e.g., `...\.haijunbot\bin\haijunbot-daemon.exe`).
- `--restart`: whether to restart the service after a successful replacement (goes through `restartServiceForHelper()`).
- Missing either `--src` or `--dst` results in an error.

### Reliable way to kill the process (when the WSL side lacks permission)

Calling `/mnt/c/Windows/System32/taskkill.exe` from WSL to kill the daemon often returns "access denied" (a WSL process has no Windows administrator privileges). **Reliable approach: use the daemon's own `windows.process.kill` capability to self-terminate** (the daemon runs with its own privileges and can kill itself):

```text
daemon(action="call", session_id="<sid>", name="windows.process.kill",
       params={"pid": <daemon_pid>, "force": true})
```

After the call, **the session disconnects immediately** (`daemon session disconnected`); this is **expected behavior**, not a failure. Then use the WSL side to complete the exe replacement + `schtasks /Run` (these two steps do not require Windows administrator privileges; WSL can operate on `/mnt/c/...` directly).

**The order is critical**: `windows.process.kill` is "the last daemon command" -- after killing, there is no daemon channel left, and all subsequent operations can only go through the WSL side filesystem + `schtasks.exe`.

## Verifying the Replacement Result

**Must** verify item by item, not just look at "the command returned success":

1. **exe hash**: the sha256 of the new exe matches the local build artifact.

   ```powershell
   Get-FileHash 'C:\Users\<user>\.haijunbot\bin\haijunbot-daemon.exe' -Algorithm SHA256
   ```

2. **Process**: the new PID is running and listening on 17800.
3. **Logs**: the daemon log shows "haijunbot-daemon vX.Y.Z started" and "registered N platform capabilities".
   - **The change in capability count is a reliable indicator of "whether the new capability took effect"**: compare the N in `registered N platform capabilities` before and after the replacement. When a new capability is added, N should increase (e.g., 26 → 27 after adding OCR); if the number does not change, the new exe did not actually take effect.
4. **Gateway**: in `list_sessions`, the session's `build_info.version` / `commit` are the new values; `connected` and `token_valid:true`. The new capability name (e.g., `ocr.recognize`) is visible in the capability list.
5. **Residue cleanup**: confirm that `.new` / `.helper.exe` have been deleted (the daemon automatically cleans up on startup; you can double-check).

**Note**: the daemon's Token **is only stored in memory and never written to disk**, so it is lost on restart (`gateways:[]`). After a restart, the Token must be re-pushed for it to reconnect to the gateway; otherwise the log stops at "started" with no `connected`/`hello_ack`. For the re-push method, see "Re-pushing the Token after restart (no need to depend on the browser)" below. If `token_valid:false` after the replacement, it is expected behavior, not a replacement failure.

### Re-pushing the Token after restart (no need to depend on the browser)

**Key conclusion**: re-pushing the Token **does not require a browser**; you can directly POST to the daemon's local interface from the command line. What the frontend page does is the same thing (`syncTokenToDaemon` in `App.vue` → `POST http://127.0.0.1:17800/api/auth`).

**Interface contract** (`handleAuth` in `daemon/internal/localapi/server.go`):

```text
POST http://127.0.0.1:17800/api/auth
Content-Type: application/json
{ "gateway": "https://hjb-ai.cn:4443", "token": "<valid token>", "name": "<terminal name>" }
```

- No authentication, no origin restriction (`withCORS` allows any origin); only `gateway` + `token` are required to be non-empty.
- On success it returns `{"success":true,"status":"connecting",...}`, and the daemon immediately connects to the gateway.

**Execute on the Windows side** (WSL cannot reach Windows's 127.0.0.1; you must use Windows PowerShell):

```powershell
$body = @{ gateway = "https://hjb-ai.cn:4443"; token = "<token>"; name = "SF-PC" } | ConvertTo-Json
Invoke-WebRequest -UseBasicParsing -Method POST -Uri http://127.0.0.1:17800/api/auth -ContentType "application/json" -Body $body
```

**Where the token comes from** (the key is finding valid credentials recognized by the gateway):

1. **Preferred: the `HAIJUNBOT_AUTH_TOKEN` environment variable of the master gateway**. `token_manager.validate_gateway_token` falls back to comparing against `HAIJUNBOT_AUTH_TOKEN` after JWT validation fails, so that UUID can be used directly as a valid Bearer Token.
2. If `hjb-ai.cn` is **this machine's gateway behind an nginx reverse proxy** (check `/etc/nginx/sites-enabled/`: `4443 → 127.0.0.1:8000`), then the token recognized by this machine's master gateway can be used for the daemon.
3. Validate the token: `curl -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/daemon/sessions`; if it returns `{"success":true,...}`, it is valid.
4. Fallback: use `/api/auth/login` (username + password) to obtain a JWT; or have the user trigger a re-push once on the browser side.

**Why not count on the browser `reload`**: the browser extension's `reload`/`navigate`/`evaluate` depend on a CDP debugger attach, and **all of them time out when the session is occupied** (`list_tabs` still works because it goes through the extension API and does not depend on attach). At this point, re-pushing via the above command-line path is more reliable.

## Practical Guidance

### Common pitfalls (all measured on real machines)

1. **`restartService()` misjudges on a daemon started by schtasks**: the PID file is missing → does not kill the old process → the old and new contend for the port → the replacement times out. See "Principle 3".
2. **The helper cannot start from the old exe**: the old exe is locked and cannot be executed. It must start from a new file copy (`.helper.exe`).
3. **A rename failure when the target is occupied is expected**, not an error -- this is exactly why the helper is needed.
4. **Waiting 60s is normal**: the helper polls waiting for the target to be released, up to 60s; when the GitHub download is slow the total time can reach over 1 minute, so observing logs requires patience.
5. **Residual files**: after replacement the helper does **not self-clean** `.new` / `.helper.exe`; on failure `<target>.new` is retained (for the next replacement). After a successful replacement it needs to be cleaned up, or rely on the cleanup at daemon startup.
6. **`update-attempt.json`**: after success it may still leave `in_progress:true`, which is harmless for "current version == target version" (`ShouldSkipUpdate` is self-consistent).
7. **Cross-drive rename fails**: the new file and the target must be **in the same directory/same drive**; otherwise copy to the target's directory first and then replace.
8. **Token loss is expected**: the daemon Token is only stored in memory and is lost on restart, requiring a frontend re-push.
9. **Non-administrator session**: `windows.process.kill` / service operations may fail due to permissions; if the daemon runs as administrator, killing it usually also requires administrator privileges.
10. **Calling `taskkill` from WSL often gets "access denied"**: a WSL process has no Windows administrator privileges, so `taskkill /F /IM haijunbot-daemon.exe` fails (but `tasklist` can list processes). Instead, use the daemon capability `windows.process.kill` to self-terminate (see "Reliable way to kill the process").
11. **WSL cannot reach Windows's `127.0.0.1`**: WSL2 and Windows have isolated network namespaces, so `curl http://127.0.0.1:17800` does not work inside WSL. To probe a local Windows-side service (the daemon local API) you must use Windows PowerShell/curl, or directly read the Windows-side log files.
12. **Never use a process spawned by the daemon to run a "redeploy script that kills the daemon"** (pitfall hit on a real machine): if you use `Start-Process powershell` inside `windows.script.exec` to run redeploy.ps1 (`schtasks /End` + `taskkill /F /IM haijunbot-daemon.exe` + `Copy-Item` + `schtasks /Run`), the first step of redeploy kills the daemon parent process, and that powershell is a child process spawned by the daemon -- Windows terminates the entire Job process tree along with it, causing the spawned powershell to be killed as well, so **the later `Copy-Item` replacement and `schtasks /Run` restart will not execute**. Result: the daemon is stopped but not restarted, the exe is not replaced, and once the daemon goes offline it can no longer be restored using daemon capabilities (the browser extension also has no system command capability), so you can only wait for the user to come back to the computer and manually run `schtasks /Run /TN HaijunBot-Daemon`. **Correct approach**: do not use a daemon-spawned process to run redeploy; either use this rule's `self-update-apply` helper mechanism (the parent process does `os.Exit(0)` to self-terminate, and the helper handles replacement + restart), or use `schtasks /Create` to create an independent one-off scheduled task (executed by the Task Scheduler service, detached from the daemon process tree) to run redeploy.

### Unverified / risk items (marked honestly)

- On a real Windows machine, the **complete path** of "target exe occupied → rename fails → delete old → retry" has only been run through the helper branch on a real machine; the delete-old-and-retry branch after a direct rename failure has not been separately verified on a real machine.
- **The complete chain of this rule's path (`fs.transfer.pull` pulling the exe from the gateway node) has not been verified on a real machine**: the capability implementation and unit tests are in `daemon/internal/capability/transfer_remote.go` and `transfer_remote_test.go`; the `pull` `remote_path` constraint rule is in the gateway's `_resolve_transfer_path` in `app.py`. On first use, first confirm the source node's node_id and the artifact landing location.
- The chain of helper replacement + restart has been fully verified on a real machine (daemon self-update scenario, log sequence: downloading → verifying → applying → starting helper → done → restarting → starting/connected).

## Self-Checklist

- [ ] Has the compiled artifact been placed **under `~/.haijunbot/transfers/` on the gateway node (source node)**?
- [ ] Is the `node_id` of `fs.transfer.pull` set to the **source node** (gateway node/master)?
- [ ] Has the sha256 of the summary returned by `pull` been checked against the source artifact?
- [ ] Has the target machine's daemon connected to the gateway (has a token)?
- [ ] Have the real path and startup method (schtasks / service) of the target exe been confirmed?
- [ ] Does the helper start from a **new file copy** (`.helper.exe`) rather than the old exe?
- [ ] Has `restartService()` **not** been called in the replacement flow (restart is instead handled by the helper)?
- [ ] Is the new file in the **same directory/same drive** as the target?
- [ ] Has the replacement result been verified using sha256 + process + logs + gateway `build_info`?
- [ ] If a new capability was added this time, has the change in N in "registered N platform capabilities" been checked?
- [ ] After restart, has the Token been re-pushed (a command-line POST to `/api/auth` suffices; no need to depend on the browser)? Is the session `connected`?
- [ ] Has residue such as `.new` / `.helper.exe` / temporary scripts been cleaned up?
- [ ] Have "verified" and "unverified" been honestly distinguished?
