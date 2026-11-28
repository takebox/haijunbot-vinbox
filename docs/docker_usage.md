# Docker Usage Guide

> This document explains how to use HaijunBot's Docker image out of the box. The image comes preinstalled with the Python environment,
> dependencies, and frontend build tools, so no local installation of Python / Rust is required.
> The image definition is in the repository root [`Dockerfile`](../Dockerfile), and the orchestration definition is in [`docker-compose.yml`](../docker-compose.yml).

## 1. Image Source and Tags

The image is published on GitHub Container Registry:

```text
ghcr.io/takebox/haijunbot
```

The tag rules are defined by [`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml),
and it automatically builds and pushes when a Git tag of the form `v*` is pushed:

| Tag | Description |
| --- | --- |
| `latest` | Latest release version |
| `{{version}}` | Full semantic version, e.g. `6.1.0` |
| `{{major}}.{{minor}}` | Major.minor version, e.g. `6.1` |
| `{{major}}` | Major version, e.g. `6` |

## 2. Quick Start

### Option 1: docker compose (recommended)

The repository root already provides `docker-compose.yml`; start it directly:

```bash
cd /path/to/your/project
docker compose up -d
```

This orchestration will:

- Use the image `ghcr.io/takebox/haijunbot:latest`;
- Run as `user: "1000:${GID:-1000}"` (inside the container this is the `haijunbot` user with UID 1000,
  with the group ID taken from the host's `GID`, to prevent files created inside the container from being inaccessible on the host);
- Mount volumes:
  - `.:/workspace`: mounts the current directory to the container working directory;
  - `${HOME}/.haijunbot:/home/haijunbot/.haijunbot`: preserves the local HaijunBot configuration (optional);
  - `${HOME}/.gitconfig:/home/haijunbot/.gitconfig:ro`: preserves Git user information (optional, read-only);
- The working directory is `/workspace`, with `stdin_open` / `tty` enabled for interactivity.

> If the host user group ID is not 1000, you can export it before starting: `export GID=$(id -g)`.

To enter the container for interactive use:

```bash
docker compose exec haijunbot bash
```

### Option 2: docker run

When not using compose, you can run it directly:

```bash
docker run -it --rm \
  --user "1000:$(id -g)" \
  -v "$PWD:/workspace" \
  -v "$HOME/.haijunbot:/home/haijunbot/.haijunbot" \
  -v "$HOME/.gitconfig:/home/haijunbot/.gitconfig:ro" \
  -p 8000:8000 -p 5173:5173 \
  -w /workspace \
  ghcr.io/takebox/haijunbot:latest
```

The container's default command is (see the end of `Dockerfile`):

```text
haijunbot-service run --gateway-host 0.0.0.0 --gateway-port 8000 \
  --frontend-host 0.0.0.0 --frontend-port 5173
```

This starts the Web service (gateway + frontend), listening on `0.0.0.0` so it can be accessed from outside the container.

### Option 3: Start Only the Gateway (without frontend)

The image bundles `haijunbot-web-gateway` (short command `hwg`), which can start the Web gateway separately,
suitable for providing only an API/gateway, or acting as a child node in a distributed deployment.

```bash
docker run -it --rm \
  -p 8000:8000 \
  ghcr.io/takebox/haijunbot:latest \
  hwg --host 0.0.0.0 --port 8000
```

Parameters supported by `hwg` (see `src/haijunbot/haijunbot_web_gateway/eli.py`):

| Option | Description |
| --- | --- |
| `--host` / `-h` | Listen address (default `127.0.0.1`; inside a container it must be set to `0.0.0.0`) |
| `--port` / `-p` | Listen port (default `8000`) |
| `--node-mode` | Node mode: `master` or `child` (default `master`) |
| `--node-id` | Current node ID (required in `child` mode) |
| `--master-url` | Master node URL (required in `child` mode) |
| `--node-secret` | Node shared secret (required in `child` mode) |

> Note: `haijunbot-service run` (the container's default command) itself also launches the `hwg` process,
> so the default startup method already includes the Gateway; use this method to start it separately only when the frontend is not needed.

### Option 4: Custom docker-compose Examples

The `docker-compose.yml` bundled with the repository is the simplest usage. Below are examples for two common scenarios,
which can be saved directly as `docker-compose.yml` and used.

#### Example 1: Gateway + frontend (custom ports and config directory)

```yaml
services:
  haijunbot:
    image: ghcr.io/takebox/haijunbot:latest
    container_name: haijunbot
    user: "1000:${GID:-1000}"
    ports:
      - "8000:8000"   # Gateway
      - "5173:5173"   # Frontend
    volumes:
      - .:/workspace
      - ${HOME}/.haijunbot:/home/haijunbot/.haijunbot
      - ${HOME}/.gitconfig:/home/haijunbot/.gitconfig:ro
    working_dir: /workspace
    environment:
      - TERM=${TERM:-xterm-256color}
    stdin_open: true
    tty: true
    restart: unless-stopped
```

#### Example 2: Gateway only, joining the master node as a child node

```yaml
services:
  haijunbot-gateway:
    image: ghcr.io/takebox/haijunbot:latest
    container_name: haijunbot-gateway
    user: "1000:${GID:-1000}"
    ports:
      - "8001:8000"
    command: >
      hwg --host 0.0.0.0 --port 8000
          --node-mode child
          --node-id worker-1
          --master-url http://<master-node-address>:8000
          --node-secret <node-secret>
    volumes:
      - ${HOME}/.haijunbot:/home/haijunbot/.haijunbot
    restart: unless-stopped
```

> `--master-url` / `--node-secret` must be replaced with the master node's actual address and secret
> (the secret can be obtained on the master node via `get_node_secret`).

## 3. First Run and API Key Configuration

Running commands such as `hjb` / `hca` for the first time launches an interactive configuration wizard that generates `~/.haijunbot/config.yaml`.

In the container scenario, the configuration file is located inside the container at `/home/haijunbot/.haijunbot/config.yaml`;
after mounting the host's `~/.haijunbot` via compose / `docker run`, the configuration is persisted to the host,
and can be reused directly on the next startup.

You can also directly edit the host's `~/.haijunbot/config.yaml`, for example:

```yaml
llm_group: default
llm_groups:
  default:
    normal_llm: gpt-5
llms:
  gpt-5:
    platform: openai
    model: gpt-5
    max_input_token_count: 128000
    llm_config:
      openai_api_key: "your-api-key-here"
```

For more configuration options, see the [Usage Guide](haijunbot_book/4.Usage_Guide.md).

## 4. Ports and Access

| Port | Purpose |
| --- | --- |
| `8000` | Web gateway |
| `5173` | Frontend page |

The container listens on `0.0.0.0` by default; after mapping to the host via `-p` in `docker run`,
you can use it by visiting `http://localhost:5173` in a browser.

## 5. FAQ

### File Permission Issues

The container runs as UID 1000. If the host user's UID/GID is not 1000, files created inside the container
may end up with incorrect ownership. Before starting, set `export GID=$(id -g)` and make sure the mounted directory is writable by UID 1000.

### Network and Proxy

The container needs to access external LLM APIs. If the host connects to the network through a proxy, note that inside the container
`127.0.0.1` points to the container itself rather than the host, so you must use a proxy address reachable from the host
(such as `--network host` or `http://host.docker.internal:<port>`).

### Offline / Intranet Environments

For offline environments, use the offline installation package (see the [Offline Installation Guide](offline_installation.md)),
or build the image on a networked machine and export it:

```bash
docker save ghcr.io/takebox/haijunbot:latest -o haijunbot.tar
# Target machine
docker load -i haijunbot.tar
```

### Image Size

The image comes preinstalled with the clang toolchain, frontend dependencies, and Python tools, so it is relatively large; if you need to slim it down,
you can trim unnecessary build stages based on the `Dockerfile`.
