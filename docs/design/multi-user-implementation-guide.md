# HaijunBot Multi-user Authentication System Implementation Guide

> This document is an Agent coding guide describing how to migrate the current single-Token authentication system to a multi-user JWT authentication system.
> Use together with the design doc `docs/design/multi-user-auth-permission.md`.

## 1. Current System Authentication Architecture

### 1.1 Authentication flow (current state)

```text
User enters password -> POST /api/auth/login {password} -> verify HAIJUNBOT_GATEWAY_PASSWORD
-> return globally unique Token (UUID) -> frontend stores in localStorage(haijunbot_auth_token)
-> subsequent requests use Bearer Token -> validate_gateway_token() compares against the env var
```

### 1.2 Key files and line numbers

| File                | Key location                   | Description                               |
| ------------------- | ------------------------------ | ----------------------------------------- |
| `token_manager.py`  | entire file, 65 lines          | Token generation/verification; UUID stored in env var |
| `gateway.py`        | L63-90 `_check_auth`           | WebSocket authentication entry            |
| `gateway.py`        | L92-129 `_check_auth_fallback` | CLI password fallback authentication      |
| `app.py`            | L1495-1547 `verify_token`      | HTTP API Token verification dependency    |
| `app.py`            | L1559-1630 `login`             | login route; verifies password, returns Token |
| `app.py`            | L1339-1341                     | generates Token at startup, stores in env var |
| `app.py`            | L1640-1660                     | WebSocket routes, no Token verification   |
| `agent_manager.py`  | L125-142 `create_agent`        | no owner_id parameter                     |
| `chat_manager.py`   | L21-33 `__init__`              | clients/rooms have no user_id association |
| `App.vue`           | L1228-1254 `loginWithPassword` | frontend login logic                      |
| `App.vue`           | L1274-1287                     | Token loading/storage                     |
| `ConnectModal.vue`  | L14, L33                       | password input                            |

### 1.3 Core problems

1. **No user concept**: one globally shared Token; user identities cannot be distinguished
2. **Token never expires**: the UUID Token is valid forever and only invalidated on restart
3. **No permission control**: possessing the Token grants all permissions
4. **Resources have no ownership**: Agent/Terminal/Timer have no owner_id, so `_own` permission checks cannot be performed

---

## 2. Implementation Order and Dependencies

```text
P1: jwt_utils.py (no dependencies)
  ↓
P2: user_manager.py (depends on jwt_utils)
  ↓
P3: permission_manager.py (depends on user_manager)
  ↓
P4: modify gateway.py + token_manager.py (depends on jwt_utils)
  ↓
P5: modify app.py authentication + routes (depends on all of P1-P4)
  ↓
P6: modify agent_manager.py + chat_manager.py (depends on P5)
  ↓
P7: modify frontend App.vue + ConnectModal.vue (depends on P5)
```

---

## 3. New Files Detailed Design

### 3.1 `src/haijunbot/haijunbot_web_gateway/jwt_utils.py`

**Responsibility**: JWT Token issuance, verification, blacklist management

**Functions to implement**:

1. `generate_jwt_token(user_id: str, username: str, is_admin: bool) -> str`
   - Use the `HAIJUNBOT_JWT_SECRET` environment variable as the signing key
   - If unset, generate a random one (stored in memory, invalid after restart)
   - payload contains: `user_id`, `username`, `is_admin`, `iat`, `jti` (no `exp` by default, i.e. never expires)
   - Validity is read from `HAIJUNBOT_JWT_EXPIRE_HOURS`, default 0 (never expires); `exp` is written only when set to > 0

2. `validate_jwt_token(token: str) -> Optional[dict]`
   - Verify the signature and validity
   - Check whether the Token is on the blacklist
   - Return the payload dict or None

3. `revoke_token(token: str) -> None`
   - Add the Token's jti to the blacklist
   - The blacklist is stored in an in-memory dict; expired entries are cleaned periodically

4. `cleanup_revoked_tokens() -> None`
   - Clean up expired entries from the blacklist

**Dependency**: `PyJWT` library (must be added to requirements)

**Environment variables**:

- `HAIJUNBOT_JWT_SECRET`: signing key
- `HAIJUNBOT_JWT_EXPIRE_HOURS`: validity period (default 0, i.e. never expires)

---

### 3.2 `src/haijunbot/haijunbot_web_gateway/user_manager.py`

**Responsibility**: user CRUD, password verification, user status management

**Class to implement `UserManager`**:

1. `__init__(self, data_dir: str)`
   - Initialize the data directory `haijunbot_data_dir/auth/`
   - Load `users.json` into memory
   - If no data file exists, create the initial admin user

2. `create_user(self, username: str, password: str, display_name: str = None, is_admin: bool = False) -> dict`
   - Validate username uniqueness (3-32 characters, only letters/digits/underscore)
   - bcrypt-hash the password (cost=12)
   - Return user info (without password_hash)

3. `authenticate(self, username: str, password: str) -> Optional[dict]`
   - Look up the user, verify the bcrypt password
   - Check the user status (active/locked)
   - On success: reset login_fail_count, update last_login_at
   - On failure: increment login_fail_count; lock after reaching 5
   - Return user info or None

4. `get_user(self, user_id: str) -> Optional[dict]`
   - Return user info (without password_hash)

5. `update_user(self, user_id: str, **kwargs) -> Optional[dict]`
   - Modifiable fields: display_name, status, is_admin

6. `reset_password(self, user_id: str, new_password: str) -> bool`
   - Admin resets a password

7. `change_password(self, user_id: str, old_password: str, new_password: str) -> bool`
   - Self-service password change; requires verifying the old password

8. `delete_user(self, user_id: str) -> bool`
   - Cannot delete self; cannot delete the last admin

9. `list_users(self, search: str = None, offset: int = 0, limit: int = 50) -> list`
   - Supports search and pagination

10. `_ensure_admin_user(self) -> None`
    - Creates the admin user on first startup
    - Password read from `HAIJUNBOT_ADMIN_PASSWORD`; if unset, a random one is generated and output to the log

**Data storage**: `haijunbot_data_dir/auth/users.json`

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
      "last_login_at": null,
      "locked_reason": null,
      "login_fail_count": 0
    }
  }
}
```

**Dependency**: `bcrypt` library (must be added to requirements)

**Environment variables**:

- `HAIJUNBOT_ADMIN_PASSWORD`: initial admin password (randomly generated if unset)

---

### 3.3 `src/haijunbot/haijunbot_web_gateway/permission_manager.py`

**Responsibility**: permission group management, permission checks, resource-level ACL

**Class to implement `PermissionManager`**:

1. `__init__(self, data_dir: str)`
   - Load 5 JSON files: groups.json, group_permissions.json, user_groups.json, user_permissions.json, resource_acl.json
   - Initialize the 5 built-in groups (sys-admin, sys-operator, sys-developer, sys-viewer, sys-chat)
   - Permission cache: `_permission_cache: dict`, invalidated when a user's permissions change

2. `check_permission(self, user_id: str, permission: str) -> bool`
   - Evaluation priority: user-level explicit deny -> user-level explicit allow -> group inheritance allow -> default deny
   - Check the cache first; on a miss, compute and cache

3. `check_resource_permission(self, user_id: str, resource_type: str, resource_id: str, permission: str) -> bool`
   - Creator is automatically fully allowed -> check resource_acl.json

4. `get_user_permissions(self, user_id: str) -> dict`
   - Return the user's effective permissions (group inheritance + user overrides)

5. Group management methods:
   - `create_group(self, name, display_name, description) -> dict`
   - `update_group(self, group_id, **kwargs) -> dict`
   - `delete_group(self, group_id) -> bool` (built-in groups cannot be deleted)
   - `get_group(self, group_id) -> dict`
   - `list_groups(self) -> list`

6. Group permission methods:
   - `get_group_permissions(self, group_id) -> dict`
   - `set_group_permissions(self, group_id, permissions: dict) -> dict`

7. User group methods:
   - `get_user_groups(self, user_id) -> list`
   - `set_user_groups(self, user_id, group_ids: list) -> list`

8. User permission overrides:
   - `get_user_overrides(self, user_id) -> dict`
   - `set_user_overrides(self, user_id, overrides: dict) -> dict`

9. Resource ACL methods:
   - `set_resource_acl(self, resource_type, resource_id, acl: dict) -> dict`
   - `get_resource_acl(self, resource_type, resource_id) -> dict`
   - `delete_resource_acl(self, resource_type, resource_id) -> bool`

10. `invalidate_cache(self, user_id: str = None)`
    - Clears the full cache when user_id=None
    - Clears only that user's cache when a user_id is specified

**Data storage**: 5 JSON files under `haijunbot_data_dir/auth/`

**Built-in group permission mapping** (see Chapter 5 of the design doc):

| Built-in group | Permission scope                                      |
| -------------- | ------------------------------------------------------ |
| sys-admin      | all permissions (_:_)                                  |
| sys-operator   | agent:_, terminal:_, timer:_, chat:_                   |
| sys-developer  | agent:create, agent:read, agent:execute, terminal:_, chat:_ |
| sys-viewer     | agent:read, terminal:read, chat:*                      |
| sys-chat       | chat:*                                                 |

**Permission format**: `resource:action`, e.g. `agent:create`, `terminal:write`, `admin:users`

**Permission override format**:

```json
{
  "user_id_1": {
    "agent:delete": "deny",
    "admin:users": "allow"
  }
}
```

---

## 4. Existing Files Modification Guide

### 4.1 `src/haijunbot/haijunbot_web_gateway/token_manager.py`

**Modification goal**: keep the old function signatures for compatibility; add a JWT verification entry

**Modification points**:

1. **L1-5 imports**: add `from .jwt_utils import validate_jwt_token, generate_jwt_token`

2. **L26-44 `validate_gateway_token`**: modify to try JWT verification first

   ```python
   # Original logic: compare against the env var HAIJUNBOT_AUTH_TOKEN
   # New logic: try JWT verification first, then fall back to the env var comparison
   def validate_gateway_token(token: str) -> Optional[dict]:
       # JWT verification first
       payload = validate_jwt_token(token)
       if payload:
           return payload
       # Fallback: env var comparison (for the CLI Gateway)
       env_token = os.environ.get('HAIJUNBOT_AUTH_TOKEN')
       if env_token and token == env_token:
           return {'user_id': 'system', 'username': 'gateway', 'is_admin': True}
       return None
   ```

3. **L15-23 `generate_gateway_token`**: keep unchanged (the CLI Gateway still needs the UUID Token)

4. **New function `validate_token_with_user`**:

   ```python
   def validate_token_with_user(token: str) -> Optional[dict]:
       """Verify the Token and return user info; used for HTTP API authentication"""
       payload = validate_jwt_token(token)
       if payload:
           return payload
       # Fallback to the old Token
       env_token = os.environ.get('HAIJUNBOT_AUTH_TOKEN')
       if env_token and token == env_token:
           return {'user_id': 'system', 'username': 'gateway', 'is_admin': True}
       return None
   ```

---

### 4.2 `src/haijunbot/haijunbot_gateway/gateway.py`

**Modification goal**: switch WebSocket authentication to JWT

**Modification points**:

1. **L1-10 imports**: add `from haijunbot_web_gateway.jwt_utils import validate_jwt_token`

2. **L63-90 `_check_auth`**: modify the Token verification logic

   ```python
   # Original logic: call validate_gateway_token to compare against the env var
   # New logic: call validate_jwt_token to verify the JWT
   async def _check_auth(self, websocket, client_id):
       token = websocket.query_params.get('token')
       if not token:
           # Try getting it from the headers
           token = websocket.headers.get('X-HaijunBot-Token')
       if not token:
           return False
       payload = validate_jwt_token(token)
       if payload:
           self._client_users[client_id] = payload  # store user info
           return True
       # Fallback to the old Token
       env_token = os.environ.get('HAIJUNBOT_AUTH_TOKEN')
       if env_token and token == env_token:
           self._client_users[client_id] = {'user_id': 'system', 'username': 'gateway', 'is_admin': True}
           return True
       return False
   ```

3. **Add the instance variable `self._client_users: dict`**: initialize it in `__init__`; stores the client_id -> user_info mapping

4. **Add method `get_client_user(self, client_id) -> Optional[dict]`**: get the user info of a WebSocket connection

#### 4.3.5 WebSocket authentication changes

1. **L1640-1660 WebSocket routes**: add Token verification
   - Extract the token from query_params and verify the JWT
   - Close the connection on verification failure (code=4001)
   - Store user_info in websocket.state.user
   - Apply the same changes to all 5 WebSocket endpoints: `/ws`, `/ws/agent/{id}`, `/ws/terminal/{id}`, `/ws/chat`, `/ws/screenshot`

---

### 4.4 `src/haijunbot/haijunbot_web_gateway/agent_manager.py`

**Modification goal**: give Agent resources an owner_id

**Modification points**:

1. **L125-142 `create_agent`**: add an `owner_id` parameter

   ```python
   # Original signature: async def create_agent(self, agent_type, working_dir, ...)
   # New signature: async def create_agent(self, agent_type, working_dir, owner_id=None, ...)
   # In _agent_info, add: 'owner_id': owner_id
   ```

2. **New fields in the Agent info structure**:
   - `owner_id: str` - creator's user_id
   - `owner_name: str` - creator's username (redundant, for convenient frontend display)

3. **Add method `get_agents_by_owner(self, owner_id: str) -> list`**: get all Agents created by a given user

4. **`list_agents` method**: non-admin users can only see their own Agents (needs filtering at the app.py route layer)

---

### 4.5 `src/haijunbot/haijunbot_web_gateway/chat_manager.py`

**Modification goal**: associate chat rooms with user_id

**Modification points**:

1. **L39-46 `register_client`**: add `user_id`, `username` parameters

   ```python
   # Original signature: def register_client(self, client_id, client_name)
   # New signature: def register_client(self, client_id, client_name, user_id=None, username=None)
   # In the _clients structure, add: 'user_id': user_id, 'username': username
   ```

2. **`_chat_rooms` in `__init__` (L21-33)**: add an `owner_id` field to the room structure
   - Add an `owner_id` parameter to the `create_room` method
   - Verify owner_id in the `delete_room` method (only the creator can delete)

3. **`join_room` / `leave_room`**: record user_id rather than only client_name

4. **Broadcast events gain a user_id field**:
   - `chat_message`: add a `user_id` field
   - `chat_client_joined` / `chat_client_left`: add a `user_id` field

---

## 5. Frontend Modification Guide

### 5.1 `src/haijunbot/haijunbot_service/frontend/src/App.vue`

**Modification goal**: change login to username+password; change the Token to JWT; add user-info management

**Modification points**:

1. **L1190 `auth` reactive object**: add a username field

   ```javascript
   // Original: auth: reactive({ password: '' })
   // New: auth: reactive({ username: '', password: '' })
   ```

2. **L1228-1254 `loginWithPassword`**: change to send username+password; store the JWT and user info

   ```javascript
   async function loginWithPassword(username, password) {
     const response = await fetch(
       `${getHttpProtocol()}://${host}:${port}/api/auth/login`,
       {
         method: "POST",
         headers: { "Content-Type": "application/json" },
         body: JSON.stringify({ username, password }),
       },
     );
     const result = await response.json();
     if (result.token) {
       localStorage.setItem("haijunbot_auth_token", result.token);
       localStorage.setItem("haijunbot_user_info", JSON.stringify(result.user));
       // ... existing logic
     }
   }
   ```

3. **L1274-1287 Token loading**: also load the user info

   ```javascript
   const savedToken = localStorage.getItem("haijunbot_auth_token");
   const savedUserInfo = localStorage.getItem("haijunbot_user_info");
   if (savedToken && savedUserInfo) {
     userInfo.value = JSON.parse(savedUserInfo);
   }
   ```

4. **Add reactive variables**:
   - `userInfo: ref(null)` - current logged-in user info
   - `isAdmin: computed(() => userInfo.value?.is_admin ?? false)`

5. **WebSocket connection**: add the token parameter to the URL

   ```javascript
   // Original: ws://host:port/ws
   // New: ws://host:port/ws?token=jwt_token
   ```

6. **401 handling (L1316)**: clear the token and user info; show the login dialog

   ```javascript
   localStorage.removeItem("haijunbot_auth_token");
   localStorage.removeItem("haijunbot_user_info");
   userInfo.value = null;
   ```

7. **New API calls**:
   - `GET /api/auth/me` - get the current user info (verifies Token validity on page refresh)
   - `POST /api/auth/logout` - logout
   - `POST /api/auth/change-password` - change password

---

### 5.2 `src/haijunbot/haijunbot_service/frontend/src/components/ConnectModal.vue`

**Modification goal**: change the login dialog to username+password

**Modification points**:

1. **L14 password input**: add a username input

   ```html
   <!-- New -->
   <div class="form-group">
     <label>Username</label>
     <input v-model="username" type="text" placeholder="Enter username" />
   </div>
   <!-- Keep the existing password field -->
   <div class="form-group">
     <label>Password</label>
     <input v-model="password" type="password" placeholder="Enter password" />
   </div>
   ```

2. **Add props/emits**:
   - prop: `username` (two-way binding)
   - emit: `update:username`

3. **Login button logic**: pass username and password together on emit

---

### 5.3 Frontend User Management UI (new)

**Modification goal**: provide admins with a user/permission management interface

**New components**:

1. **`src/haijunbot/haijunbot_service/frontend/src/components/UserManagement.vue`**
   - User list (table: username / display name / status / group / actions)
   - Create-user dialog (username + password + display_name + is_admin)
   - Edit-user dialog (display_name + status + group assignment)
   - Reset-password dialog
   - Delete confirmation
   - Visible only when `is_admin=true` or with the `admin:users` permission

2. **`src/haijunbot/haijunbot_service/frontend/src/components/PermissionManagement.vue`**
   - Permission group list (table: group name / display name / member count / actions)
   - Group permission editing (checkbox matrix: resource x action)
   - Group member management (add/remove users)
   - Visible only when `is_admin=true` or with the `admin:permissions` permission

3. **App.vue integration**:
   - Add a top-nav user menu (avatar / username dropdown)
   - Dropdown items: user info, change password, user management (admin), permission management (admin), logout
   - Add routes/Tabs: user management, permission management
   - The `userInfo` ref drives UI permission control (v-if="isAdmin")

4. **Change-password dialog**:
   - Available to all users
   - Old password + new password + confirm password
   - Calls `POST /api/auth/change-password`

---

1. **WebSocket connection**: add the token parameter to the URL

   ```typescript
   // Original: ws://host:port/ws
   // New: ws://host:port/ws?token=jwt_token
   ```

2. **Add user info storage**:
   - `panelState` adds `userInfo: { user_id, username, display_name, is_admin } | null`
   - Store userInfo after a successful login
   - Clear the token and userInfo on a 401 response

3. **Additions to the settings panel** (L913-974 settingsPanelMarkup):
   - Show the currently logged-in username
   - Change-password button
   - Logout button

---

## 6. Dependencies and Deployment

### 6.1 New Python Dependencies

Add to `requirements.txt` or `pyproject.toml`:

```text
PyJWT>=2.8.0
bcrypt>=4.0.0
```

### 6.2 Environment Variables

| Variable                | Required | Default       | Description                                    |
| ----------------------- | -------- | ------------- | ---------------------------------------------- |
| `HAIJUNBOT_JWT_SECRET`     | No       | random        | JWT signing key; must be set in production     |
| `HAIJUNBOT_JWT_EXPIRE_HOURS` | No     | 0             | JWT validity (hours), 0=never expires          |
| `HAIJUNBOT_ADMIN_PASSWORD` | No       | random        | initial admin password; output to the log on first startup |

### 6.3 Data Directory

On first startup, automatically create the `haijunbot_data_dir/auth/` directory and the following files:

```text
auth/
  users.json          # user data
  groups.json         # permission group definitions
  group_permissions.json  # group permission mappings
  user_groups.json    # user-group relationships
  user_permissions.json   # user permission overrides
  resource_acl.json   # resource-level ACL
```

### 6.4 First Startup Flow

1. Check whether `auth/users.json` exists
2. If it does not exist, create the directory and initial files
3. Create the admin user (password from the env var or randomly generated)
4. Create the 5 built-in permission groups
5. Add the admin user to the sys-admin group
6. Output the admin password to the log (first time only)

---

## 7. Verification Checklist

### 7.1 Backend Verification

- [ ] `POST /api/auth/login` logs in with username+password and returns a JWT
- [ ] `GET /api/auth/me` gets the current user info with the JWT
- [ ] `POST /api/auth/logout` invalidates the Token after logout
- [ ] `POST /api/users` creates a user (admin permission required)
- [ ] Non-admin access to admin endpoints returns 403
- [ ] Requests return 401 after the JWT expires
- [ ] WebSocket connections authenticate with the token parameter
- [ ] WebSocket connections without a token or with an invalid token are rejected
- [ ] Agent creation records owner_id
- [ ] A non-owner user deleting an Agent returns 403 (when no `agent:delete` permission)

### 7.2 Frontend Verification

- [ ] The login dialog shows username+password inputs
- [ ] The username is displayed after a successful login
- [ ] Expired Tokens automatically redirect to the login dialog
- [ ] WebSocket connections work normally (with the token parameter)
- [ ] Chat room functionality works (with user_id association)
- [ ] The login state is restored after a page refresh (when the JWT has not expired)

### 7.3 Permission Verification

- [ ] sys-admin group users can perform all operations
- [ ] sys-viewer group users can only view; cannot create/delete
- [ ] sys-chat group users can only use chat functionality
- [ ] User-level deny overrides group-level allow
- [ ] Resource owners can manage their own resources