# -*- coding: utf-8 -*-
"""Timer tool module

Supports scheduled tool execution, scheduled addition of prompts to multiline input, and delayed tool execution.
Supports relative/absolute/interval timing; the timer is a global instance and must be persisted when a session is saved/restored.
"""

import json
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from haijunbot.haijunbot_utils.output import PrettyOutput


# Global timer manager singleton
_timer_manager_instance: Optional["TimerManager"] = None
_timer_manager_lock = threading.Lock()


def get_timer_manager() -> "TimerManager":
    """Get the global timer manager singleton"""
    global _timer_manager_instance
    with _timer_manager_lock:
        if _timer_manager_instance is None:
            _timer_manager_instance = TimerManager()
        return _timer_manager_instance


class TimerTask:
    """Scheduled task data class"""

    def __init__(
        self,
        task_id: str,
        task_type: str,
        time_type: str,
        time_value: Any,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        prompt_text: Optional[str] = None,
        interval_seconds: Optional[float] = None,
        status: str = "pending",
        created_at: Optional[str] = None,
        next_fire_time: Optional[str] = None,
    ) -> None:
        self.task_id = task_id
        self.task_type = task_type  # tool_call / prompt / delayed_tool_call
        self.time_type = time_type  # relative / absolute / interval
        self.time_value = time_value
        self.tool_name = tool_name
        self.tool_args = tool_args or {}
        self.prompt_text = prompt_text
        self.interval_seconds = interval_seconds
        self.status = status  # pending / running / completed / cancelled
        self.created_at = created_at or datetime.now().isoformat()
        self.next_fire_time = next_fire_time
        self._timer: Optional[threading.Timer] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "time_type": self.time_type,
            "time_value": self.time_value,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "prompt_text": self.prompt_text,
            "interval_seconds": self.interval_seconds,
            "status": self.status,
            "created_at": self.created_at,
            "next_fire_time": self.next_fire_time,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimerTask":
        """Deserialize from a dict"""
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            time_type=data["time_type"],
            time_value=data["time_value"],
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args", {}),
            prompt_text=data.get("prompt_text"),
            interval_seconds=data.get("interval_seconds"),
            status=data.get("status", "pending"),
            created_at=data.get("created_at"),
            next_fire_time=data.get("next_fire_time"),
        )


class TimerManager:
    """Timer manager (global singleton)

    Manages the creation, scheduling, cancellation, and persistence of all scheduled tasks.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, TimerTask] = {}
        self._lock = threading.Lock()
        self._registry = None  # Lazy fetch to avoid circular imports

    def _get_registry(self):
        """Lazily fetch the tool registry"""
        if self._registry is None:
            from haijunbot.haijunbot_tools.registry import ToolRegistry

            self._registry = ToolRegistry()
        return self._registry

    def _calculate_delay(self, time_type: str, time_value: Any) -> float:
        """Calculate the delay in seconds until the next fire"""
        if time_type == "relative":
            delay = float(time_value)
            if delay <= 0:
                raise ValueError("Relative time must be greater than 0")
            return delay
        elif time_type == "absolute":
            target_time = datetime.fromisoformat(time_value)
            delay = (target_time - datetime.now()).total_seconds()
            if delay <= 0:
                raise ValueError(f"Absolute time has already passed: {time_value}")
            return delay
        elif time_type == "interval":
            interval = float(time_value)
            if interval <= 0:
                raise ValueError("Interval must be greater than 0")
            return interval
        else:
            raise ValueError(f"Invalid time type: {time_type}")

    def add_task(
        self,
        task_type: str,
        time_type: str,
        time_value: Any,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        prompt_text: Optional[str] = None,
        interval_seconds: Optional[float] = None,
    ) -> TimerTask:
        """Add a scheduled task"""
        if task_type in ("tool_call", "delayed_tool_call") and not tool_name:
            raise ValueError(f"Task type {task_type} must specify tool_name")
        if task_type == "prompt" and not prompt_text:
            raise ValueError("prompt type tasks must specify prompt_text")
        if time_type == "interval" and not interval_seconds:
            interval_seconds = float(time_value)

        task_id = str(uuid.uuid4())[:8]
        delay = self._calculate_delay(time_type, time_value)
        next_fire = (datetime.now() + timedelta(seconds=delay)).isoformat()

        task = TimerTask(
            task_id=task_id,
            task_type=task_type,
            time_type=time_type,
            time_value=time_value,
            tool_name=tool_name,
            tool_args=tool_args or {},
            prompt_text=prompt_text,
            interval_seconds=interval_seconds,
            status="pending",
            next_fire_time=next_fire,
        )

        with self._lock:
            self._tasks[task_id] = task
            self._schedule_task(task, delay)

        return task

    def _schedule_task(self, task: TimerTask, delay: float) -> None:
        """Schedule a scheduled task"""
        if task._timer is not None:
            task._timer.cancel()
        task._timer = threading.Timer(delay, self._execute_task, args=(task.task_id,))
        task._timer.daemon = True
        task._timer.start()
        task.status = "pending"

    def _execute_task(self, task_id: str) -> None:
        """Execute the scheduled task callback"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status == "cancelled":
                return
        try:
            task.status = "running"
            if task.task_type == "prompt":
                self._execute_prompt_task(task)
            elif task.task_type in ("tool_call", "delayed_tool_call"):
                self._execute_tool_task(task)
            if task.time_type == "interval" and task.status != "cancelled":
                interval = task.interval_seconds or float(task.time_value)
                next_fire = (datetime.now() + timedelta(seconds=interval)).isoformat()
                task.next_fire_time = next_fire
                task.status = "pending"
                self._schedule_task(task, interval)
            else:
                task.status = "completed"
        except Exception as e:
            task.status = "completed"
            PrettyOutput.auto_print(f"Scheduled task {task_id} failed to execute: {e}")

    def _inject_message(self, message: str, description: str = "") -> None:
        """Unified message injection method

        Args:
            message: the message content to inject
            description: description information used for logging (e.g., "Scheduled prompt", "Tool execution result")
        """
        from haijunbot.haijunbot_utils.globals import add_input_buffer, input_inject_callback

        # Prefer the input injection callback (if the Agent is waiting for input)
        if input_inject_callback is not None:
            input_inject_callback(message)
        else:
            add_input_buffer(message)

        # Print the log
        if description:
            PrettyOutput.auto_print(description)

    def _execute_prompt_task(self, task: TimerTask) -> None:
        """Execute a prompt injection task"""
        try:
            # Build the injection message, including timer information
            inject_message = f"[Timer#{task.task_id[:8]}|{task.task_type}|{task.time_type}] {task.prompt_text}"
            self._inject_message(inject_message, f"Scheduled prompt injected: {task.prompt_text}")
        except Exception as e:
            PrettyOutput.auto_print(f"Prompt injection failed: {e}")

    def _execute_tool_task(self, task: TimerTask) -> None:
        """Execute a tool call task"""
        try:
            registry = self._get_registry()
            tool = registry.get_tool(task.tool_name)
            if tool:
                PrettyOutput.auto_print(f"Scheduled tool execution: {task.tool_name}")
                result = tool.func(task.tool_args)

                # Build the result message
                result_message = (
                    result.get("message", str(result))
                    if result
                    else "Tool execution completed (no return value)"
                )
                PrettyOutput.auto_print(f"Tool execution result: {result_message}")

                inject_message = f"[Timer#{task.task_id[:8]}|{task.task_type}|{task.time_type}] Tool {task.tool_name} execution completed\nResult: {result_message}"
                self._inject_message(
                    inject_message, f"Tool execution result injected: {result_message}"
                )
            else:
                error_message = f"Tool does not exist: {task.tool_name}"
                PrettyOutput.auto_print(error_message)
                inject_message = f"[Timer#{task.task_id[:8]}|{task.task_type}|{task.time_type}] {error_message}"
                self._inject_message(inject_message, f"Tool error injected: {error_message}")
        except Exception as e:
            error_message = f"Tool execution failed: {e}"
            PrettyOutput.auto_print(error_message)
            try:
                inject_message = f"[Timer#{task.task_id[:8]}|{task.task_type}|{task.time_type}] {error_message}"
                self._inject_message(inject_message, f"Tool exception injected: {error_message}")
            except Exception:
                pass  # Ignore secondary exceptions

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task._timer is not None:
                task._timer.cancel()
            task.status = "cancelled"
            return True

    def list_tasks(self) -> list[Dict[str, Any]]:
        """List all scheduled tasks"""
        with self._lock:
            return [
                task.to_dict()
                for task in self._tasks.values()
                if task.status != "cancelled"
            ]

    def clear_tasks(self) -> int:
        """Clear all scheduled tasks"""
        with self._lock:
            count = 0
            for task in self._tasks.values():
                if task._timer is not None:
                    task._timer.cancel()
                if task.status != "cancelled":
                    count += 1
                task.status = "cancelled"
            self._tasks.clear()
            return count

    def get_state(self) -> Dict[str, Any]:
        """Get the timer state for persistence"""
        with self._lock:
            tasks_data = []
            for task in self._tasks.values():
                if task.status != "cancelled":
                    tasks_data.append(task.to_dict())
            return {"tasks": tasks_data}

    def restore_state(self, state_data: Dict[str, Any]) -> None:
        """Restore the timer state from persisted data"""
        tasks_data = state_data.get("tasks", [])
        now = datetime.now()
        restored_count = 0
        skipped_count = 0
        for task_data in tasks_data:
            task = TimerTask.from_dict(task_data)
            # Skip cancelled or completed tasks: they should not continue firing after restoration
            if task.status in ("cancelled", "completed"):
                skipped_count += 1
                continue
            if task.next_fire_time:
                try:
                    next_fire = datetime.fromisoformat(task.next_fire_time)
                    if next_fire <= now:
                        if task.time_type == "interval":
                            interval = task.interval_seconds or float(task.time_value)
                            delay = interval
                        else:
                            skipped_count += 1
                            continue
                    else:
                        delay = (next_fire - now).total_seconds()
                except (ValueError, TypeError):
                    skipped_count += 1
                    continue
            else:
                skipped_count += 1
                continue
            with self._lock:
                self._tasks[task.task_id] = task
                self._schedule_task(task, delay)
            restored_count += 1
        if restored_count > 0 or skipped_count > 0:
            msg = f"Timer restored: {restored_count} task(s)"
            if skipped_count > 0:
                msg += f", {skipped_count} expired and skipped"
            PrettyOutput.auto_print(msg)


class TimerTool:
    """Timer tool

    Supports scheduled injection of prompts into multiline input, and relative/absolute/interval timing.
    Note: the scheduled tool execution feature has been integrated into tool calls; you can add after/at/loop arguments to the arguments of any tool call.
    """

    name = "timer"
    description = "Timer tool: supports scheduled prompt injection and manages scheduled tasks (cancel/list/clear)"
    parameters = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "description": "Operation type: add (add a scheduled prompt task), cancel (cancel a task), list (list all tasks), clear (clear all tasks)",
                "enum": ["add", "cancel", "list", "clear"],
            },
            "task_type": {
                "type": "string",
                "description": "Task type (required for the add operation): only supports prompt (scheduled prompt injection)",
                "enum": ["prompt"],
            },
            "time_type": {
                "type": "string",
                "description": "Time type (required for the add operation): relative (relative seconds), absolute (absolute time in ISO format), interval (interval seconds)",
                "enum": ["relative", "absolute", "interval"],
            },
            "time_value": {
                "type": "string",
                "description": "Time value (required for the add operation): seconds for relative, an ISO time string for absolute, interval seconds for interval",
            },
            "prompt_text": {
                "type": "string",
                "description": "Prompt text (required for the add operation)",
            },
            "task_id": {
                "type": "string",
                "description": "Task ID (required for the cancel operation)",
            },
        },
        "required": ["operation"],
    }

    def __init__(self) -> None:
        """Initialize the timer tool"""
        self.manager = get_timer_manager()

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a timer operation"""
        operation = args.get("operation", "")
        if operation == "add":
            return self._handle_add(args)
        elif operation == "cancel":
            return self._handle_cancel(args)
        elif operation == "list":
            return self._handle_list()
        elif operation == "clear":
            return self._handle_clear()
        else:
            return {"success": False, "message": f"Invalid operation: {operation}"}

    def _handle_add(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Handle adding a scheduled prompt task"""
        task_type = kwargs.get("task_type")
        time_type = kwargs.get("time_type")
        time_value = kwargs.get("time_value")
        prompt_text = kwargs.get("prompt_text")

        if not task_type:
            return {"success": False, "message": "The add operation must specify task_type"}
        if task_type != "prompt":
            return {
                "success": False,
                "message": "The timer tool only supports prompt type tasks. For scheduled tool execution, add after/at/loop arguments to the arguments of the tool call.",
            }
        if not time_type:
            return {"success": False, "message": "The add operation must specify time_type"}
        if not time_value:
            return {"success": False, "message": "The add operation must specify time_value"}
        if not prompt_text:
            return {"success": False, "message": "prompt type tasks must specify prompt_text"}

        try:
            task = self.manager.add_task(
                task_type=task_type,
                time_type=time_type,
                time_value=time_value,
                prompt_text=prompt_text,
                interval_seconds=float(kwargs.get("time_value", 0))
                if time_type == "interval"
                else None,
            )
            result_data = {
                "task_id": task.task_id,
                "next_fire_time": task.next_fire_time,
            }
            return {
                "success": True,
                "stdout": json.dumps(result_data, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        except ValueError as e:
            return {"success": False, "stdout": "", "stderr": str(e)}

    def _handle_cancel(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cancelling a scheduled task"""
        task_id = kwargs.get("task_id", "")
        if not task_id:
            return {"success": False, "message": "The cancel operation must specify task_id"}
        if self.manager.cancel_task(task_id):
            return {
                "success": True,
                "stdout": f"Scheduled task {task_id} cancelled",
                "stderr": "",
            }
        return {"success": False, "stdout": "", "stderr": f"Scheduled task {task_id} does not exist"}

    def _handle_list(self) -> Dict[str, Any]:
        """Handle listing scheduled tasks"""
        tasks = self.manager.list_tasks()
        if not tasks:
            return {
                "success": True,
                "stdout": json.dumps(
                    {"tasks": [], "message": "There are currently no scheduled tasks"},
                    ensure_ascii=False,
                    indent=2,
                ),
                "stderr": "",
            }
        result_data = {
            "tasks": tasks,
            "total": len(tasks),
        }
        return {
            "success": True,
            "stdout": json.dumps(result_data, ensure_ascii=False, indent=2),
            "stderr": "",
        }

    def _handle_clear(self) -> Dict[str, Any]:
        """Handle clearing all scheduled tasks"""
        count = self.manager.clear_tasks()
        return {"success": True, "stdout": f"Cleared {count} scheduled task(s)", "stderr": ""}
