# HaijunBot Multi-user Authentication and Group Permission Management Plan

## 1. Overview

### 1.1 Goals

Introduce a complete user management system and fine-grained permission control into the HaijunBot Web Gateway, achieving:

- Independent user registration/login, with an independent password per user
- Admin CRUD management of users
- Group permission management, with permission granularity down to the Agent level
- Multi-dimensional permission control: Agent operations, terminal access, file access, config sync, chat rooms, etc.

### 1.2 Design Principles

- **Least privilege**: no permissions by default; explicit grants only
- **Group-first**: permissions are assigned per group; users inherit group permissions, with user-level overrides supported
- **Backward compatibility**: smooth transition for the existing single-Token mode
- **Performance-first**: permission checks use an in-memory cache, avoiding a DB query on every request

---

## 2. User Management

### 2.1 User Model

```text
User {
  user_id:        str       # unique ID, UUID
  username:       str       # username, unique, 3-32 characters
  password_hash:  str       # bcrypt hash
  display_name:   str       # display name
  is_admin:       bool      # whether admin (built-in role, cannot be deleted)
  status:         str       # active / disabled / locked
  created_at:     datetime
  updated_at:     datetime
  last_login_at:  datetime
  locked_reason:  str       # lock reason (multiple failures / admin lock)
  login_fail_count: int     # consecutive login failure count
}
```

### 2.2 Initial Administrator

On the first system startup, an initial administrator account is created automatically:

- Username: `admin`
- Password: read from the environment variable `HAIJUNBOT_ADMIN_PASSWORD`; if not set, a random password is generated and output to the log
- Password change is enforced after the first login

### 2.3 User Management APIs (admin only)

| API                                         | Method | Description                                                          |
| ------------------------------------------- | ------ | ------------------------------------------------------------------- |
| `/api/admin/users`                          | GET    | list all users (supports pagination/search)                         |
| `/api/admin/users`                          | POST   | create a user                                                       |
| `/api/admin/users/{user_id}`                | GET    | get user details                                                    |
| `/api/admin/users/{user_id}`                | PATCH  | modify user info (reset password / change status / change display name) |
| `/api/admin/users/{user_id}`                | DELETE | delete a user (cannot delete self / cannot delete the last admin)   |
| `/api/admin/users/{user_id}/password/reset` | POST   | reset a user's password                                             |
| `/api/admin/users/{user_id}/groups`         | GET    | get the list of groups the user belongs to                          |
| `/api/admin/users/{user_id}/groups`         | PUT    | set the user's groups (replace)                                     |
| `/api/admin/users/{user_id}/permissions`    | GET    | get the user's effective permissions (group inheritance + user overrides) |

### 2.4 Self-service User APIs

| API                  | Method | Description                                |
| -------------------- | ------ | ------------------------------------------ |
| `/api/auth/login`    | POST   | login (changed to username+password)       |
| `/api/auth/logout`   | POST   | logout (revokes the Token)                 |
| `/api/auth/me`       | GET    | get the current user's info                |
| `/api/auth/password` | PUT    | change one's own password                  |

### 2.5 Login Flow Changes

**Current flow**:

```text
POST /api/auth/login {password} -> {token: "globally unique Token"}
```

**New flow**:

```text
POST /api/auth/login {username, password} -> {token: "JWT containing user_id", expires_in: 86400}
```

The Token changes to JWT format; the payload contains:

```json
{
  "user_id": "uuid",
  "username": "alice",
  "is_admin": false,
  "iat": 1234567890,
  "exp": 1234654290
}
```

---

## 3. Group Permission Management

### 3.1 Permission Group Model

```text
Group {
  group_id:       str       # unique ID, UUID (system groups prefixed with sys-)
  group_name:     str       # group name, unique
  description:    str       # group description
  is_system:      bool      # built-in system group, cannot be deleted
  created_at:     datetime
  updated_at:     datetime
}
```

### 3.2 Built-in Permission Groups

| Group name        | group_id       | Description                                                      |
| ----------------- | -------------- | ---------------------------------------------------------------- |
| `administrators`  | `sys-admin`    | super admin; has all permissions; cannot be modified             |
| `operators`       | `sys-operator` | operations staff; can manage Agents/nodes/terminals; cannot manage users |
| `developers`      | `sys-developer`| developers; can create Agents / edit code / use terminals        |
| `viewers`         | `sys-viewer`   | read-only users; can only view Agent status/logs                 |
| `chat-users`      | `sys-chat`     | chat room users; can only use chat functionality                 |

### 3.3 Permission Group Management APIs (admin only)

| API                                        | Method | Description                              |
| ------------------------------------------ | ------ | ----------------------------------------- |
| `/api/admin/groups`                        | GET    | list all groups                          |
| `/api/admin/groups`                        | POST   | create a custom group                    |
| `/api/admin/groups/{group_id}`             | GET    | get group details                        |
| `/api/admin/groups/{group_id}`             | PATCH  | modify group info                        |
| `/api/admin/groups/{group_id}`             | DELETE | delete a custom group (system groups cannot be deleted) |
| `/api/admin/groups/{group_id}/permissions` | GET    | get the group's permission configuration |
| `/api/admin/groups/{group_id}/permissions` | PUT    | set the group's permission configuration |
| `/api/admin/groups/{group_id}/members`     | GET    | get the group's member list              |

---

## 4. Permission System Design

### 4.1 Permission Categories

Permissions are split into two layers: **global permissions** and **resource-level permissions**.

#### 4.1.1 Global Permissions

Controls whether a user can use a category of functionality:

| Permission identifier | Description                                                         | Default |
| --------------------- | ------------------------------------------------------------------- | ------- |
| `agent.create`        | create an Agent                                                     | deny    |
| `agent.list_all`      | view all users' Agents (otherwise only one's own + authorized ones) | deny    |
| `agent.delete_own`    | delete Agents created by oneself                                    | deny    |
| `agent.delete_any`    | delete any Agent                                                    | deny    |
| `agent.stop_own`      | stop Agents created by oneself                                      | deny    |
| `agent.stop_any`      | stop any Agent                                                      | deny    |
| `agent.regenerate_own`| regenerate one's own Agents                                         | deny    |
| `agent.regenerate_any`| regenerate any Agent                                                | deny    |
| `terminal.open`       | open a terminal                                                     | deny    |
| `terminal.list`       | view the terminal list                                              | deny    |
| `terminal.delete_own` | delete terminals created by oneself                                 | deny    |
| `terminal.delete_any` | delete any terminal                                                 | deny    |
| `file.read`           | read file content                                                   | deny    |
| `file.write`          | write / edit files                                                  | deny    |
| `file.browse`         | browse directory structures                                         | deny    |
| `config.sync`         | sync node configuration                                             | deny    |
| `config.view`         | view node configuration                                             | deny    |
| `node.view`           | view node status                                                    | deny    |
| `node.restart`        | restart a node service                                              | deny    |
| `node.code_update`    | update node code                                                    | deny    |
| `node.secret`         | get the node connection secret                                      | deny    |
| `timer.create`        | create a scheduled task                                             | deny    |
| `timer.list`          | view scheduled tasks                                                | deny    |
| `timer.delete_own`    | delete scheduled tasks created by oneself                           | deny    |
| `timer.delete_any`    | delete any scheduled task                                           | deny    |
| `chat.join`           | join a chat room                                                    | deny    |
| `chat.create_room`    | create a chat room                                                  | deny    |
| `chat.delete_own_room`| delete chat rooms created by oneself                                | deny    |
| `chat.send_message`   | send chat messages                                                  | deny    |
| `chat.private_message`| send private messages                                               | deny    |
| `group.create`        | create an Agent communication group                                 | deny    |
| `group.join`          | join a group                                                        | deny    |
| `group.manage_own`    | manage groups created by oneself                                    | deny    |
| `data.read`           | read KV storage data                                                | deny    |
| `data.write`          | write KV storage data                                               | deny    |
| `data.delete`          | delete KV storage data                                              | deny    |
| `user.manage`         | user management (CRUD)                                              | deny    |
| `group.manage`        | permission group management                                         | deny    |
| `permission.manage`   | permission assignment management                                    | deny    |
| `model.view`          | view model group configuration                                      | deny    |
| `completion.use`      | use code completion                                                 | deny    |
| `search.use`          | use global search                                                   | deny    |

#### 4.1.2 Resource Permissions

On top of global permissions, fine-grained control over specific resource instances. Currently only Agents support resource-level permissions:

```json
{
  "resource_type": "agent",
  "resource_id": "agent-uuid",
  "permissions": {
    "agent.view": true,
    "agent.chat": true,
    "agent.edit_config": false,
    "agent.stop": false,
    "agent.delete": false,
    "agent.read_log": true,
    "agent.read_session": true,
    "agent.write_session": false
  }
}
```

**Agent resource-level permission items**:

| Permission identifier | Description                 |
| --------------------- | ---------------------------- |
| `agent.view`          | view Agent details          |
| `agent.chat`          | chat with the Agent         |
| `agent.edit_config`   | modify the Agent config     |
| `agent.stop`          | stop the Agent              |
| `agent.delete`        | delete the Agent            |
| `agent.read_log`      | view the Agent's logs       |
| `agent.read_session`  | view the Agent's conversation history |
| `agent.write_session` | write / modify the Agent's conversations |

**Permission inheritance rules**:

- The Agent creator automatically gets all resource-level permissions for that Agent
- The `agent.delete_any` global permission can override the `agent.delete` resource-level permission
- The `agent.stop_any` global permission can override the `agent.stop` resource-level permission
- Resource-level permissions only apply to non-creators

#### 4.1.3 Permission Evaluation Priority

```text
1. Admin bypass: is_admin=true -> all allowed
2. Explicit deny: user-level deny -> final deny
3. Explicit allow: user-level allow -> final allow
4. Group inheritance allow: allow in any member group -> allow
5. Resource-level allow: allow in the resource ACL -> allow
6. Default deny: no matching rule -> deny
```

---

## 5. Built-in Group Permission Mapping

### 5.1 administrators (sys-admin)

All permissions = `allow`, cannot be modified.

### 5.2 operators (sys-operator)

| Permission              | Value |
| ----------------------- | ----- |
| `agent.create`          | allow |
| `agent.list_all`        | allow |
| `agent.delete_own`      | allow |
| `agent.delete_any`      | allow |
| `agent.stop_own`        | allow |
| `agent.stop_any`        | allow |
| `agent.regenerate_own`  | allow |
| `agent.regenerate_any`  | allow |
| `terminal.open`         | allow |
| `terminal.list`         | allow |
| `terminal.delete_own`   | allow |
| `terminal.delete_any`   | allow |
| `file.read`             | allow |
| `file.write`            | allow |
| `file.browse`           | allow |
| `config.sync`           | allow |
| `config.view`           | allow |
| `node.view`             | allow |
| `node.restart`          | allow |
| `node.code_update`      | allow |
| `node.secret`           | allow |
| `timer.create`          | allow |
| `timer.list`            | allow |
| `timer.delete_own`      | allow |
| `timer.delete_any`      | allow |
| `chat.join`             | allow |
| `chat.create_room`      | allow |
| `chat.delete_own_room`  | allow |
| `chat.send_message`     | allow |
| `chat.private_message`  | allow |
| `group.create`          | allow |
| `group.join`            | allow |
| `group.manage_own`      | allow |
| `data.read`             | allow |
| `data.write`            | allow |
| `data.delete`           | allow |
| `model.view`            | allow |
| `completion.use`        | allow |
| `search.use`            | allow |

### 5.3 developers (sys-developer)

| Permission              | Value |
| ----------------------- | ----- |
| `agent.create`          | allow |
| `agent.list_all`        | deny  |
| `agent.delete_own`      | allow |
| `agent.delete_any`      | deny  |
| `agent.stop_own`        | allow |
| `agent.stop_any`        | deny  |
| `agent.regenerate_own`  | allow |
| `agent.regenerate_any`  | deny  |
| `terminal.open`         | allow |
| `terminal.list`         | allow |
| `terminal.delete_own`   | allow |
| `terminal.delete_any`   | deny  |
| `file.read`             | allow |
| `file.write`            | allow |
| `file.browse`           | allow |
| `config.sync`           | deny  |
| `config.view`           | allow |
| `node.view`             | allow |
| `node.restart`          | deny  |
| `node.code_update`      | deny  |
| `node.secret`           | deny  |
| `timer.create`          | allow |
| `timer.list`            | allow |
| `timer.delete_own`      | allow |
| `timer.delete_any`      | deny  |
| `chat.join`             | allow |
| `chat.create_room`      | allow |
| `chat.delete_own_room`  | allow |
| `chat.send_message`     | allow |
| `chat.private_message`  | allow |
| `group.create`          | allow |
| `group.join`            | allow |
| `group.manage_own`      | allow |
| `data.read`             | allow |
| `data.write`            | allow |
| `data.delete`           | deny  |
| `model.view`            | allow |
| `completion.use`        | allow |

### 5.4 viewers (sys-viewer)

| Permission              | Value |
| ----------------------- | ----- |
| `agent.create`          | deny  |
| `agent.list_all`        | allow |
| `agent.delete_own`      | deny  |
| `agent.delete_any`      | deny  |
| `agent.stop_own`        | deny  |
| `agent.stop_any`        | deny  |
| `agent.regenerate_own`  | deny  |
| `agent.regenerate_any`  | deny  |
| `terminal.open`         | deny  |
| `terminal.list`         | deny  |
| `terminal.delete_own`   | deny  |
| `terminal.delete_any`   | deny  |
| `file.read`             | allow |
| `file.write`            | deny  |
| `file.browse`           | allow |
| `config.sync`           | deny  |
| `config.view`           | deny  |
| `node.view`             | allow |
| `node.restart`          | deny  |
| `node.code_update`      | deny  |
| `node.secret`           | deny  |
| `timer.create`          | deny  |
| `timer.list`            | allow |
| `timer.delete_own`      | deny  |
| `timer.delete_any`      | deny  |
| `chat.join`             | deny  |
| `chat.create_room`      | deny  |
| `chat.delete_own_room`  | deny  |
| `chat.send_message`     | deny  |
| `chat.private_message`  | deny  |
| `group.create`          | deny  |
| `group.join`            | deny  |
| `group.manage_own`      | deny  |
| `data.read`             | allow |
| `data.write`            | deny  |
| `data.delete`           | deny  |
| `model.view`            | allow |
| `completion.use`        | deny  |
| `search.use`            | allow |

### 5.5 chat-users (sys-chat)

| Permission              | Value |
| ----------------------- | ----- |
| `agent.create`          | deny  |
| `agent.list_all`        | deny  |
| `agent.delete_own`      | deny  |
| `agent.delete_any`      | deny  |
| `agent.stop_own`        | deny  |
| `agent.stop_any`        | deny  |
| `agent.regenerate_own`  | deny  |
| `agent.regenerate_any`  | deny  |
| `terminal.open`         | deny  |
| `terminal.list`         | deny  |
| `terminal.delete_own`   | deny  |
| `terminal.delete_any`   | deny  |
| `file.read`             | deny  |
| `file.write`            | deny  |
| `file.browse`           | deny  |
| `config.sync`           | deny  |
| `config.view`           | deny  |
| `node.view`             | deny  |
| `node.restart`          | deny  |
| `node.code_update`      | deny  |
| `node.secret`           | deny  |
| `timer.create`          | deny  |
| `timer.list`            | deny  |
| `timer.delete_own`      | deny  |
| `timer.delete_any`      | deny  |
| `chat.join`             | allow |
| `chat.create_room`      | allow |
| `chat.delete_own_room`  | allow |
| `chat.send_message`     | allow |
| `chat.private_message`  | allow |
| `group.create`          | deny  |
| `group.join`            | deny  |
| `group.manage_own`      | deny  |
| `data.read`             | deny  |
| `data.write`            | deny  |
| `data.delete`           | deny  |
| `model.view`            | deny  |

---

## 6. Permission Check Flow

### 6.1 Request Handling Flow

```text
Client request -> parse JWT -> get user_id -> permission check -> execute / deny
```

Detailed steps:

1. **Token parsing**: extract the Bearer Token from the request Header; verify the JWT signature and validity
2. **User loading**: get user_id from the JWT payload; load the user info and permission cache
3. **Permission check**: match the required permission identifiers based on the request's API path and operation type
4. **Resource-level check** (e.g. when a specific Agent is involved): check the user's ACL for that resource
5. **Decision**: proceed if allowed; return 403 if denied

### 6.2 Permission Check Middleware

Extend `_check_auth` in `gateway.py` into `_check_auth_and_permission`:

```python
async def _check_auth_and_permission(
    self,
    request,
    required_permission: str,
    resource_type: str = None,
    resource_id: str = None
) -> tuple[bool, Optional[dict]]:
    """Checks authentication and permission

    Returns:
        (allowed, user_info)
    """
    # 1. Authentication check
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return False, None

    # 2. JWT verification
    payload = validate_jwt_token(token)
    if not payload:
        return False, None

    user_id = payload["user_id"]
    user = user_store.get_user(user_id)
    if not user or user.status != "active":
        return False, None

    # 3. Admin bypass
    if user.is_admin:
        return True, {"user_id": user_id, "username": user.username, "is_admin": True}

    # 4. Global permission check
    if not permission_manager.check_permission(user_id, required_permission):
        return False, None

    # 5. Resource-level permission check
    if resource_type and resource_id:
        if not permission_manager.check_resource_permission(
            user_id, resource_type, resource_id, required_permission
        ):
            return False, None

    return True, {"user_id": user_id, "username": user.username, "is_admin": False}
```

### 6.3 API-to-Permission Mapping Table

| API path                     | Method | Required permission                      | Resource type |
| ---------------------------- | ------ | ---------------------------------------- | ------------- |
| `/api/agents`                | POST   | `agent.create`                           | -             |
| `/api/agents`                | GET    | - (only one's own + authorized)          | -             |
| `/api/agents/{id}`           | GET    | -                                        | agent.view    |
| `/api/agents/{id}`           | DELETE | `agent.delete_own` or `agent.delete_any` | agent         |
| `/api/agents/{id}/stop`      | POST   | `agent.stop_own` or `agent.stop_any`     | agent         |
| `/api/agents/{id}/regenerate`| POST   | `agent.regenerate_own` or `agent.regenerate_any` | agent   |
| `/api/terminals`             | POST   | `terminal.open`                          | -             |
| `/api/terminals`             | GET    | `terminal.list`                          | -             |
| `/api/terminals/{id}`        | DELETE | `terminal.delete_own` or `terminal.delete_any` | -        |
| `/api/file-content`          | GET    | `file.read`                              | -             |
| `/api/file-write`            | POST   | `file.write`                             | -             |
| `/api/directories`           | GET    | `file.browse`                            | -             |
| `/api/node/status`           | GET    | `node.view`                              | -             |
| `/api/node/secret`           | GET    | `node.secret`                            | -             |
| `/api/node/restart`          | POST   | `node.restart`                           | -             |
| `/api/node/code-update`      | POST   | `node.code_update`                       | -             |
| `/api/timers`                | POST   | `timer.create`                           | -             |
| `/api/timers`                | GET    | `timer.list`                             | -             |
| `/api/timers/{id}`           | DELETE | `timer.delete_own` or `timer.delete_any` | -             |
| `/api/chat/register`         | POST   | `chat.join`                              | -             |
| `/api/chat/create_room`      | POST   | `chat.create_room`                       | -             |
| `/api/chat/delete_room`      | POST   | `chat.delete_own_room`                   | -             |
| `/api/chat/message`          | POST   | `chat.send_message`                      | -             |
| `/api/chat/private_message`  | POST   | `chat.private_message`                   | -             |
| `/api/groups`                | POST   | `group.create`                           | -             |
| `/api/groups/{id}/join`      | POST   | `group.join`                             | -             |
| `/api/data/read`             | POST   | `data.read`                              | -             |
| `/api/data/write`            | POST   | `data.write`                             | -             |
| `/api/data/delete`           | POST   | `data.delete`                            | -             |
| `/api/admin/users`           | \*     | `user.manage`                            | -             |
| `/api/admin/groups`          | \*     | `group.manage`                           | -             |
| `/api/admin/permissions`     | \*     | `permission.manage`                      | -             |
| `/api/model-groups`          | GET    | `model.view`                             | -             |
| `/api/completions`           | POST   | `completion.use`                         | -             |
| `/api/search`                | POST   | `search.use`                             | -             |

### 6.4 _own vs. _any Determination Logic

For `xxx_own` / `xxx_any` permissions, the check flow:

```text
1. User has xxx_any permission? -> allowed to operate on any resource
2. User has xxx_own permission? -> check whether the resource was created by the user
   - yes -> allowed
   - no -> deny (403)
3. Neither -> deny (403)
```

A `created_by` field must be added to the data model to identify the resource creator:

- Agent: `create_agent` in `agent_manager.py` must record `owner_id`
- Terminal: must record `owner_id`

---

## 7. Data Storage Design

### 7.1 Storage Approach

Uses JSON file storage (consistent with the existing `auth_store`), located in the `haijunbot_data_dir/auth/` directory:

```text
haijunbot_data_dir/auth/
├── users.json              # user data
├── groups.json             # permission group data
├── group_permissions.json  # group permission configuration
├── user_groups.json        # user-group associations
├── user_permissions.json   # user-level permission overrides
├── resource_acl.json       # resource-level ACL
└── tokens_blacklist.json   # Token blacklist (logout / revocation)
```

### 7.2 Data Structures

**users.json**:

```json
{
  "users": {
    "uuid-1": {
      "user_id": "uuid-1",
      "username": "admin",
      "password_hash": "$2b$12$...",
      "display_name": "Administrator",
      "is_admin": true,
      "status": "active",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z",
      "last_login_at": "2025-01-01T00:00:00Z",
      "locked_reason": null,
      "login_fail_count": 0
    }
  }
}
```

**groups.json**:

```json
{
  "groups": {
    "sys-admin": {
      "group_id": "sys-admin",
      "group_name": "administrators",
      "description": "Super administrator",
      "is_system": true,
      "created_at": "2025-01-01T00:00:00Z"
    }
  }
}
```

**group_permissions.json**:

```json
{
  "sys-admin": {
    "*": "allow"
  },
  "sys-developer": {
    "agent.create": "allow",
    "agent.list_all": "deny",
    "terminal.open": "allow"
  }
}
```

**user_groups.json**:

```json
{
  "uuid-2": ["sys-developer"],
  "uuid-3": ["sys-viewer", "sys-chat"]
}
```

**user_permissions.json** (user-level overrides; take precedence over group permissions):

```json
{
  "uuid-2": {
    "node.view": "deny"
  }
}
```

**resource_acl.json**:

```json
{
  "agent": {
    "agent-uuid-1": {
      "owner_id": "uuid-2",
      "acl": {
        "uuid-3": {
          "agent.view": true,
          "agent.chat": true,
          "agent.edit_config": false
        }
      }
    }
  }
}
```

### 7.3 In-memory Cache

Load all permission data into memory at startup; write back to the files synchronously on any change:

```python
class PermissionManager:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._users = {}           # user_id -> User
        self._groups = {}          # group_id -> Group
        self._group_perms = {}     # group_id -> {perm: allow/deny}
        self._user_groups = {}     # user_id -> [group_id]
        self._user_perms = {}      # user_id -> {perm: allow/deny}
        self._resource_acl = {}    # resource_type -> {resource_id -> {user_id -> {perm: bool}}}
        self._user_cache = {}      # user_id -> computed effective permissions (lazy)
        self._load_all()

    def check_permission(self, user_id: str, permission: str) -> bool:
        """Checks a user's global permission"""
        # 1. User-level explicit deny
        user_overrides = self._user_perms.get(user_id, {})
        if user_overrides.get(permission) == "deny":
            return False

        # 2. User-level explicit allow
        if user_overrides.get(permission) == "allow":
            return True

        # 3. Group inheritance
        for group_id in self._user_groups.get(user_id, []):
            group_perms = self._group_perms.get(group_id, {})
            if group_perms.get(permission) == "allow":
                return True

        # 4. Default deny
        return False

    def check_resource_permission(
        self, user_id: str, resource_type: str,
        resource_id: str, permission: str
    ) -> bool:
        """Checks a resource-level permission"""
        resource = self._resource_acl.get(resource_type, {}).get(resource_id)
        if not resource:
            return False

        # Creator is automatically fully allowed
        if resource.get("owner_id") == user_id:
            return True

        # Check the ACL
        user_acl = resource.get("acl", {}).get(user_id, {})
        return user_acl.get(permission, False)

    def invalidate_cache(self, user_id: str = None):
        """Clears the cache when permissions change"""
        if user_id:
            self._user_cache.pop(user_id, None)
        else:
            self._user_cache.clear()
```

---

## 8. Deployment and Initialization

### 8.1 First Startup

1. On first system startup, automatically create the `admin` user; the password is read from `HAIJUNBOT_ADMIN_PASSWORD`; if not set, a random one is generated and output to the log
2. Password change is enforced after the first login
3. All requests must carry a valid JWT Token

### 8.2 Agent Ownership

- `owner_id` for existing Agents defaults to `admin`
- Admins can manually assign Agents to other users

### 8.3 Frontend Adaptation

**ConnectModal.vue changes**:

- Add a `username` input (already present, keep it)
- The `password` input is changed to the user password (not the global password)
- Login request changes to `{username, password}`
- Store the returned JWT Token

**App.vue changes**:

- `authStore` changes to store `{token, user_id, username, is_admin}`
- All API requests carry the JWT Token

---

## 9. Security Considerations

### 9.1 Password Security

- Passwords are stored using bcrypt hashes (cost factor=12)
- Password policy: at least 8 characters; it is recommended to include upper/lowercase + digits + special characters
- Lock the account for 30 minutes after 5 consecutive login failures
- Admins can manually lock/unlock accounts

### 9.2 Token Security

- The JWT signing key is read from the `HAIJUNBOT_JWT_SECRET` environment variable; if not set, a random one is generated (invalid after restart)
- Tokens never expire by default (no `exp` written, convenient for long-lived backend connections); to set a validity period, configure `HAIJUNBOT_JWT_EXPIRE_HOURS` > 0
- Token blacklist supported (entries added on logout)
- Expired entries are periodically cleaned from the blacklist

### 9.3 Privilege Escalation Protection

- Users cannot modify their own group membership, permissions, or is_admin status
- Admins cannot delete themselves or the last admin account
- Permission changes take effect immediately (cache cleared)
- All permission-change operations are recorded in the audit log

### 9.4 API Security

- All `/api/admin/*` endpoints require `user.manage` / `group.manage` / `permission.manage` permissions
- Sensitive operations (delete user, reset password, modify permissions) require secondary confirmation
- When the API returns 403, it includes the permission identifier so the frontend can show a precise prompt

---

## 10. Implementation Plan

### 10.1 Implementation Phases

| Phase | Content                        | Involved files                                        | Estimated effort |
| ----- | ------------------------------ | ------------------------------------------------------ | ---------------- |
| P1    | user management module         | add `user_manager.py`; modify `app.py`, `gateway.py`   | 3 days           |
| P2    | JWT authentication rework      | modify `gateway.py`, `app.py`; add `jwt_utils.py`      | 2 days           |
| P3    | permission groups & management | add `permission_manager.py`; modify `app.py`           | 3 days           |
| P4    | resource-level permissions (Agent ACL) | modify `agent_manager.py`, `app.py`              | 2 days           |
| P5    | API permission interception    | modify all routes in `app.py`; add permission checks   | 3 days           |
| P6    | frontend adaptation            | modify `ConnectModal.vue`, `App.vue`                   | 2 days           |
| P7    | testing & documentation        | unit tests, integration tests, user docs               | 2 days           |

#### Total: approximately 17 working days

### 10.2 New File List

| File                                            | Description                                   |
| ----------------------------------------------- | --------------------------------------------- |
| `haijunbot_web_gateway/user_manager.py`            | user manager (CRUD, password verification)    |
| `haijunbot_web_gateway/permission_manager.py`      | permission manager (checks, caching)          |
| `haijunbot_web_gateway/jwt_utils.py`               | JWT utilities (issuance, verification, blacklist) |
| `haijunbot_data_dir/auth/users.json`               | user data storage                            |
| `haijunbot_data_dir/auth/groups.json`              | permission group data storage                |
| `haijunbot_data_dir/auth/group_permissions.json`   | group permission configuration               |
| `haijunbot_data_dir/auth/user_groups.json`         | user-group associations                      |
| `haijunbot_data_dir/auth/user_permissions.json`    | user-level permission overrides              |
| `haijunbot_data_dir/auth/resource_acl.json`        | resource-level ACL                           |
| `haijunbot_data_dir/auth/tokens_blacklist.json`    | Token blacklist                              |

### 10.3 Modified File List

| File                                                         | Modifications                                            |
| ------------------------------------------------------------ | -------------------------------------------------------- |
| `haijunbot_web_gateway/app.py`                                  | add permission checks to all routes; add admin APIs      |
| `haijunbot_gateway/gateway.py`                                  | change `_check_auth` to `_check_auth_and_permission`     |
| `haijunbot_web_gateway/agent_manager.py`                        | add an `owner_id` field to `create_agent`                |
| `haijunbot_web_gateway/chat_manager.py`                         | change `created_by` to `owner_id`                        |
| `haijunbot_service/frontend/src/App.vue`                        | permission state management, feature-entry control       |
| `haijunbot_service/frontend/src/components/ConnectModal.vue`    | change the login form to username+password               |

---

## 11. Environment Variables

| Variable                     | Description                                    | Default value     |
| ---------------------------- | ---------------------------------------------- | ----------------- |
| `HAIJUNBOT_ADMIN_PASSWORD`      | initial admin password (on first startup)      | randomly generated |
| `HAIJUNBOT_JWT_SECRET`          | JWT signing key                                | randomly generated (invalid after restart) |
| `HAIJUNBOT_JWT_EXPIRE_HOURS`    | JWT validity (hours), 0=never expires          | 0                 |
| `HAIJUNBOT_LOCK_FAIL_COUNT`     | login failure lock threshold                   | 5                 |
| `HAIJUNBOT_LOCK_DURATION_MINUTES`| lock duration (minutes)                        | 30                |

---

## 12. Summary

This plan designs a complete multi-user authentication and group permission management system for the HaijunBot Web Gateway:

1. **Independent user system**: a separate account/password per user; JWT Token authentication; admin management supported
2. **Group permissions**: 5 built-in groups (admin/operator/developer/viewer/chat-user) + custom groups
3. **Fine-grained permissions**: 42 global permissions + 8 Agent resource-level permissions, covering all APIs
4. **Permission priority**: admin bypass -> user-level deny -> user-level allow -> group inheritance -> resource ACL -> default deny
5. **Security hardening**: bcrypt passwords, JWT signing, failure locking, privilege escalation protection
   Permission granularity is refined down to the Agent level, supporting control over 8 operations per individual Agent (view/chat/config/stop/delete/log/session, etc.), meeting the permission-isolation requirements of multi-user collaboration scenarios.