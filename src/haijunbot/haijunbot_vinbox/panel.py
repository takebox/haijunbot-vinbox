# -*- coding: utf-8 -*-
"""Minimal panel server for HaijunBot.

Serves the HTML panel template and provides JSON status endpoint.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from html import escape as _html_escape
from pathlib import Path
from typing import Any
from typing import Dict

from haijunbot.haijunbot_utils import vinbox_runtime

PANEL_VERSION = "1"

VINBOX_API = os.environ.get("VINBOX_API", "http://127.0.0.1:7331")
LLAMA_URL = os.environ.get("HAIJUNBOT_LLAMA_URL", "http://127.0.0.1:8088")
CHAT_TIMEOUT = float(os.environ.get("HAIJUNBOT_CHAT_TIMEOUT", "180"))


def _ask_llama(prompt: str) -> tuple[str, str]:
    """Ask llama-server directly and return (reply, model name)."""
    body = json.dumps(
        {
            "model": "local",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 160,
            "temperature": 0.3,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        LLAMA_URL.rstrip("/") + "/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=CHAT_TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8", "replace"))
    reply = (payload["choices"][0]["message"]["content"] or "").strip()
    if not reply:
        raise ValueError("llama.cpp tidak mengembalikan teks")
    name = "local llama.cpp"
    try:
        with urllib.request.urlopen(LLAMA_URL.rstrip("/") + "/v1/models", timeout=5) as response:
            models = json.loads(response.read().decode("utf-8", "replace"))
        name = (models.get("data") or [{}])[0].get("id") or name
    except Exception:  # noqa: BLE001 - the name is cosmetic
        pass
    return reply, name


def ask_model(prompt: str) -> Dict[str, Any]:
    """Ask the local model, falling back to Vinbox's own model API.

    The panel runs on the host and llama-server is published on port 8088, so
    the panel can talk to llama.cpp with a long timeout: Vinbox's
    /api/models/test gives up after 45s, which a slow machine cannot meet. If
    llama-server is not reachable, the panel asks Vinbox instead so a provider
    model can still answer.
    """
    try:
        reply, name = _ask_llama(prompt)
        return {
            "ok": True,
            "reply": reply,
            "answered_by": name,
            "attempts": [{"model": name, "ok": True}],
        }
    except Exception as exc:  # noqa: BLE001 - fall back to Vinbox below
        llama_error = str(exc)

    body = json.dumps({"prompt": prompt}).encode("utf-8")
    request = urllib.request.Request(
        VINBOX_API.rstrip("/") + "/api/models/test",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=CHAT_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001 - report instead of raising
        return {"ok": False, "error": f"llama.cpp: {llama_error}; Vinbox: {exc}"}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "balasan Vinbox tidak valid"}
    if not payload.get("ok"):
        payload["error"] = f"llama.cpp: {llama_error}; {payload.get('error') or ''}"
    else:
        payload["answered_by"] = payload.get("answered_by") or "Vinbox"
    return payload


def _cdp_alive(timeout: float = 1.0) -> Dict[str, Any]:
    url = vinbox_runtime.cdp_url().rstrip("/") + "/json/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
        return {"alive": True, "browser": data.get("Browser", ""), "url": url}
    except Exception:  # noqa: BLE001 - status must never raise
        return {"alive": False, "browser": "", "url": "", "error": ""}


def run_task(instruction: str, **kwargs: Any) -> Dict[str, Any]:
    """Run one real HaijunBot task, callable by Haijun over HTTP.

    This is the path behind ``POST /task``: the same in-process bridge Haijun
    imports (``haijunbot.vinbox_bridge.ask``), so the task uses Vinbox's model
    lane, Vinbox's Chromium and Vinbox's terminal instead of any provider or
    browser of HaijunBot's own.
    """
    from haijunbot import vinbox_bridge

    result = vinbox_bridge.ask(instruction, **kwargs)
    if isinstance(result, dict):
        return result
    return {"ok": True, "reply": str(result)}


def collect_status() -> Dict[str, Any]:
    """Collect status data from Vinbox."""
    data_dir = Path(vinbox_runtime.data_dir())
    runtime = vinbox_runtime.status()
    cdp = _cdp_alive() if runtime.get("inside_vinbox") else {
        "alive": False,
        "browser": "",
        "url": runtime.get("cdp_url", ""),
        "error": "tidak berjalan di dalam Vinbox",
    }
    executions_html = '<tr><td colspan="5" class="muted">belum ada eksekusi</td></tr>\n'
    log_file = data_dir / "executions.jsonl"
    if log_file.is_file():
        try:
            records = json.loads(log_file.read_text(encoding="utf-8"))
            if records:
                rows = []
                for rec in records[-10:]:
                    ts = rec.get("timestamp", "")
                    success = "OK" if rec.get("success") else "GAGAL"
                    rows.append(
                        "<tr><td>" + ts[:16] + "</td>"
                        "<td class=\"" + ("ok" if rec.get("success") else "warn") + "\">"
                        + success + "</td>"
                        "<td title=\"" + (rec.get("stdout") or "") + "\">"
                        + (rec.get("stdout") or "")[:50] + "</td>"
                        "<td title=\"" + (rec.get("stderr") or "") + "\">"
                        + (rec.get("stderr") or "")[:50] + "</td></tr>"
                    )
                executions_html = "<table><tbody>" + "\n".join(rows) + "</tbody></table>\n"
        except (OSError, ValueError):
            pass
    return {
        "version": PANEL_VERSION,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "runtime": runtime,
        "cdp": cdp,
        "data": {
            "path": str(data_dir),
            "exists": data_dir.is_dir(),
            "sessions": sum(1 for _ in (data_dir / "sessions").glob("*.json")) if data_dir.is_dir() else 0,
            "bytes": sum(f.stat().st_size for f in data_dir.rglob("*") if f.is_file()),
            "latest": [],
        },
        "executions": executions_html,
    }


def _esc(value: Any) -> str:
    """Escape a value for HTML text/attribute position."""
    return _html_escape("" if value is None else str(value), quote=True)


def _badge(ok: bool, label: str) -> str:
    css = "ok" if ok else "warn"
    return f'<span class="badge {css}">{_esc(label)}</span>'


def render_html(
    payload: Dict[str, Any], template_path: Path | str | None = None
) -> str:
    """Render ``panel_template.html`` with the data from :func:`collect_status`.

    The template carries ``{{badge_vinbox}}``, ``{{badge_cdp}}``,
    ``{{generated_at}}`` and ``{{sections}}``. Everything is escaped here, so a
    model id or a data path cannot break the page.
    """
    if template_path is None:
        template = Path(__file__).with_name("panel_template.html")
    else:
        template = Path(template_path)
    text = template.read_text(encoding="utf-8")

    runtime = payload.get("runtime") or {}
    cdp = payload.get("cdp") or {}
    data = payload.get("data") or {}

    inside = bool(runtime.get("inside_vinbox"))
    cdp_alive = bool(cdp.get("alive"))
    badges = " ".join(
        [
            _badge(inside, "Vinbox" if inside else "standalone"),
            _badge(cdp_alive, "CDP" if cdp_alive else "CDP mati"),
        ]
    )

    where = _esc(runtime.get("vinbox_home")) if inside else "standalone"
    browser = cdp.get("browser") or cdp.get("error") or ""
    shell = runtime.get("shell") or "pwsh belum terpasang"

    sections = [
        "<section><h2>Model</h2>"
        f'<div class="value">{_esc(runtime.get("model") or "belum dipilih")}</div>'
        '<p class="hint">Dipilih di Settings → MODELS.</p></section>',
        "<section><h2>Vinbox</h2>"
        f'<div class="value">{where}</div></section>',
        "<section><h2>Terminal</h2>"
        f'<div class="value">{_esc(shell)}</div></section>',
        "<section><h2>Chromium (CDP)</h2>"
        f'<div class="value">{_esc(cdp.get("url") or "")}</div>'
        f'<p class="hint">{_esc(browser)}</p></section>',
        "<section><h2>Data HaijunBot</h2>"
        f'<div class="value">{_esc(data.get("path") or "")}</div></section>',
        '<section class="wide"><h2>Eksekusi terakhir</h2>'
        + (payload.get("executions") or "")
        + "</section>",
    ]

    return (
        text.replace("{{badge_vinbox}}", badges)
        .replace("{{badge_cdp}}", "")
        .replace("{{generated_at}}", _esc(payload.get("generated_at") or ""))
        .replace("{{sections}}", "\n".join(sections))
    )


def serve(panel_path: str | None = None, port: int = 7340,
          host: str | None = None) -> None:
    """Serve the panel, rendering fresh status on every request."""
    template_path = Path(panel_path) if panel_path else Path(__file__).with_name(
        "panel_template.html"
    )

    from http.server import BaseHTTPRequestHandler
    from http.server import ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server API
            if self.path == "/status.json":
                body = json.dumps(collect_status(), ensure_ascii=False, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/" or self.path == "/panel.html" or self.path == "/index.html":
                body = render_html(collect_status(), template_path).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def _json(self, payload: Dict[str, Any], status: int) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802 - http.server API
            if self.path not in {"/chat", "/task"}:
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8", "replace") or "{}")
            except ValueError:
                self._json({"ok": False, "error": "JSON tidak valid"}, 400)
                return
            prompt = str(data.get("prompt") or "").strip()[:4000]
            if self.path == "/task":
                prompt = str(data.get("instruction") or prompt).strip()[:4000]
            if not prompt:
                self._json({"ok": False, "error": "prompt kosong"}, 400)
                return
            if self.path == "/task":
                try:
                    payload = run_task(prompt)
                except Exception as exc:  # noqa: BLE001 - report the real failure
                    self._json({"ok": False, "error": "tugas gagal: " + str(exc)}, 500)
                    return
                self._json(payload, 200)
                return
            try:
                payload = ask_model(prompt)
            except Exception as exc:  # noqa: BLE001 - report the real failure
                self._json({"ok": False, "error": "Vinbox tidak menjawab: " + str(exc)}, 502)
                return
            self._json(payload, 200)

        def log_message(self, fmt, *args):  # keep the console quiet
            return

    bind = host or os.environ.get("HAIJUNBOT_PANEL_HOST", "127.0.0.1")
    httpd = ThreadingHTTPServer((bind, port), Handler)
    print("HaijunBot panel: http://" + bind + ":" + str(port), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="HaijunBot panel untuk Vinbox")
    parser.add_argument(
        "--panel",
        # Resolve next to the package so the documented `python -m ...` command
        # works from any working directory. This is the template, rendered per
        # request, not a stale snapshot.
        default=str(Path(__file__).with_name("panel_template.html")),
        help="Path to HTML panel template file",
    )
    parser.add_argument("--port", type=int, default=7340)
    parser.add_argument("--host", default=None,
                        help="Bind address (default 127.0.0.1, env HAIJUNBOT_PANEL_HOST)")
    args = parser.parse_args()
    serve(args.panel, args.port, args.host)


if __name__ == "__main__":
    main()