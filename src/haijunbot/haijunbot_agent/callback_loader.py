# -*- coding: utf-8 -*-
"""Callback/event loading responsibility module

The "callback/event loading" cluster of responsibilities extracted from the Agent class.
Design notes:
- Follows the existing splitting paradigm of the haijunbot_agent package (such as MemoryManager(self), HistoryCompressor(self)):
  this module holds an agent reference, and within its method bodies accesses the Agent's other capabilities via self.agent.xxx.
- The Agent side keeps thin delegating methods with the same names, ensuring the external interface remains completely unchanged.
- Circular dependencies are handled via TYPE_CHECKING.
"""

import subprocess
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import List

from haijunbot.haijunbot_agent.events import AFTER_SUMMARY
from haijunbot.haijunbot_agent.events import AFTER_TOOL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_MODEL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_SUMMARY
from haijunbot.haijunbot_agent.events import BEFORE_TOOL_CALL
from haijunbot.haijunbot_utils.config import get_after_tool_call_cb_dirs
from haijunbot.haijunbot_utils.config import get_before_model_call_cb_dirs
from haijunbot.haijunbot_utils.config import get_before_tool_call_cb_dirs
from haijunbot.haijunbot_utils.config import get_summary_cb_dirs
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.output import PrettyOutput

if TYPE_CHECKING:
    from haijunbot.haijunbot_agent import Agent


class CallbackLoader:
    """Callback/event loading responsibility implementation

    All methods are equivalent to the same-named methods formerly on the Agent class, only replacing self.xxx with self.agent.xxx.
    """

    def __init__(self, agent: "Agent") -> None:
        self.agent = agent

    def load_after_tool_callbacks(self) -> None:
        """
        Scan the Python files in after_tool_call_cb_dirs and dynamically register callbacks.
        Agreed priorities (registered on the first match):
        - Module-level callable object: after_tool_call_cb
        - Factory method returning one or more callable objects: get_after_tool_call_cb(), register_after_tool_call_cb()
        """
        try:
            dirs = get_after_tool_call_cb_dirs()
            if not dirs:
                return
            for d in dirs:
                p_dir = Path(d)
                if not p_dir.exists() or not p_dir.is_dir():
                    continue
                for file_path in p_dir.glob("*.py"):
                    if file_path.name == "__init__.py":
                        continue
                    parent_dir = str(file_path.parent)
                    added_path = False
                    try:
                        if parent_dir not in sys.path:
                            sys.path.insert(0, parent_dir)
                            added_path = True
                        module_name = file_path.stem

                        # Parse the requirements comment at the top of the file
                        requirements: List[str] = []
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                for line in f:
                                    line = line.strip()
                                    if line.startswith("# requirements:"):
                                        deps_str = line[
                                            len("# requirements:") :
                                        ].strip()
                                        if deps_str:
                                            requirements = deps_str.split()
                                        break
                        except Exception as e:
                            PrettyOutput.auto_print(
                                f"⚠️ Failed to read the callback file dependency declaration [{file_path.name}]: {e}"
                            )

                        # Install dependencies
                        if requirements:
                            PrettyOutput.auto_print(
                                f"🔧 Installing callback file dependencies [{file_path.name}]: {', '.join(requirements)}"
                            )
                            try:
                                result = subprocess.run(
                                    ["uv", "pip", "install"] + requirements,
                                    capture_output=True,
                                    text=True,
                                    timeout=120,
                                )
                                if result.returncode == 0:
                                    PrettyOutput.auto_print(
                                        f"✅ Dependencies installed successfully [{file_path.name}]"
                                    )
                                else:
                                    PrettyOutput.auto_print(
                                        f"❌ Failed to install dependencies [{file_path.name}]: {result.stderr.strip()}"
                                    )
                            except subprocess.TimeoutExpired:
                                PrettyOutput.auto_print(
                                    f"❌ Dependency installation timed out [{file_path.name}] (over 120 seconds)"
                                )
                            except Exception as e:
                                PrettyOutput.auto_print(
                                    f"❌ Dependency installation error [{file_path.name}]: {e}"
                                )

                        module = __import__(module_name)
                        PrettyOutput.auto_print(
                            f"📦 Loading callback file from the config directory: {file_path}"
                        )

                        candidates: List[Callable[[Any], None]] = []

                        # 1) Directly exported callback
                        if hasattr(module, "after_tool_call_cb"):
                            obj = getattr(module, "after_tool_call_cb")
                            if callable(obj):
                                candidates.append(obj)

                        # 2) Factory method: get_after_tool_call_cb()
                        if hasattr(module, "get_after_tool_call_cb"):
                            factory = getattr(module, "get_after_tool_call_cb")
                            if callable(factory):
                                try:
                                    ret = factory()
                                    if callable(ret):
                                        candidates.append(ret)
                                    elif isinstance(ret, (list, tuple)):
                                        for c in ret:
                                            if callable(c):
                                                candidates.append(c)
                                except Exception as e:
                                    PrettyOutput.auto_print(
                                        f"⚠️ Callback factory method get_after_tool_call_cb raised an error [{type(e).__name__}]: {e}"
                                    )

                        # 3) Factory method: register_after_tool_call_cb()
                        if hasattr(module, "register_after_tool_call_cb"):
                            factory2 = getattr(module, "register_after_tool_call_cb")
                            if callable(factory2):
                                try:
                                    ret2 = factory2()
                                    if callable(ret2):
                                        candidates.append(ret2)
                                    elif isinstance(ret2, (list, tuple)):
                                        for c in ret2:
                                            if callable(c):
                                                candidates.append(c)
                                except Exception as e:
                                    PrettyOutput.auto_print(
                                        f"⚠️ Callback factory method register_after_tool_call_cb raised an error [{type(e).__name__}]: {e}"
                                    )

                        for cb in candidates:
                            try:

                                def _make_wrapper(
                                    callback: Callable[[Any], None],
                                ) -> Callable[..., None]:
                                    def _wrapper(**kwargs: Any) -> None:
                                        try:
                                            agent = kwargs.get("agent")
                                            callback(agent)
                                        except Exception as e:
                                            PrettyOutput.auto_print(
                                                f"⚠️ Callback function raised an error [{type(e).__name__}]: {e}"
                                            )

                                    return _wrapper

                                self.agent.event_bus.subscribe(
                                    AFTER_TOOL_CALL, _make_wrapper(cb)
                                )
                            except Exception as e:
                                PrettyOutput.auto_print(
                                    f"⚠️ Callback subscription error [{type(e).__name__}]: {e}"
                                )

                    except Exception as e:
                        PrettyOutput.auto_print(f"⚠️ Failed to load callbacks from {file_path}: {e}")
                    finally:
                        if added_path:
                            try:
                                sys.path.remove(parent_dir)
                            except ValueError:
                                pass
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ An error occurred while loading the callback directory: {e}")

    def load_event_callbacks(
        self,
        event_name: str,
        config_getter: Callable[[], List[str]],
        callback_names: List[str],
        target: str = "event_bus",
    ) -> None:
        """
        Generic callback loading method, supporting scanning config directories and registering callbacks.

        Args:
            event_name: Event name (such as BEFORE_TOOL_CALL)
            config_getter: Config directory getter function (such as get_before_tool_call_cb_dirs)
            callback_names: List of callback function names (priority from high to low)
                            e.g.: ["before_tool_call_cb", "get_before_tool_call_cb", "register_before_tool_call_cb"]
            target: Callback registration target, determining where the callback is stored:
                - "event_bus": register with EventBus (notification type, default)
                - "hook": register with the hooks list (interception type; returning False intercepts)
                - "modifier": register with the modifiers list (modification type; returns the modified value)
        """
        try:
            dirs = config_getter()
            if not dirs:
                return
            for d in dirs:
                p_dir = Path(d)
                if not p_dir.exists() or not p_dir.is_dir():
                    continue
                for file_path in p_dir.glob("*.py"):
                    if file_path.name == "__init__.py":
                        continue
                    parent_dir = str(file_path.parent)
                    added_path = False
                    try:
                        if parent_dir not in sys.path:
                            sys.path.insert(0, parent_dir)
                            added_path = True
                        module_name = file_path.stem

                        # Parse the requirements comment at the top of the file
                        requirements: List[str] = []
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                for line in f:
                                    line = line.strip()
                                    if line.startswith("# requirements:"):
                                        deps_str = line[
                                            len("# requirements:") :
                                        ].strip()
                                        if deps_str:
                                            requirements = deps_str.split()
                                        break
                        except Exception as e:
                            PrettyOutput.auto_print(
                                f"⚠️ Failed to parse callback file dependencies [{file_path.name}]: {e}"
                            )

                        # Install dependencies
                        if requirements:
                            PrettyOutput.auto_print(
                                f"🔧 Installing callback file dependencies [{file_path.name}]: {', '.join(requirements)}"
                            )
                            try:
                                result = subprocess.run(
                                    ["uv", "pip", "install"] + requirements,
                                    capture_output=True,
                                    text=True,
                                    timeout=120,
                                )
                                if result.returncode == 0:
                                    PrettyOutput.auto_print(
                                        f"✅ Dependencies installed successfully [{file_path.name}]"
                                    )
                                else:
                                    PrettyOutput.auto_print(
                                        f"❌ Failed to install dependencies [{file_path.name}]: {result.stderr.strip()}"
                                    )
                            except subprocess.TimeoutExpired:
                                PrettyOutput.auto_print(
                                    f"❌ Dependency installation timed out [{file_path.name}] (over 120 seconds)"
                                )
                            except Exception as e:
                                PrettyOutput.auto_print(
                                    f"❌ Dependency installation error [{file_path.name}]: {e}"
                                )

                        module = __import__(module_name)
                        PrettyOutput.auto_print(
                            f"📦 Loading callback file from the config directory: {file_path}"
                        )

                        candidates: List[Callable] = []

                        # Try to obtain callbacks in priority order
                        for callback_name in callback_names:
                            if hasattr(module, callback_name):
                                obj = getattr(module, callback_name)
                                if callable(obj):
                                    try:
                                        ret = (
                                            obj()
                                            if callback_name.startswith(
                                                ("get_", "register_")
                                            )
                                            else obj
                                        )
                                        if callable(ret):
                                            candidates.append(ret)
                                        elif isinstance(ret, (list, tuple)):
                                            for c in ret:
                                                if callable(c):
                                                    candidates.append(c)
                                    except Exception as e:
                                        PrettyOutput.auto_print(
                                            f"⚠️ Failed to call factory method {callback_name}() [{file_path.name}]: {e}"
                                        )

                        # Register callbacks according to the target type
                        for cb in candidates:
                            try:
                                if target == "hook":
                                    # Hook: interception type, registered with the hooks list
                                    if event_name == BEFORE_TOOL_CALL:
                                        self.agent._before_tool_call_hooks.append(cb)
                                    # Also register with EventBus as a notification
                                    self.agent.event_bus.subscribe(event_name, cb)
                                elif target == "modifier":
                                    # Modifier: modification type, registered with the modifiers list
                                    if event_name == BEFORE_MODEL_CALL:
                                        self.agent._before_model_call_modifiers.append(
                                            cb
                                        )
                                    elif event_name == BEFORE_SUMMARY:
                                        self.agent._before_summary_modifiers.append(cb)
                                else:
                                    # Event: notification type, registered with EventBus
                                    self.agent.event_bus.subscribe(event_name, cb)
                            except Exception as e:
                                PrettyOutput.auto_print(
                                    f"⚠️ Failed to register callback [{file_path.name}]: {e}\n{traceback.format_exc()}"
                                )

                    except Exception as e:
                        PrettyOutput.auto_print(
                            f"⚠️ Failed to load callback file [{file_path}]: {e}\n{traceback.format_exc()}"
                        )
                    finally:
                        if added_path:
                            try:
                                sys.path.remove(parent_dir)
                            except ValueError:
                                pass
        except Exception as e:
            PrettyOutput.auto_print(
                f"⚠️ Failed to load the {event_name} callback directory: {e}\n{traceback.format_exc()}"
            )

    def load_all_event_callbacks(self) -> None:
        """
        Load all event callbacks (including before_tool_call, before_model_call, summary, etc.).
        """
        # Load before_tool_call callbacks (Hook: interception + Event notification)
        self.agent._load_event_callbacks(
            event_name=BEFORE_TOOL_CALL,
            config_getter=get_before_tool_call_cb_dirs,
            callback_names=[
                "before_tool_call_cb",
                "get_before_tool_call_cb",
                "register_before_tool_call_cb",
            ],
            target="hook",
        )

        # Load before_model_call callbacks (Modifier: modification type)
        self.agent._load_event_callbacks(
            event_name=BEFORE_MODEL_CALL,
            config_getter=get_before_model_call_cb_dirs,
            callback_names=[
                "before_model_call_cb",
                "get_before_model_call_cb",
                "register_before_model_call_cb",
            ],
            target="modifier",
        )

        # Load before_summary callbacks (Modifier: modification type)
        self.agent._load_event_callbacks(
            event_name=BEFORE_SUMMARY,
            config_getter=get_summary_cb_dirs,
            callback_names=[
                "before_summary_cb",
                "get_before_summary_cb",
                "register_before_summary_cb",
            ],
            target="modifier",
        )

        # Load after_summary callbacks (Event: notification type)
        self.agent._load_event_callbacks(
            event_name=AFTER_SUMMARY,
            config_getter=get_summary_cb_dirs,
            callback_names=[
                "after_summary_cb",
                "get_after_summary_cb",
                "register_after_summary_cb",
            ],
        )

    def fire_after_tool_call(self) -> None:
        """Fire AFTER_TOOL_CALL: emit will call all subscribed callbacks in priority order.

        (Previously it manually iterated _listeners before emit, causing the same batch of callbacks to be dispatched twice)
        """
        try:
            self.agent.event_bus.emit(
                AFTER_TOOL_CALL,
                agent=self.agent,
                current_response="",
                need_return=False,
                tool_prompt="",
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.__init__", function="_fire_after_tool_call"
            )
            pass
