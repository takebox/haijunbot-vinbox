# HaijunBot Architecture Refactoring Plan

> Version: 1.0
> Date: 2026-08-16
> Status: Design draft

---

## 1. Project Overview

**Project name**: HaijunBot AI Assistant
**Current version**: 3.1.14
**Tech stack**: Python 3.12 + FastAPI + Vue 3 + TypeScript
**Code size**: approximately 155,000 lines of Python, 24 modules, 92 test files

---

## 2. Current State Analysis

### 2.1 Module List and Code Volume

| Module                  | Files | LOC    | Responsibility            |
| ----------------------- | ----- | ------ | ------------------------- |
| haijunbot_agent            | 51    | 19,131 | Main Agent core logic     |
| haijunbot_c2rust           | 52    | 18,658 | C→Rust migration pipeline |
| haijunbot_code_agent       | 59    | 16,868 | Code Agent                |
| haijunbot_tools            | 27    | 15,652 | Tool set                  |
| haijunbot_utils            | 23    | 15,292 | General utility library   |
| haijunbot_web_gateway      | 21    | 14,313 | Web gateway               |
| haijunbot_sec              | 23    | 27,734 | Security scanning         |
| haijunbot_lsp              | 8     | 6,302  | LSP language service      |
| haijunbot_browser          | 2     | 3,855  | Browser automation        |
| haijunbot_platform         | 7     | 2,515  | AI platform adaptation    |
| haijunbot_service          | 7     | 2,445  | Web service entry         |
| haijunbot_config           | 4     | 2,444  | Configuration management  |
| haijunbot_platform_manager | 3     | 2,032  | Platform manager          |
| haijunbot_windows          | 2     | 1,683  | Windows support           |
| haijunbot_mcp              | 4     | 1,477  | MCP protocol integration  |
| haijunbot_memory_organizer | 3     | 1,457  | Memory organizer          |
| haijunbot_gateway          | 7     | 886    | CLI gateway bridge        |
| haijunbot_jck              | 4     | 754    | JCK tool                  |
| haijunbot_git_utils        | 1     | 576    | Git commit tool           |
| haijunbot_methodology      | 1     | 481    | Methodology management    |
| haijunbot_smart_shell      | 2     | 458    | Smart Shell               |
| haijunbot_rules_index      | 3     | 255    | Rule index                |
| haijunbot_git_squash       | 2     | 76     | Git squash                |
| haijunbot_data             | 0     | 0      | Data files (empty)        |

### 2.2 Core Problem Identification

#### Problem 1: Severe circular dependencies

The following modules have bidirectional dependencies, violating the dependency inversion principle:

```text
haijunbot_agent ←→ haijunbot_tools
haijunbot_agent ←→ haijunbot_code_agent
haijunbot_utils ←→ haijunbot_platform
haijunbot_web_gateway → haijunbot_service (reverse dependency)
```

**Impact**:

- Modules cannot be tested independently
- Modifying one module may affect another
- Sensitive to import order, prone to runtime errors
- Hinders modular decomposition and independent deployment

#### Problem 2: Overly large files

| File                                | LOC    | Problem                                        |
| ----------------------------------- | ------ | ---------------------------------------------- |
| haijunbot_sec/checkers/c_checker.py    | 9,453  | A single file carries all of the C security-check logic |
| haijunbot_web_gateway/app.py           | 7,357  | All routes are concentrated in one file        |
| haijunbot_sec/checkers/rust_checker.py | 3,908  | A single file carries all of the Rust security-check logic |
| haijunbot_browser/eli.py               | 3,850  | ELI entry mixed with business logic            |
| haijunbot_agent/`__init__.py`          | 3,444  | The module init file carries too many responsibilities |

**Impact**:

- Poor code readability, hard to maintain
- Frequent merge conflicts
- Cannot develop in parallel
- Test coverage is hard

#### Problem 3: Unclear module responsibilities

- `haijunbot_agent/__init__.py` has 3444 lines, carrying multiple responsibilities including Agent class definition, event handling, and tool invocation
- The boundary between `haijunbot_service` and `haijunbot_web_gateway` is blurry; service only contains eli.py yet is reverse-depended on by web_gateway
- The `haijunbot_data` directory is empty but kept in the module list
- Frontend code is embedded in `haijunbot_service/frontend/`, mixed with backend Python code

#### Problem 4: Frontend-backend coupling

The frontend Vue 3 code is located in `src/haijunbot/haijunbot_service/frontend/`, under the same directory tree as the backend Python code, which leads to:

- The build system must handle both Python and Node.js
- Deployment must handle the frontend build artifacts separately
- Version management becomes messy

---

## 3. Target Architecture

### 3.1 Layered Architecture Design

```text
┌─────────────────────────────────────────────────┐
│                 Interface Layer                  │
│  CLI / Web UI / WebSocket / REST API / LSP      │
├─────────────────────────────────────────────────┤
│                 Application Layer                │
│  Agent Core / Code Agent / C2Rust / Security     │
├─────────────────────────────────────────────────┤
│                  Domain Layer                    │
│  Tool Set / Platform / MCP / Methodology / Memory │
├─────────────────────────────────────────────────┤
│               Infrastructure Layer               │
│  Config / Logs / Git / Utilities / Data Storage  │
└─────────────────────────────────────────────────┘
```

### 3.2 Dependency Rules

```text
Interface Layer → Application Layer → Domain Layer → Infrastructure Layer

No reverse dependencies allowed:
- The infrastructure layer must not depend on any module above it
- The domain layer must not depend on the application layer or interface layer
- The application layer must not depend on the interface layer
```

### 3.3 Target Module Division

#### Infrastructure Layer

| Module         | Responsibility                              | Source                                |
| -------------- | ------------------------------------------- | ------------------------------------- |
| haijunbot_core    | Config, logs, general utilities, global state | Merge haijunbot_utils + haijunbot_config   |
| haijunbot_git     | Git operation wrapper                       | Extracted from haijunbot_utils           |
| haijunbot_storage | File storage, session persistence, symbol cache | New                                |

#### Domain Layer

| Module               | Responsibility                            | Source                                  |
| -------------------- | ----------------------------------------- | --------------------------------------- |
| haijunbot_platform      | AI platform adaptation (OpenAI/Juglow) | Keep independent                        |
| haijunbot_tools         | Tool registration and dispatch            | Keep independent, remove the dependency on haijunbot_agent |
| haijunbot_mcp           | MCP protocol integration                  | Keep independent                        |
| haijunbot_methodology   | Methodology management                    | Keep independent                        |
| haijunbot_memory        | Memory management                         | Merge haijunbot_memory_organizer           |

#### Application Layer

| Module              | Responsibility   | Source                    |
| ------------------- | ---------------- | ------------------------- |
| haijunbot_agent        | Main Agent core  | Split `__init__.py`       |
| haijunbot_code_agent   | Code Agent       | Keep independent          |
| haijunbot_c2rust       | C→Rust migration | Keep independent          |
| haijunbot_sec          | Security scanning | Split the oversized checker files |
| haijunbot_lsp          | LSP language service | Keep independent       |
| haijunbot_browser      | Browser automation | Keep independent         |

#### Interface Layer

| Module            | Responsibility        | Source                                        |
| ----------------- | -------------------- | ---------------------------------------- |
| haijunbot_cli        | ELI entry            | Merge haijunbot_gateway + haijunbot_smart_shell |
| haijunbot_web        | Web gateway + service | Merge haijunbot_web_gateway + haijunbot_service |
| haijunbot_frontend   | Frontend Vue app     | Independent from haijunbot_service/frontend  |
| haijunbot_windows    | Windows support      | Keep independent                          |

---

## 4. Phased Implementation Plan

### Phase 1: Eliminate circular dependencies (priority: high)

**Goal**: break the circular dependencies between haijunbot_agent ↔ haijunbot_tools ↔ haijunbot_code_agent

**Specific steps**:

1. **Extract shared interfaces**: create `haijunbot_core/interfaces.py`, defining the abstract interface between Agents and tools
2. **Decouple haijunbot_tools**: remove the direct imports of haijunbot_agent in haijunbot_tools, using dependency injection or callbacks instead
3. **Decouple haijunbot_code_agent**: remove the direct imports of haijunbot_agent in haijunbot_code_agent
4. **Decouple haijunbot_utils**: remove the dependency on haijunbot_platform in haijunbot_utils, moving platform-related logic down

**Acceptance criteria**:

- `grep -rn "from haijunbot.haijunbot_agent" haijunbot_tools/` returns empty
- `grep -rn "from haijunbot.haijunbot_tools" haijunbot_agent/` keeps only lazy imports
- All tests pass

### Phase 2: Split oversized files (priority: high)

**Goal**: split files over 2000 lines into multiple modules

**Specific steps**:

1. **Split c_checker.py (9453 lines)**:
   - `c_checker/base.py`: base checker class
   - `c_checker/buffer_overflow.py`: buffer overflow checks
   - `c_checker/memory_safety.py`: memory safety checks
   - `c_checker/integer_overflow.py`: integer overflow checks
   - `c_checker/format_string.py`: format string checks
   - `c_checker/taint_analysis.py`: taint analysis
   - `c_checker/concurrency.py`: concurrency safety checks

2. **Split app.py (7357 lines)**:
   - `web/routes/agent_routes.py`: Agent management routes
   - `web/routes/node_routes.py`: node management routes
   - `web/routes/chat_routes.py`: chat room routes
   - `web/routes/auth_routes.py`: authentication routes
   - `web/routes/terminal_routes.py`: terminal routes
   - `web/websocket_manager.py`: WebSocket connection management
   - `web/middleware.py`: middleware

3. **Split rust_checker.py (3908 lines)**:
   - Split into multiple sub-modules by check type

4. **Split haijunbot_agent/`__init__.py` (3444 lines)**:
   - `agent/core.py`: Agent core class
   - `agent/events.py`: event definitions
   - `agent/tool_executor.py`: tool executor
   - `agent/session.py`: session management

**Acceptance criteria**:

- No file exceeds 1500 lines
- All tests pass after the split
- Import paths are updated correctly

### Phase 3: Module reorganization (priority: medium)

**Goal**: reorganize modules according to the layered architecture

**Specific steps**:

1. **Merge haijunbot_service into haijunbot_web_gateway**: eliminate the reverse dependency
2. **Independence for the frontend**: move `haijunbot_service/frontend/` to the project root `frontend/`
3. **Delete the empty module**: remove the empty haijunbot_data directory
4. **Merge small modules**:
   - haijunbot_git_squash → haijunbot_git_utils
   - haijunbot_methodology → haijunbot_utils
   - haijunbot_rules_index → haijunbot_agent

**Acceptance criteria**:

- Module dependency relationships conform to the layered architecture
- No reverse dependencies
- All CLI commands work correctly

### Phase 4: Strengthen test coverage (priority: medium)

**Goal**: add tests for the refactored core modules

**Specific steps**:

1. Add unit tests for haijunbot_tools
2. Add integration tests for haijunbot_web_gateway
3. Add security checker tests for haijunbot_sec
4. Establish a CI coverage threshold (core modules ≥ 80%)

**Acceptance criteria**:

- The test coverage report shows ≥ 80% coverage for core modules
- The CI pipeline includes a coverage check

### Phase 5: Documentation and conventions (priority: low)

**Goal**: establish architecture documentation and development conventions

**Specific steps**:

1. Document the inter-module dependency graph
2. Establish a code review checklist
3. Write a development guide for new modules
4. Establish an architecture decision record (ADR) mechanism

---

## 5. Risk Assessment and Mitigation

| Risk                                                    | Impact | Probability | Mitigation                             |
| ------------------------------------------------------- | ------ | ----------- | -------------------------------------- |
| Decoupling circular dependencies introduces runtime errors | High   | Medium      | Use lazy imports as a transition, replace gradually |
| Splitting large files causes import path errors         | High   | Medium      | Keep a compatibility layer for old paths, deprecate gradually |
| Module merging breaks CLI commands                      | Medium | Low         | Keep aliases for the old entry points  |
| Frontend independence changes the build process         | Medium | Low         | Migrate in phases, keep old paths      |
| Insufficient test coverage causes regressions           | High   | Medium      | Add tests before refactoring           |

---

## 6. Rollback Strategy

Each phase is committed independently, ensuring it can be rolled back separately:

```bash
# Roll back to before Phase 1
git revert <phase1-commit>

# Roll back to before Phase 2
git revert <phase2-commit>

# Full rollback to before the refactor
git reset --hard 5c366bc7d2423597fdc85c214a962260120179df
```

---

## 7. Appendix

### 7.1 Current Module Dependency Graph

```text
haijunbot_agent ←→ haijunbot_tools
haijunbot_agent ←→ haijunbot_code_agent
haijunbot_agent ←→ haijunbot_sec
haijunbot_agent ←→ haijunbot_c2rust
haijunbot_utils ←→ haijunbot_platform
haijunbot_web_gateway → haijunbot_service
haijunbot_web_gateway → haijunbot_gateway
haijunbot_tools → haijunbot_mcp
haijunbot_tools → haijunbot_code_agent
```

### 7.2 Target Module Dependency Graph

```text
Interface layer:
  haijunbot_cli → haijunbot_agent → haijunbot_tools → haijunbot_core
  haijunbot_web → haijunbot_agent → haijunbot_tools → haijunbot_core
  haijunbot_frontend → haijunbot_web (HTTP/WebSocket)

Application layer:
  haijunbot_agent → haijunbot_tools → haijunbot_core
  haijunbot_code_agent → haijunbot_tools → haijunbot_core
  haijunbot_c2rust → haijunbot_agent → haijunbot_tools → haijunbot_core
  haijunbot_sec → haijunbot_tools → haijunbot_core
  haijunbot_lsp → haijunbot_core
  haijunbot_browser → haijunbot_core

Domain layer:
  haijunbot_platform → haijunbot_core
  haijunbot_tools → haijunbot_core
  haijunbot_mcp → haijunbot_core
  haijunbot_methodology → haijunbot_core
  haijunbot_memory → haijunbot_core

Infrastructure layer:
  haijunbot_core (no dependencies)
  haijunbot_git → haijunbot_core
  haijunbot_storage → haijunbot_core
```

### 7.3 Key File Index

| File                                | Current LOC | Target LOC  | Split Plan                    |
| ----------------------------------- | ----------- | ----------- | ----------------------------- |
| haijunbot_sec/checkers/c_checker.py    | 9,453       | < 1,500 × 7 | Split by check type           |
| haijunbot_web_gateway/app.py           | 7,357       | < 1,500 × 5 | Split by route type           |
| haijunbot_sec/checkers/rust_checker.py | 3,908       | < 1,500 × 3 | Split by check type           |
| haijunbot_browser/eli.py               | 3,850       | < 1,500 × 3 | Separate ELI from business logic |
| haijunbot_agent/`__init__.py`          | 3,444       | < 1,500 × 3 | Split by responsibility       |
| haijunbot_tools/task_list_manager.py   | 2,671       | < 1,500 × 2 | Split by function             |
| haijunbot_utils/utils.py               | 2,389       | < 1,500 × 2 | Split by function             |
| haijunbot_tools/registry.py            | 2,311       | < 1,500 × 2 | Split by function             |
| haijunbot_tools/gateway_manager.py     | 2,300       | < 1,500 × 2 | Split by function             |
| haijunbot_web_gateway/node_manager.py  | 2,245       | < 1,500 × 2 | Split by function             |