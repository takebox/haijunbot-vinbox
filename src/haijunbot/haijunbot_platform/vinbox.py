# -*- coding: utf-8 -*-
"""Vinbox platform for HaijunBot.

Vinbox is the machine HaijunBot now lives in. It already owns the model lane:

* OpenCode free models (local ``opencode serve``, no API key),
* local llama.cpp (``vinbox/models/*.gguf``),
* optional subscription providers the user enabled in Vinbox Settings,
* live browser AI as the last honest fallback.

HaijunBot must not carry its own Juglow API key. This platform asks
``app/llm/model_registry.py`` (the Vinbox model registry) for an answer, so the
same model the Haijun panel uses is the model the agent uses. No key, no
subscription, no second provider stack.

The platform is intentionally text-only and uses HaijunBot's plain-text tool
protocol (``supports_native_tool_calls`` stays False), because Vinbox's answer
path is a single prompt -> text call.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Generator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from haijunbot.haijunbot_platform.base import BasePlatform
from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_utils.output import PrettyOutput

_REGISTRY_LOCK = threading.Lock()
_REGISTRY_CACHE: Dict[str, Any] = {"module": None, "path": None}


def _candidate_registry_paths() -> List[Path]:
    """Where ``model_registry.py`` can really be, in priority order."""
    paths: List[Path] = []

    env_home = os.environ.get("VINBOX_HOME", "").strip()
    if env_home:
        paths.append(Path(env_home) / "app" / "llm" / "model_registry.py")

    paths.append(Path("/app/vinbox/app/llm/model_registry.py"))

    # When HaijunBot is vendored inside Vinbox's File Manager.
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "app" / "llm" / "model_registry.py"
        if candidate not in paths:
            paths.append(candidate)

    # Last resort: the same tree layout as this repo.
    for parent in here.parents:
        candidate = parent / "vinbox" / "app" / "llm" / "model_registry.py"
        if candidate not in paths:
            paths.append(candidate)

    return paths


def load_model_registry():
    """Load Vinbox's model registry once, without touching Vinbox's code."""
    with _REGISTRY_LOCK:
        if _REGISTRY_CACHE["module"] is not None:
            return _REGISTRY_CACHE["module"]

        last_error: Optional[Exception] = None
        for path in _candidate_registry_paths():
            if not path.is_file():
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    "vinbox_model_registry", path
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                # Register before exec so dataclasses/typing inside the module
                # can resolve themselves if they ever need to.
                sys.modules["vinbox_model_registry"] = module
                spec.loader.exec_module(module)
                _REGISTRY_CACHE["module"] = module
                _REGISTRY_CACHE["path"] = str(path)
                return module
            except Exception as exc:  # noqa: BLE001 - reported below
                last_error = exc

        searched = [str(path) for path in _candidate_registry_paths()]
        raise RuntimeError(
            "Vinbox model registry tidak ditemukan. Set VINBOX_HOME ke folder "
            f"vinbox. Dicari: {searched}. Error terakhir: {last_error}"
        )


def _text_of(message: Union[str, List[ContentBlock]]) -> str:
    if isinstance(message, str):
        return message.strip()
    parts: List[str] = []
    for block in message:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = str(block.get("text", "")).strip()
            if text:
                parts.append(text)
        elif block.get("type") == "image_url":
            parts.append("[image]")
    return "\n".join(parts).strip()


class VinboxModel(BasePlatform):
    """BasePlatform implementation backed by Vinbox's model registry."""

    def __init__(self, platform_type: str = "normal", agent: Optional[Any] = None):
        super().__init__(platform_type=platform_type, agent=agent)
        self.messages: List[Dict[str, Any]] = []
        self.system_message = ""
        self._registry = load_model_registry()
        self._last_used: Dict[str, Any] = {}
        try:
            self._last_used = dict(self._registry.current_selection())
        except Exception:
            self._last_used = {}

    # -- registry ---------------------------------------------------------
    @classmethod
    def platform_name(cls) -> str:
        return "vinbox"

    @classmethod
    def get_required_env_keys(cls) -> List[str]:
        # No API key is required. That is the whole point of Vinbox.
        return []

    # -- BasePlatform contract -------------------------------------------
    def set_model_name(self, model_name: str):
        self.model_name = model_name or "vinbox-auto"
        # A real Vinbox model id is ``<lane>:<model>``. Selecting it keeps the
        # agent and the Haijun panel on the same model.
        try:
            if ":" in self.model_name:
                self._registry.select_model(self.model_name)
        except Exception:
            pass

    def set_system_prompt(self, message: str):
        self.messages = []
        self.system_message = message or ""
        if self.system_message:
            self.messages.append({"role": "system", "content": self.system_message})

    def set_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Replace the conversation history (agent checkpoints call this)."""
        self.messages = list(messages or [])
        for msg in self.messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                self.system_message = str(msg.get("content") or "")
                break
        self._conversation_turn = sum(
            1
            for msg in self.messages
            if isinstance(msg, dict) and msg.get("role") == "user"
        )

    def get_messages(self) -> List[Dict[str, Any]]:
        return self.messages

    def trim_messages(self) -> bool:
        """Keep the system prompt and drop the 10 oldest turns."""
        if not self.messages:
            return False
        system_messages = [
            msg for msg in self.messages if msg.get("role") == "system"
        ]
        others = [msg for msg in self.messages if msg.get("role") != "system"]
        if len(others) <= 10:
            return False
        self.messages = system_messages + others[10:]
        return True

    def get_model_list(self) -> List[Tuple[str, str]]:
        rows: List[Tuple[str, str]] = []
        try:
            listing = self._registry.list_models()
            for group in listing.get("groups", []):
                for model in group.get("models", []):
                    model_id = str(model.get("id") or "")
                    if not model_id:
                        continue
                    rows.append((model_id, str(model.get("name") or model_id)))
        except Exception as exc:  # noqa: BLE001 - the panel shows a real note
            PrettyOutput.auto_print(f"⚠️ Daftar model Vinbox gagal dibaca: {exc}")

        if not rows:
            try:
                current = self._registry.current_selection()
                rows.append(
                    (
                        str(current.get("id") or "vinbox-auto"),
                        str(current.get("model") or "Vinbox"),
                    )
                )
            except Exception:
                rows.append(("vinbox-auto", "Vinbox"))
        return rows

    def name(self) -> str:
        selection = self._last_used or {}
        label = selection.get("model") or self.model_name or "Vinbox"
        return f"Vinbox · {label}"

    def delete_chat(self) -> bool:
        self.messages = []
        if self.system_message:
            self.messages.append({"role": "system", "content": self.system_message})
        return True

    # -- chat -------------------------------------------------------------
    def _prompt(self, message: Union[str, List[ContentBlock]]) -> str:
        """Flatten the conversation into Vinbox's one-prompt answer call."""
        lines: List[str] = []
        history = [
            msg
            for msg in self.messages
            if isinstance(msg, dict) and msg.get("role") != "system"
        ][-24:]
        for msg in history:
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(block.get("text", ""))
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            if content:
                lines.append(f"{msg.get('role', 'user')}: {content}")

        user_text = _text_of(message)
        lines.append(f"user: {user_text}")
        prompt = "\n".join(lines)
        # Keep the prompt bounded; a local 4k model cannot take a whole session.
        limit = int(os.environ.get("VINBOX_PROMPT_LIMIT", "12000"))
        if len(prompt) > limit:
            prompt = prompt[-limit:]
        return prompt

    def chat(
        self, message: Union[str, List[ContentBlock]]
    ) -> Generator[Tuple[str, str], None, None]:
        user_text = _text_of(message)
        if not user_text:
            raise ValueError("Vinbox: pesan kosong")

        prompt = self._prompt(message)
        system = self.system_message or None

        try:
            self._last_used = dict(self._registry.current_selection())
        except Exception:
            pass

        try:
            reply, error = self._registry.answer(
                prompt,
                system=system,
                timeout=int(os.environ.get("VINBOX_LLM_TIMEOUT", "300")),
            )
        except Exception as exc:  # noqa: BLE001 - surface the real cause
            raise RuntimeError(f"Vinbox chat gagal: {exc}") from exc

        if error:
            raise RuntimeError(f"Vinbox chat gagal: {error}")
        if not reply or not str(reply).strip():
            raise RuntimeError("Vinbox chat tidak mengembalikan jawaban")

        reply = str(reply)

        # Keep history for the next turn. Vinbox itself is stateless, so the
        # platform is the place that remembers the conversation.
        self.messages.append({"role": "user", "content": user_text})
        self.messages.append({"role": "assistant", "content": reply})

        # Stream in small chunks so HaijunBot's panel behaves like a model.
        chunk_size = max(1, int(os.environ.get("VINBOX_STREAM_CHUNK", "120")))
        for start in range(0, len(reply), chunk_size):
            yield ("content", reply[start : start + chunk_size])
