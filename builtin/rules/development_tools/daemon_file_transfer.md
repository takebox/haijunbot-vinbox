---
name: daemon_file_transfer
description: Triggered when files need to be moved between two machines (especially between haijunbot-daemon nodes, such as NAS to/from PC). Triggered whenever the user mentions "transfer a file to some machine", "download/upload a file to some device", "cross-machine file transfer", "fs.transfer.push/pull", "transferring files between daemons", or "put a file on the desktop". Not triggered: copying files on the same machine (use fs.read/write or shell cp); only reading remote file content (use fs.read); web uploads and downloads (use browser_ext).
---

# Cross-Machine File Transfer (fs.transfer.push / pull) Operation Guide

## Rule Overview

`fs.transfer.push` / `fs.transfer.pull` is a **cross-machine direct file transfer** capability provided by haijunbot-daemon: the daemon internally loops over chunks, and bytes only flow between the daemon and the gateway, **never passing through the Agent context**, so moving large files will not blow up the context. Only a summary (path, size, sha256) is returned.

This rule records the correct usage and all known pitfalls so you do not fall into them repeatedly.

## The Principles You Must Follow

### 1. Know the transfer topology: daemon ↔ **agent node**, not daemon ↔ daemon

**This is the easiest thing to get wrong.**

The data path is:

```text
local daemon --(HTTP, with gateway token)--> gateway /api/node/{node_id}/file-transfer/{upload|download}
                                                  --(WebSocket)--> target node writes to disk/packages
```

`node_id` must be an **agent node registered on the gateway side** (one that `gateway_manager(action="list_nodes")` can list, such as `master`, `worker-83`, `sf-pc`), **not the client_id of a daemon session**.

**Forbidden**: passing the `client_id` / `node_id` returned by `daemon(action="list_sessions")` (shaped like `daemon-hinas-11408`) as `node_id` to push/pull — the gateway cannot find that node and returns **HTTP 502 `Node xxx not found`**.

**How to determine it**: `node_id` can only be taken from `nodes[].node_id` of `gateway_manager(action="list_nodes")`.

### 2. Transferring files between two daemons: use the "agent node relay" two-step method

When both machines are daemons (for example a home NAS and a PC), there is **no** direct daemon-to-daemon channel. The correct approach is to relay through an agent node that both sides can access:

**Step A (source machine pushes to the relay node):**

```text
daemon(action="call", session_id="<source machine sid>", name="fs.transfer.push",
       params={"gateway":"https://hjb-ai.cn:4443",
               "node_id":"master",              # must be an agent node
               "local_path":"/source/path/file.jpg",
               "remote_path":"file.jpg",         # converges onto the relay node's ~/.haijunbot/transfers/
               "mode":"file",
               "chunk_size":524288},             # see section 3, must be <=524288
       timeout=120)
```

**Step B (the target machine pulls from the same relay node):**

```text
daemon(action="call", session_id="<target machine sid>", name="fs.transfer.pull",
       params={"gateway":"https://hjb-ai.cn:4443",
               "node_id":"master",              # the same node as in step A
               "remote_path":"file.jpg",         # consistent with remote_path in step A
               "local_path":"C:\\Users\\xxx\\Desktop\\file.jpg",
               "mode":"file",
               "chunk_size":524288},
       timeout=120)
```

**Key points**:

- `gateway`, `node_id`, `remote_path`, and `mode` in both steps must be consistent.
- On the relay node the file lands in `~/.haijunbot/transfers/<remote_path>` (an absolute path is de-rooted, preserving the structure).
- After completion, it is recommended to clean up the residual file on the relay node (use that node's shell capability `rm`).

**Direction analysis (make sure to distinguish this first; it is the easiest to reverse)**:

- `fs.transfer.push` = **"the initiator's local machine → the specified remote node"**. `local_path` is the file on **the initiator's local machine**, and `remote_path` is the landing point **on the remote node**.
- `fs.transfer.pull` = **"the specified remote node → the initiator's local machine"**. `remote_path` is the file **on the remote node**, and `local_path` is the landing point **on the initiator's local machine**.
- Mnemonic: **`local` always means the initiator's local machine, `remote` always means the `node_id` node**; push means "push out" (local→remote), pull means "pull in" (remote→local).
- Whoever initiates the operation calls it with their own `session_id`: **to place a file on a machine, initiate it on that machine's daemon session** (use push to put it in, use pull to fetch it from elsewhere).
- Common mistake: wanting to "send a file from machine A to machine B", but calling `pull` on machine A (the direction is reversed) — the correct approach is **A pushes to the relay node, B pulls** (see the two-step method in section 2).

### 3. chunk_size must be <= 524288 (512 KiB) — otherwise you get a 413

The **nginx in front of the gateway has a default `client_max_body_size` of 1 MB**, and the chunk content is transferred as base64 (expanding roughly 4/3). The daemon's default chunk size is **1 MiB**, which is about 1.4 MB after base64, **guaranteed to be rejected by nginx**, reporting:

```text
413 Request Entity Too Large (nginx)
```

**You must explicitly pass `chunk_size`, and satisfy: `chunk_size * 4/3 < 1 MB`, i.e. `chunk_size <= ~750 KB`.**

**The recommended value is `524288` (512 KiB, about 683 KB after base64)**, which is safe and keeps the number of round trips reasonable.

> If you mistakenly use the default value and see a 413, do not suspect the daemon or the network; just reduce `chunk_size` and retry.

### 4. The gateway must be the **exact address (including the port)** that the daemon has authenticated against

The daemon indexes credentials by `hostname:port` (`GatewayKey`). `https://hjb-ai.cn` and `https://hjb-ai.cn:4443` are **two different gateways**.

If it reports "no usable credentials for gateway xxx, cannot initiate a direct transfer", it means the gateway address this daemon authenticated against does not match the one you passed.

**How to get the correct address**: check that daemon's log (Linux `~/.haijunbot/logs/daemon.log`, Windows `C:\Users\<user>\.haijunbot\logs\daemon.log`) and look for something like:

```text
[localapi] received auth push: gateway=https://hjb-ai.cn:4443 token=... name="SF-PC"
```

**Copy the gateway value from the log verbatim** (including the port); do not omit the port on your own.

### 5. The tool call timeout must be enlarged to 120s

`daemon(action="call")` has a default timeout of 30s. Chunked transfers across the public internet are slow (measured: a 5 MB file takes about 35s in 10 chunks), so **the default timeout will falsely report `capability call timed out`**, even though the transfer may still be running in the background or may have been aborted.

**You must explicitly pass `timeout=120`** (for larger files it can be enlarged further).

> After a timeout, **do not retry immediately** — first check whether the target file has landed (see section 6), to avoid duplicate transfers.

### 6. You must verify after completion

Use the `sha256` in the summary and compare it with the actual file on both ends to confirm integrity:

```text
# source machine (Linux)
sha256sum /source/path/file.jpg

# target machine (Windows)
(Get-FileHash 'C:\...\file.jpg' -Algorithm SHA256).Hash
```

The `sha256` field returned by push/pull is the SHA-256 of the whole package, and both ends should match exactly (the Windows side is case-insensitive). **Only a passed verification counts as success**; do not claim completion just because the command did not report an error.

## Common Error Quick Reference

| Symptom                                | Cause                                              | Handling                                            |
| -------------------------------------- | -------------------------------------------------- | --------------------------------------------------- |
| `HTTP 502 Node xxx not found`          | `node_id` was given a daemon's client_id           | use the agent node id from `list_nodes` instead     |
| `HTTP 413 Request Entity Too Large`    | `chunk_size` too large (default 1 MiB)             | explicitly pass `chunk_size=524288`                 |
| `no usable credentials for gateway`    | gateway address differs from what the daemon authenticated (different port) | check the daemon log and copy the gateway including the port |
| `capability call timed out`            | the tool's default 30s timeout is too short        | pass `timeout=120`; first check whether the file has landed before deciding to retry |
| file not found on the source machine   | `remote_path` was converged onto the node's `~/.haijunbot/transfers/` | use a relative path, or calculate the actual landing point by the de-rooted structure |

## Complete Example: NAS photo → Windows desktop (verified on a real machine, 2026-09-27)

**Scenario**: transfer `/mnt/sdb1/pictures/banana-pi-photos/IMG20230827095833.jpg` (about 5 MB) on the NAS (hinas, Linux) to the SF-PC (Windows) desktop. Both machines are daemons, **with no direct channel**, so transfer must be relayed through the agent node `master`.

### Step 1: Survey the environment

```text
gateway_manager(action="list_nodes")
# → returns the agent node list; take node_id="master" (this is a node registered on the gateway side, not a daemon)

daemon(action="list_sessions")
# → returns all daemon sessions; take two:
#   source machine NAS:  session_id="daemon-hinas-11408"  (note: this is a daemon's client_id, never use it as node_id!)
#   target machine PC: session_id="daemon-SF-PC-35748"
```

### Step 2: The source machine (NAS) pushes to the relay node master

```text
daemon(action="call", session_id="daemon-hinas-11408", name="fs.transfer.push",
       params={"gateway": "https://hjb-ai.cn:4443",
               "node_id": "master",                       # agent node, not a daemon
               "local_path": "/mnt/sdb1/pictures/banana-pi-photos/IMG20230827095833.jpg",
               "remote_path": "IMG20230827095833.jpg",    # the relative path under ~/.haijunbot/transfers/ on master
               "mode": "file",
               "chunk_size": 524288},
       timeout=120)
# measured: about 15.7s, in 10 chunks; returns size=5178920, sha256=8c87abdf01396f00...
```

### Step 3: The target machine (SF-PC) pulls from the same node master to the desktop

```text
daemon(action="call", session_id="daemon-SF-PC-35748", name="fs.transfer.pull",
       params={"gateway": "https://hjb-ai.cn:4443",          # exactly the same as in step 2
               "node_id": "master",                          # exactly the same as in step 2
               "remote_path": "IMG20230827095833.jpg",       # consistent with remote_path in step 2
               "local_path": "C:\\Users\\skyfire\\Desktop\\IMG20230827095833.jpg",
               "mode": "file",
               "chunk_size": 524288},
       timeout=120)
# measured: about 35.5s, in 10 chunks
```

### Step 4: Verification (the sha256 on both ends must match)

```text
# NAS side
sha256sum "/mnt/sdb1/pictures/banana-pi-photos/IMG20230827095833.jpg"
# Windows side (run on the daemon of SF-PC)
daemon(action="call", session_id="daemon-SF-PC-35748", name="windows.script.exec",
       params={"interpreter": "powershell",
               "script": "(Get-FileHash 'C:\\Users\\skyfire\\Desktop\\IMG20230827095833.jpg' -Algorithm SHA256).Hash"})

# measured result: both ends have
#   8C87ABDF01396F00DF2FF6A881D13E7036C58B93AA12578ECA497399F2BB1246
#   size 5178920 bytes — completely identical, the transfer succeeded
```

### Step 5: Clean up the residual file on the relay node

```text
# on master the file landed at ~/.haijunbot/transfers/IMG20230827095833.jpg; delete it after use
gateway_manager(action="exec_command", node_id="master",
                command="rm -f ~/.haijunbot/transfers/IMG20230827095833.jpg")
```

**The pitfalls this example fell into (all have been written into the corresponding sections above)**:

1. At first I passed `daemon-hinas-11408`, returned by `daemon(action="list_sessions")`, as `node_id` → **HTTP 502 `Node daemon-hinas-11408 not found`**. Correct approach: `node_id` can only be an agent node from `list_nodes` (`master`).
2. I did not pass `chunk_size`, using the default 1 MiB → **HTTP 413**. Correct approach: explicitly pass `524288`.
3. The tool default `timeout=30`, and a 5 MB file took 35s → falsely reported `capability call timed out`. Correct approach: pass `timeout=120`.
4. `gateway` was initially written as `https://hjb-ai.cn` (no port) → reported "no usable credentials". Correct approach: copy `https://hjb-ai.cn:4443` from the daemon log.

## Capability Parameters Quick Reference

| Capability            | Direction              | Required parameters                          | Key returns               |
| --------------------- | ---------------------- | -------------------------------------------- | ------------------------- |
| `fs.transfer.push`    | local → remote node    | `gateway`, `node_id`, `local_path`, `remote_path` | `size`, `sha256`, `chunks` |
| `fs.transfer.pull`    | remote node → local    | `gateway`, `node_id`, `local_path`, `remote_path` | `size`, `sha256`, `chunks` |

Common optional parameters: `mode` (`file`/`dir`, inferred by default from the `local_path` type), `chunk_size` (**be sure to pass 524288**). Single transfer limit: 512 MiB.
