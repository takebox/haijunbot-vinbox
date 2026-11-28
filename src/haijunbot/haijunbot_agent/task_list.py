# -*- coding: utf-8 -*-
"""Task list module.

This module provides task list management functionality, supporting dynamic multi-task management, layered context sharing, and Agent permission isolation.
"""

import os
import time
from collections import OrderedDict
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from threading import Lock
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple


class TaskStatus(Enum):
    """Task status enum."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class AgentType(Enum):
    """Agent type enum."""

    MAIN = "main"
    SUB = "sub"  # Sub-Agent; automatically identifies the code/general task type


@dataclass
class Task:
    """Task entity.

    The task entity is the minimal data unit, stored as a structured dictionary.
    """

    task_id: str
    task_name: str
    task_desc: str
    status: TaskStatus
    expected_output: str
    agent_type: AgentType
    create_time: int
    update_time: int
    dependencies: List[str] = field(default_factory=list)
    actual_output: Optional[str] = None
    model_call_count: int = 0  # Number of model calls (incremented each time a BEFORE_MODEL_CALL event fires)

    def __post_init__(self) -> None:
        """Validate field constraints."""
        # Validate the task_id format (supports the numeric ID format: task-number)
        if not self.task_id.startswith("task-"):
            raise ValueError(f"task_id format error: {self.task_id}")

        # Validate whether the numeric part is a valid number
        try:
            int(self.task_id[5:])  # Extract the numeric part after task-
        except ValueError:
            raise ValueError(f"task_id format error: {self.task_id}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dict."""
        result = asdict(self)
        result["status"] = self.status.value
        result["agent_type"] = self.agent_type.value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Create a task from a dict."""
        data = data.copy()
        data["status"] = TaskStatus(data["status"])
        data["agent_type"] = AgentType(data["agent_type"])
        return cls(**data)

    def update_status(
        self, new_status: TaskStatus, actual_output: Optional[str] = None
    ) -> bool:
        """Update the task status."""
        # Remove status transition validation; allow arbitrary status transitions
        self.status = new_status
        self.update_time = int(time.time() * 1000)
        if actual_output is not None:
            self.actual_output = actual_output
        return True


class TaskList:
    """Task list container.

    Used to manage multiple task entities, stored as an ordered dictionary.
    """

    def __init__(
        self,
        main_goal: str,
        max_active_tasks: int = 10,
        version: int = 1,
    ):
        """Initialize the task list.

        Args:
            main_goal: the user's core requirement
            max_active_tasks: the maximum number of active tasks
            version: the version number
        """
        self.main_goal = main_goal
        self.tasks: Dict[str, Task] = OrderedDict()
        self.max_active_tasks = max_active_tasks
        self.version = version
        self._lock = Lock()

    def _update_active_and_completed_lists(self) -> None:
        """Update the active and completed task lists."""
        # This method is mainly for internal maintenance; in actual use it is accessed via properties
        pass

    @property
    def active_task_ids(self) -> List[str]:
        """Get the list of active task IDs."""
        return [
            task_id
            for task_id, task in self.tasks.items()
            if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
        ]

    @property
    def completed_task_ids(self) -> List[str]:
        """Get the list of completed task IDs."""
        return [
            task_id
            for task_id, task in self.tasks.items()
            if task.status == TaskStatus.COMPLETED
        ]

    def add_task(self, task: Task) -> bool:
        """Add a task."""
        with self._lock:
            if task.task_id in self.tasks:
                return False
            # Validate the dependency relationships
            for dep_id in task.dependencies:
                if dep_id not in self.tasks:
                    return False
            self.tasks[task.task_id] = task
            self.version += 1
            return True

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task."""
        return self.tasks.get(task_id)

    def update_task(self, task_id: str, **kwargs: Any) -> bool:
        """Update a task."""
        with self._lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks[task_id]
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.update_time = int(time.time() * 1000)
            self.version += 1
            return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dict."""
        return {
            "main_goal": self.main_goal,
            "tasks": {task_id: task.to_dict() for task_id, task in self.tasks.items()},
            "max_active_tasks": self.max_active_tasks,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskList":
        """Create a task list from a dict."""
        task_list = cls(
            main_goal=data["main_goal"],
            max_active_tasks=data.get("max_active_tasks", 10),
            version=data.get("version", 1),
        )
        for task_id, task_data in data.get("tasks", {}).items():
            task = Task.from_dict(task_data)
            task_list.tasks[task_id] = task
        return task_list


class TaskListManager:
    """Task list manager.

    Implements a three-layer architecture: data layer, core logic layer, interface layer.
    """

    # Global task counter, used to generate consecutive numeric task IDs
    _global_task_counter = 0
    _global_tasklist_counter = 0
    _counter_lock = Lock()

    def __init__(self, root_dir: str, persist_dir: Optional[str] = None):
        """Initialize the task list manager.

        Args:
            root_dir: the project root directory
            persist_dir: the persistence directory, defaulting to .haijunbot/task_lists
        """
        self.root_dir = root_dir
        self.persist_dir = persist_dir or os.path.join(
            root_dir, ".haijunbot", "task_lists"
        )
        os.makedirs(self.persist_dir, exist_ok=True)

        # In-memory storage: task_list_id -> TaskList
        self.task_lists: Dict[str, TaskList] = {}

        # Permission isolation: agent_id -> Set[task_id]
        self.agent_task_mapping: Dict[str, Set[str]] = {}

        self._lock = Lock()

    @classmethod
    def _get_next_task_id(cls) -> str:
        """Get the next consecutive numeric task ID.

        Returns:
            str: a task ID in the format "task-number"
        """
        with cls._counter_lock:
            cls._global_task_counter += 1
            return f"task-{cls._global_task_counter}"

    @classmethod
    def _get_next_tasklist_id(cls) -> str:
        """Get the next consecutive numeric task list ID.

        Returns:
            str: a task list ID in the format "tasklist-number"
        """
        with cls._counter_lock:
            cls._global_tasklist_counter += 1
            return f"tasklist-{cls._global_tasklist_counter}"

    def _check_agent_permission(
        self, agent_id: str, task_id: str, is_main_agent: bool
    ) -> bool:
        """Check Agent permission.

        Args:
            agent_id: Agent ID
            task_id: the task ID
            is_main_agent: whether it is the main Agent

        Returns:
            bool: whether it has permission
        """
        if is_main_agent:
            return True
        # A sub-Agent can only access its associated tasks
        return task_id in self.agent_task_mapping.get(agent_id, set())

    # ========== Interface layer: main-Agent-exclusive interfaces ==========

    def create_task_list(
        self, main_goal: str, agent_id: str
    ) -> Tuple[Optional[str], bool, Optional[str]]:
        """Create a task list container.

        Args:
            main_goal: the user's core requirement
            agent_id: the main Agent ID

        Returns:
            Tuple[task_list_id, status, error_msg]
        """
        try:
            task_list_id = self._get_next_tasklist_id()
            task_list = TaskList(main_goal=main_goal)

            with self._lock:
                self.task_lists[task_list_id] = task_list
                # The main Agent has all permissions
                self.agent_task_mapping[agent_id] = set()

            return task_list_id, True, None
        except Exception as e:
            return None, False, str(e)

    def add_task(
        self, task_list_id: str, task_info: dict[str, Any], agent_id: str
    ) -> Tuple[Optional[str], bool, Optional[str]]:
        """Add a task to the task list.

        Args:
            task_list_id: the task list ID
            task_info: the task information dict (containing the Task required fields)
            agent_id: the main Agent ID

        Returns:
            Tuple[task_id, status, error_msg]
        """
        try:
            with self._lock:
                if task_list_id not in self.task_lists:
                    return None, False, "Task list does not exist"

                task_list = self.task_lists[task_list_id]

                # Validate required fields
                required_fields = [
                    "task_name",
                    "task_desc",
                    "expected_output",
                    "agent_type",
                ]
                missing_fields = [
                    field for field in required_fields if field not in task_info
                ]
                if missing_fields:
                    return None, False, f"Missing required field(s): {', '.join(missing_fields)}"

                # Create the task (using a consecutive numeric ID instead of UUID)
                task_id = self._get_next_task_id()
                current_time = int(time.time() * 1000)

                task = Task(
                    task_id=task_id,
                    task_name=task_info["task_name"],
                    task_desc=task_info["task_desc"],
                    status=TaskStatus.PENDING,
                    expected_output=task_info["expected_output"],
                    agent_type=AgentType(task_info["agent_type"]),
                    create_time=current_time,
                    update_time=current_time,
                    dependencies=task_info.get("dependencies", []),
                )

                # Validate the dependency relationships (check for circular dependencies)
                if not self._validate_dependencies(task_list, task):
                    return None, False, "Dependency relationship validation failed: circular or invalid dependency"

                if not task_list.add_task(task):
                    return None, False, "Failed to add task: the task ID already exists or the dependency is invalid"

                return task_id, True, None
        except ValueError as e:
            return None, False, f"Field format error: {str(e)}"
        except Exception as e:
            return None, False, str(e)

    def add_tasks(
        self, task_list_id: str, tasks_info: list[dict[str, Any]], agent_id: str
    ) -> Tuple[List[str], bool, Optional[str]]:
        """Batch-add tasks to the task list.

        Args:
            task_list_id: the task list ID
            tasks_info: a list of task information dicts (each containing the Task required fields)
            agent_id: the main Agent ID

        Returns:
            Tuple[task_ids, status, error_msg]
        """
        try:
            with self._lock:
                if task_list_id not in self.task_lists:
                    return [], False, "Task list does not exist"

                task_list = self.task_lists[task_list_id]

                if not tasks_info:
                    return [], False, "The task list is empty"

                # Validate required fields
                required_fields = [
                    "task_name",
                    "task_desc",
                    "expected_output",
                    "agent_type",
                ]

                # First validate the basic fields of all tasks
                for idx, task_info in enumerate(tasks_info):
                    missing_fields = [
                        field for field in required_fields if field not in task_info
                    ]
                    if missing_fields:
                        return (
                            [],
                            False,
                            f"Task {idx + 1} is missing required field(s): {', '.join(missing_fields)}",
                        )

                # Create all task objects (do not add to the list yet; used for dependency validation)
                current_time = int(time.time() * 1000)
                tasks_to_add = []
                task_ids = []
                # Create a mapping from task name to task ID (for dependency matching)
                name_to_id_map = {}

                # First pass: create all task objects and build the name-to-ID mapping
                for task_info in tasks_info:
                    task_id = self._get_next_task_id()
                    task_ids.append(task_id)
                    task_name = task_info["task_name"]
                    name_to_id_map[task_name] = task_id

                    task = Task(
                        task_id=task_id,
                        task_name=task_name,
                        task_desc=task_info["task_desc"],
                        status=TaskStatus.PENDING,
                        expected_output=task_info["expected_output"],
                        agent_type=AgentType(task_info["agent_type"]),
                        create_time=current_time,
                        update_time=current_time,
                        dependencies=[],  # Do not set dependencies yet; handle them later
                    )
                    tasks_to_add.append(task)

                # Second pass: process dependencies, converting task names to task IDs
                for idx, task_info in enumerate(tasks_info):
                    dependencies = task_info.get("dependencies", [])
                    if dependencies:
                        processed_deps = []
                        for dep in dependencies:
                            # If it is a task name, convert it to a task ID
                            if dep in name_to_id_map:
                                processed_deps.append(name_to_id_map[dep])
                            else:
                                # It may be a task ID, use it directly (it may also be an existing task name)
                                # Check whether it is an existing task name
                                found = False
                                for existing_task in task_list.tasks.values():
                                    if existing_task.task_name == dep:
                                        processed_deps.append(existing_task.task_id)
                                        found = True
                                        break
                                if not found:
                                    # Assume it is a task ID, use it directly
                                    processed_deps.append(dep)
                        tasks_to_add[idx].dependencies = processed_deps

                # Validate the dependency relationships of all tasks (check for circular and invalid dependencies)
                # First check whether the tasks depended upon are all in this batch or already in the task list
                task_id_map = {t.task_id: t for t in tasks_to_add}
                for task in tasks_to_add:
                    for dep_id in task.dependencies:
                        # Check whether the dependency is in the tasks to be added in this batch
                        dep_in_batch = dep_id in task_id_map
                        # Check whether the dependency is already in the task list
                        dep_in_list = task_list.get_task(dep_id) is not None
                        if not (dep_in_batch or dep_in_list):
                            return (
                                [],
                                False,
                                f"The dependency {dep_id} of task {task.task_name} does not exist",
                            )

                # Temporarily add all tasks to the task list (for circular dependency checking)
                temp_tasks = {}
                for task in tasks_to_add:
                    temp_tasks[task.task_id] = task
                    task_list.tasks[task.task_id] = task

                # Validate circular dependencies
                try:
                    for task in tasks_to_add:
                        if not self._validate_dependencies_batch(
                            task_list, task, task_id_map
                        ):
                            return (
                                [],
                                False,
                                f"Dependency validation failed for task {task.task_name}: circular dependency",
                            )
                finally:
                    # Remove the temporarily added tasks
                    for task_id in temp_tasks:
                        if task_id in task_list.tasks:
                            del task_list.tasks[task_id]

                # All validations passed; batch-add the tasks
                added_task_ids = []
                for task in tasks_to_add:
                    if task_list.add_task(task):
                        added_task_ids.append(task.task_id)
                    else:
                        # If adding a task fails, roll back the added tasks
                        for added_id in added_task_ids:
                            if added_id in task_list.tasks:
                                del task_list.tasks[added_id]
                        return (
                            [],
                            False,
                            f"Failed to add task {task.task_id}: the task ID already exists or the dependency is invalid",
                        )

                return added_task_ids, True, None
        except ValueError as e:
            return [], False, f"Field format error: {str(e)}"
        except Exception as e:
            return [], False, str(e)

    def _validate_dependencies(self, task_list: TaskList, task: Task) -> bool:
        """Validate the dependency relationships and check for circular dependencies."""
        visited = set()

        def has_cycle(current_id: str) -> bool:
            if current_id in visited:
                return True
            visited.add(current_id)
            current_task = task_list.get_task(current_id)
            if current_task:
                for dep_id in current_task.dependencies:
                    if has_cycle(dep_id):
                        return True
            visited.remove(current_id)
            return False

        # Check whether the new task's dependencies would cause a cycle
        visited.add(task.task_id)
        for dep_id in task.dependencies:
            dep_task = task_list.get_task(dep_id)
            if not dep_task:
                # The depended-upon task does not exist (may be in this batch during batch-add)
                # In that case, it is checked separately during batch-add; return True here first
                continue
            if has_cycle(dep_id):
                visited.remove(task.task_id)
                return False  # Circular dependency exists
        visited.remove(task.task_id)
        return True

    def _validate_dependencies_batch(
        self, task_list: TaskList, task: Task, batch_task_map: Dict[str, Task]
    ) -> bool:
        """Validate the dependency relationships during batch-add and check for circular dependencies."""
        visited = set()

        def has_cycle(current_id: str) -> bool:
            if current_id in visited:
                return True
            visited.add(current_id)
            # Look in the batch first, then in the task list
            current_task = batch_task_map.get(current_id) or task_list.get_task(
                current_id
            )
            if current_task:
                for dep_id in current_task.dependencies:
                    if has_cycle(dep_id):
                        return True
            visited.remove(current_id)
            return False

        # Check whether the new task's dependencies would cause a cycle
        visited.add(task.task_id)
        for dep_id in task.dependencies:
            if has_cycle(dep_id):
                visited.remove(task.task_id)
                return False  # Circular dependency exists
        visited.remove(task.task_id)
        return True

    def get_next_task(
        self, task_list_id: str, agent_id: str
    ) -> Tuple[Optional[Task], Optional[str]]:
        """Get the highest-priority pending task.

        Args:
            task_list_id: the task list ID
            agent_id: the main Agent ID

        Returns:
            Tuple[task, msg]
        """
        with self._lock:
            if task_list_id not in self.task_lists:
                return None, "Task list does not exist"

            task_list = self.task_lists[task_list_id]

            # Get all pending tasks (pending status)
            pending_tasks = [
                task
                for task in task_list.tasks.values()
                if task.status == TaskStatus.PENDING
            ]

            if not pending_tasks:
                return None, "No pending task"

            # Check the active task count limit
            active_count = len(task_list.active_task_ids)
            if active_count >= task_list.max_active_tasks:
                return None, f"Active task count has reached the upper limit ({task_list.max_active_tasks})"

            # Filter out tasks whose dependencies are satisfied
            ready_tasks = []
            completed_ids = set(task_list.completed_task_ids)

            for task in pending_tasks:
                if all(dep_id in completed_ids for dep_id in task.dependencies):
                    ready_tasks.append(task)

            if not ready_tasks:
                return None, "No pending task with satisfied dependencies"

            # Sort ascending by the numeric part of task_id
            def extract_task_number(task_id: str) -> int:
                """Extract the numeric part from task_id"""
                try:
                    return int(task_id.split("-")[1])
                except (IndexError, ValueError):
                    return 999999

            ready_tasks.sort(key=lambda t: extract_task_number(t.task_id))

            return ready_tasks[0], None

    # ========== Interface layer: interfaces shared by main Agent / sub-Agent ==========

    def update_task_status(
        self,
        task_list_id: str,
        task_id: str,
        status: str,
        agent_id: str,
        is_main_agent: bool,
        actual_output: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Update the task status and execution result.

        Args:
            task_list_id: the task list ID
            task_id: the task ID
            status: the new status
            agent_id: Agent ID
            is_main_agent: whether it is the main Agent
            actual_output: the actual output (optional)

        Returns:
            Tuple[status, msg]
        """
        try:
            new_status = TaskStatus(status)
        except ValueError:
            return False, f"Invalid status value: {status}"

        try:
            with self._lock:
                if task_list_id not in self.task_lists:
                    return False, "Task list does not exist"

                # Permission check
                if not self._check_agent_permission(agent_id, task_id, is_main_agent):
                    return False, "Insufficient permission: cannot access this task"

                task_list = self.task_lists[task_list_id]
                task = task_list.get_task(task_id)
                if not task:
                    return False, "Task does not exist"

                # Status transition
                if not task.update_status(new_status, actual_output):
                    return False, f"Invalid status transition: {task.status.value} -> {status}"

                task_list.version += 1

                return True, None
        except Exception as e:
            return False, str(e)

    def get_task_detail(
        self, task_list_id: str, task_id: str, agent_id: str, is_main_agent: bool
    ) -> Tuple[Optional[Task], bool, Optional[str]]:
        """Get the task details.

        Args:
            task_list_id: the task list ID
            task_id: the task ID
            agent_id: Agent ID
            is_main_agent: whether it is the main Agent

        Returns:
            Tuple[task, status, error_msg]
        """
        with self._lock:
            if task_list_id not in self.task_lists:
                return None, False, "Task list does not exist"

            # Permission check
            if not self._check_agent_permission(agent_id, task_id, is_main_agent):
                return None, False, "Insufficient permission: cannot access this task"

            task_list = self.task_lists[task_list_id]
            task = task_list.get_task(task_id)
            if not task:
                return None, False, "Task does not exist"

            return task, True, None

    def register_sub_agent(
        self, agent_id: str, task_ids: List[str], main_agent_id: str
    ) -> bool:
        """Register the association between a sub-Agent and tasks.

        Args:
            agent_id: the sub-Agent ID
            task_ids: the list of associated task IDs
            main_agent_id: the main Agent ID (used for permission verification)

        Returns:
            bool: whether it succeeded
        """
        with self._lock:
            # Verify the main Agent permission (simplified implementation; could be stricter in practice)
            if main_agent_id not in self.agent_task_mapping:
                return False

            self.agent_task_mapping[agent_id] = set(task_ids)
            return True

    def get_task_list(self, task_list_id: str) -> Optional[TaskList]:
        """Get the task list (internal method)."""
        return self.task_lists.get(task_list_id)

    def get_task_list_summary(self, task_list_id: str) -> Optional[dict[str, Any]]:
        """Get the task list summary information.

        Returns:
            Dict: a dict containing the task statistics
        """
        with self._lock:
            if task_list_id not in self.task_lists:
                return None

            task_list = self.task_lists[task_list_id]
            tasks = list(task_list.tasks.values())

            summary = {
                "task_list_id": task_list_id,
                "main_goal": task_list.main_goal,
                "version": task_list.version,
                "total_tasks": len(tasks),
                "pending": len([t for t in tasks if t.status == TaskStatus.PENDING]),
                "running": len([t for t in tasks if t.status == TaskStatus.RUNNING]),
                "completed": len(
                    [t for t in tasks if t.status == TaskStatus.COMPLETED]
                ),
                "failed": len([t for t in tasks if t.status == TaskStatus.FAILED]),
                "abandoned": len(
                    [t for t in tasks if t.status == TaskStatus.ABANDONED]
                ),
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "task_name": t.task_name,
                        "task_desc": t.task_desc,
                        "status": t.status.value,
                        "agent_type": t.agent_type.value,
                        "dependencies": t.dependencies,
                        "actual_output": t.actual_output,
                    }
                    for t in tasks
                ],
            }
            return summary

    def delete_task_list(self, task_list_id: str, is_main_agent: bool) -> Tuple[bool, Optional[str]]:
        """Delete a task list.

        Args:
            task_list_id: the task list ID
            is_main_agent: whether it is the main Agent

        Returns:
            Tuple[bool, Optional[str]]: (whether it succeeded, error message)
        """
        if not is_main_agent:
            return False, "Only the main Agent can delete a task list"

        with self._lock:
            if task_list_id not in self.task_lists:
                return False, f"Task list {task_list_id} does not exist"

            # Get all task_ids in the deleted task list
            task_list = self.task_lists[task_list_id]
            deleted_task_ids = set(task_list.tasks.keys())

            # Delete the task list
            del self.task_lists[task_list_id]

            # Clean up the related entries in agent_task_mapping
            # Traverse agent_task_mapping and remove the mappings of deleted tasks
            for agent_id_key in list(self.agent_task_mapping.keys()):
                task_ids = self.agent_task_mapping[agent_id_key]
                # Remove the deleted task IDs
                new_task_ids = task_ids - deleted_task_ids

                if new_task_ids:
                    self.agent_task_mapping[agent_id_key] = new_task_ids
                else:
                    # If the mapping is empty, delete the key
                    del self.agent_task_mapping[agent_id_key]

            return True, None
