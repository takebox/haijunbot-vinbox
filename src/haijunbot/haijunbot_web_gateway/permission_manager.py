"""HaijunBot permission management module

Responsibilities: permission group management, permission checking
Data storage: 4 JSON files under haijunbot_data_dir/auth/
"""

import os
import json
import uuid
import logging
from typing import Any, Optional, cast

logger = logging.getLogger(__name__)

# List of available permissions (resource -> action list), for dynamic rendering of the permission matrix in the permission group configuration UI.
# This is the single source of truth for permission definitions: maintain it here when adding/modifying permissions; the frontend obtains it via
# GET /api/permissions/schema to avoid hardcoding.
# Each resource may use "*" to mean all actions under that resource (e.g. admin:* matches admin:config, etc.).
PERMISSION_SCHEMA = {
    "admin": ["*", "config", "permissions", "plugins", "users"],
    "agent": ["*", "create", "delete", "read"],
    "file": ["*", "read", "write", "upload"],
    "terminal": ["*", "create"],
    "timer": ["*", "read", "create", "delete"],
    "node": ["*", "access"],
    "*": ["*"],
}

BUILTIN_GROUPS = {
    "sys-admin": {
        "display_name": "System Admin",
        "description": "Full system access",
        "is_builtin": True,
        "permissions": {"*:*": "allow"},
        "accessible_nodes": ["*"],
    },
    "sys-operator": {
        "display_name": "Operator",
        "description": "Agent, Terminal, Timer, Chat management",
        "is_builtin": True,
        "permissions": {
            "agent:create": "allow",
            "agent:delete": "allow",
            "terminal:*": "allow",
            "file:read": "allow",
            "file:write": "allow",
            "file:upload": "allow",
            "timer:*": "allow",
            "admin:config": "allow",
        },
        "accessible_nodes": ["*"],
    },
    "sys-developer": {
        "display_name": "Developer",
        "description": "Agent create/delete, Terminal, Chat",
        "is_builtin": True,
        "permissions": {
            "agent:create": "allow",
            "agent:delete": "allow",
            "terminal:*": "allow",
            "file:read": "allow",
            "file:write": "allow",
            "file:upload": "allow",
        },
        "accessible_nodes": [],
    },
    "sys-viewer": {
        "display_name": "Viewer",
        "description": "Read-only access",
        "is_builtin": True,
        "permissions": {
            "file:read": "allow",
        },
        "accessible_nodes": [],
    },
}


class PermissionManager:
    """Permission manager, responsible for permission group management and permission checking"""

    def __init__(self, data_dir: str):
        self._data_dir = os.path.join(data_dir, "auth")
        os.makedirs(self._data_dir, exist_ok=True)
        self._groups_file = os.path.join(self._data_dir, "groups.json")
        self._group_permissions_file = os.path.join(
            self._data_dir, "group_permissions.json"
        )
        self._user_groups_file = os.path.join(self._data_dir, "user_groups.json")
        self._user_permissions_file = os.path.join(
            self._data_dir, "user_permissions.json"
        )
        self._groups: dict[str, dict] = {}
        self._group_permissions: dict[str, dict] = {}
        self._user_groups: dict[str, list] = {}
        self._user_permissions: dict[str, dict] = {}
        self._permission_cache: dict[str, bool] = {}
        self._user_manager: Optional[Any] = (
            None  # Inject a UserManager reference for is_admin checks
        )
        self._load_data()
        self._ensure_builtin_groups()

    def _load_json(self, filepath: str) -> dict:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return cast(dict, json.load(f))
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load {filepath}: {e}")
        return {}

    def _save_json(self, filepath: str, data: dict) -> None:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"Failed to save {filepath}: {e}")

    def _load_data(self) -> None:
        self._groups = self._load_json(self._groups_file)
        self._group_permissions = self._load_json(self._group_permissions_file)
        self._user_groups = self._load_json(self._user_groups_file)
        self._user_permissions = self._load_json(self._user_permissions_file)

    def _save_groups(self) -> None:
        self._save_json(self._groups_file, self._groups)

    def _save_group_permissions(self) -> None:
        self._save_json(self._group_permissions_file, self._group_permissions)

    def _save_user_groups(self) -> None:
        self._save_json(self._user_groups_file, self._user_groups)

    def _save_user_permissions(self) -> None:
        self._save_json(self._user_permissions_file, self._user_permissions)

    def _ensure_builtin_groups(self) -> None:
        for group_id, group_def in BUILTIN_GROUPS.items():
            # Ensure the group definition exists and update it
            if group_id not in self._groups:
                self._groups[group_id] = {
                    "group_id": group_id,
                    "name": group_id,
                    "display_name": group_def["display_name"],
                    "description": group_def["description"],
                    "is_builtin": True,
                    "accessible_nodes": group_def.get("accessible_nodes", []),
                }
            else:
                # Existing builtin group: update metadata (without overwriting user-customized fields)
                existing = self._groups[group_id]
                existing["display_name"] = group_def["display_name"]
                existing["description"] = group_def["description"]
                existing["is_builtin"] = True
                if "accessible_nodes" not in existing:
                    existing["accessible_nodes"] = group_def.get("accessible_nodes", [])
            # Force-sync builtin group permissions (overwriting old configuration)
            perms = group_def["permissions"]
            self._group_permissions[group_id] = (
                {k: v for k, v in perms.items()} if isinstance(perms, dict) else {}
            )
        self._save_groups()
        self._save_group_permissions()

    def _match_permission(self, pattern: str, permission: str) -> bool:
        if pattern == "*:*":
            return True
        if pattern == permission:
            return True
        parts = pattern.split(":")
        if len(parts) == 2 and parts[1] == "*":
            return permission.startswith(parts[0] + ":")
        return False

    def set_user_manager(self, user_manager) -> None:
        """Inject a UserManager reference for is_admin checks."""
        self._user_manager = user_manager
        self._permission_cache.clear()  # Clear the cache to ensure recomputation

    def check_permission(self, user_id: str, permission: str) -> bool:
        # admin users skip all permission checks
        if self._user_manager and user_id:
            user = self._user_manager.get_user(user_id)
            if user and user.get("is_admin", False):
                return True
        cache_key = f"{user_id}:{permission}"
        if cache_key in self._permission_cache:
            return self._permission_cache[cache_key]
        result = self._compute_permission(user_id, permission)
        self._permission_cache[cache_key] = result
        return result

    def _compute_permission(self, user_id: str, permission: str) -> bool:
        user_overrides = self._user_permissions.get(user_id, {})
        for pattern, decision in user_overrides.items():
            if self._match_permission(pattern, permission):
                # Supports both booleans (True/False) and strings ("allow"/"deny")
                if decision is False or decision == "deny":
                    return False
                if decision is True or decision == "allow":
                    return True
        user_group_ids = self._user_groups.get(user_id, [])
        for group_id in user_group_ids:
            group_perms = self._group_permissions.get(group_id, {})
            for pattern, decision in group_perms.items():
                if self._match_permission(pattern, permission):
                    if decision == "allow":
                        return True
        return False

    def get_user_permissions(self, user_id: str) -> dict:
        result: dict[str, list] = {"allowed": [], "denied": []}
        user_group_ids = self._user_groups.get(user_id, [])
        for group_id in user_group_ids:
            group_perms = self._group_permissions.get(group_id, {})
            for pattern, decision in group_perms.items():
                if decision == "allow" and pattern not in result["allowed"]:
                    result["allowed"].append(pattern)
        user_overrides = self._user_permissions.get(user_id, {})
        for pattern, decision in user_overrides.items():
            if decision == "allow" and pattern not in result["allowed"]:
                result["allowed"].append(pattern)
            elif decision == "deny":
                result["denied"].append(pattern)
                if pattern in result["allowed"]:
                    result["allowed"].remove(pattern)
        return result

    # --- Group management methods ---

    def create_group(
        self, name: str, display_name: str, description: str = ""
    ) -> Optional[dict]:
        group_id = str(uuid.uuid4())
        self._groups[group_id] = {
            "group_id": group_id,
            "name": name,
            "display_name": display_name,
            "description": description,
            "is_builtin": False,
        }
        self._group_permissions[group_id] = {}
        self._save_groups()
        self._save_group_permissions()
        logger.info(f"Created group: {name} (id={group_id})")
        return self._groups[group_id]

    def update_group(self, group_id: str, **kwargs) -> Optional[dict]:
        group = self._groups.get(group_id)
        if group is None:
            return None
        allowed = {"display_name", "description", "accessible_nodes"}
        for key, value in kwargs.items():
            if key in allowed:
                group[key] = value
        self._save_groups()
        return group

    def delete_group(self, group_id: str) -> bool:
        group = self._groups.get(group_id)
        if group is None:
            return False
        if group.get("is_builtin"):
            logger.warning(f"Cannot delete builtin group: {group_id}")
            return False
        del self._groups[group_id]
        self._group_permissions.pop(group_id, None)
        for uid, gids in self._user_groups.items():
            if group_id in gids:
                gids.remove(group_id)
        self._save_groups()
        self._save_group_permissions()
        self._save_user_groups()
        self.invalidate_cache()
        return True

    def get_group(self, group_id: str) -> Optional[dict]:
        return self._groups.get(group_id)

    def list_groups(self) -> list:
        return list(self._groups.values())

    # --- Group permission methods ---

    def get_group_permissions(self, group_id: str) -> Optional[dict]:
        perms = self._group_permissions.get(group_id)
        if perms is None:
            return None
        group = self._groups.get(group_id, {})
        result = dict(perms)
        result["accessible_nodes"] = group.get("accessible_nodes", [])
        return result

    def set_group_permissions(self, group_id: str, permissions: dict) -> Optional[dict]:
        if group_id not in self._groups:
            return None
        # Extract accessible_nodes, do not store it in group_permissions
        accessible_nodes = permissions.pop("accessible_nodes", None)
        if accessible_nodes is not None:
            self._groups[group_id]["accessible_nodes"] = accessible_nodes
            self._save_groups()
        self._group_permissions[group_id] = permissions
        self._save_group_permissions()
        self.invalidate_cache()
        return self.get_group_permissions(group_id)

    # --- User group methods ---

    def get_user_groups(self, user_id: str) -> list:
        group_ids = self._user_groups.get(user_id, [])
        return [self._groups[gid] for gid in group_ids if gid in self._groups]

    def set_user_groups(self, user_id: str, group_ids: list) -> list:
        self._user_groups[user_id] = group_ids
        self._save_user_groups()
        self.invalidate_cache(user_id)
        return self.get_user_groups(user_id)

    # --- User permission overrides ---

    def get_user_overrides(self, user_id: str) -> dict:
        return self._user_permissions.get(user_id, {})

    def set_user_overrides(self, user_id: str, overrides: dict) -> dict:
        self._user_permissions[user_id] = overrides
        self._save_user_permissions()
        self.invalidate_cache(user_id)
        return self._user_permissions[user_id]

    # --- Node access checks ---

    def check_node_access(self, user_id: str, node_id: str) -> bool:
        """Check whether the user has permission to access the specified node.

        Args:
            user_id: User ID
            node_id: Target node ID

        Returns:
            True = has permission, False = no permission
        """
        if user_id == "system":
            return True
        # is_admin users have access to all nodes
        if self._user_manager and user_id:
            user = self._user_manager.get_user(user_id)
            if user and user.get("is_admin", False):
                return True
        user_group_ids = self._user_groups.get(user_id, [])
        for group_id in user_group_ids:
            group = self._groups.get(group_id, {})
            accessible_nodes = group.get("accessible_nodes", [])
            if "*" in accessible_nodes:
                return True
            if node_id in accessible_nodes:
                return True
        return False

    def get_user_accessible_nodes(self, user_id: str) -> list:
        """Get the list of all node IDs the user can access.

        Args:
            user_id: User ID

        Returns:
            A list of node IDs; ["*"] means all nodes
        """
        if user_id == "system":
            return ["*"]
        # is_admin users have access to all nodes
        if self._user_manager and user_id:
            user = self._user_manager.get_user(user_id)
            if user and user.get("is_admin", False):
                return ["*"]
        result = []
        has_all = False
        user_group_ids = self._user_groups.get(user_id, [])
        for group_id in user_group_ids:
            group = self._groups.get(group_id, {})
            accessible_nodes = group.get("accessible_nodes", [])
            if "*" in accessible_nodes:
                has_all = True
                break
            for nid in accessible_nodes:
                if nid not in result:
                    result.append(nid)
        if has_all:
            return ["*"]
        return result

    # --- Cache invalidation ---

    def invalidate_cache(self, user_id: Optional[str] = None) -> None:
        if user_id is None:
            self._permission_cache.clear()
        else:
            keys_to_remove = [
                k for k in self._permission_cache if k.startswith(f"{user_id}:")
            ]
            for k in keys_to_remove:
                del self._permission_cache[k]

    def get_permission_schema(self) -> dict:
        """Get the list of available permissions (resource -> action list), for dynamic rendering of the permission group configuration UI.

        Returns:
            dict: {resource: [actions, ...]}; "*" on a resource means all actions under that resource.
        """
        return {k: list(v) for k, v in PERMISSION_SCHEMA.items()}
