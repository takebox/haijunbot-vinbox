# HaijunBot vs haijun-code Agent Implementation Comparison Analysis Report

## 1. Project Overview

### 1.1 Analysis Scope

**HaijunBot project**:
- Core files: `src/haijunbot/haijunbot_agent/haijunbot.py`, `src/haijunbot/haijunbot_agent/run_loop.py`, `src/haijunbot/haijunbot_agent/tool_executor.py`, `src/haijunbot/haijunbot_tools/registry.py`
- Tech stack: Python + Typer + Rich
- Architecture pattern: Modular monolithic application

**haijun-code project**:
- Core files: `src/Tool.ts`, `src/tools.ts`, `src/QueryEngine.ts`
- Tech stack: TypeScript + Bun + React/Ink
- Architecture pattern: Object-oriented + async generators

### 1.2 Code Sources

- HaijunBot analysis sources:
  - `/home/skyfire/code/HaijunBot/src/haijunbot/haijunbot_agent/haijunbot.py` (1496 lines)
  - `/home/skyfire/code/HaijunBot/src/haijunbot/haijunbot_agent/run_loop.py` (908 lines)
  - `/home/skyfire/code/HaijunBot/src/haijunbot/haijunbot_agent/tool_executor.py` (219 lines)
  - `/home/skyfire/code/HaijunBot/src/haijunbot/haijunbot_tools/registry.py` (1480 lines)

- haijun-code analysis sources:
  - `/home/skyfire/code/haijun-code/src/Tool.ts` (792 lines)
  - `/home/skyfire/code/haijun-code/src/tools.ts` (389 lines)
  - `/home/skyfire/code/haijun-code/src/QueryEngine.ts` (1295 lines)

---

## 2. Core Feature Comparison Table

### 2.1 Agent Initialization

| Dimension        | HaijunBot                            | haijun-code                        | Analysis                                  |
| --------------- | --------------------------------- | ---------------------------------- | ----------------------------------------- |
| **Initialization** | CLI entry `run_eli()` + Typer    | `QueryEngine` class constructor    | HaijunBot is command-based, haijun-code is class-instantiated |
| **Config loading** | YAML config files + env vars     | `QueryEngineConfig` object injection | HaijunBot config is scattered, haijun-code centralized |
| **State management** | `AgentStateManager` singleton + lock | `AppState` immutable + functional update | HaijunBot mutable state, haijun-code functional |
| **Session restore** | `--restore-session` param        | `initialMessages` param            | Both support session restoration         |

### 2.2 Tool System

| Dimension          | HaijunBot                          | haijun-code                              | Analysis                              |
| ----------------- | ------------------------------- | ---------------------------------------- | ------------------------------------- |
| **Tool definition** | `ToolRegistry` class + JSON Schema | `Tool<Input, Output, P>` generic interface | HaijunBot dynamic registration, haijun-code static typing |
| **Tool call format** | Jsonnet format `<TOOL_CALL>` tags | Juglow API native format              | HaijunBot custom format, haijun-code standard |
| **Tool discovery** | `get_all_tools()` dynamic loading | `getAllBaseTools()` static list + conditional import | HaijunBot supports dynamic MCP extension |
| **Permission control** | `execute_tool_confirm` boolean flag | `ToolPermissionContext` + `CanUseToolFn` | haijun-code permission system more complete |
| **Tool aliases**  | Not supported                  | `aliases?: string[]`                     | haijun-code supports backward compatibility |
| **Progress callback** | Not supported                  | `onProgress?: ToolCallProgress<P>`       | haijun-code supports real-time progress |

### 2.3 Execution Flow

| Dimension          | HaijunBot                                        | haijun-code                              | Analysis                            |
| ----------------- | --------------------------------------------- | ---------------------------------------- | ----------------------------------- |
| **Main loop**     | `AgentRunLoop` class + `_handle_tool_calls()` | `QueryEngine.submitMessage()` async generator | HaijunBot sync loop, haijun-code async stream |
| **Tool execution** | `execute_tool_call()` function                | `tool.call()` method                     | HaijunBot procedural, haijun-code OOP |
| **Multi-tool calls** | Supported, sequential execution              | Supported, parallel/sequential configurable | haijun-code more flexible           |
| **Context compression** | `check_and_compress_context()` based on token/rounds | Built-in compression + snip              | Both have compression mechanisms    |
| **Interrupt handling** | `_handle_interrupt_with_input()`              | `AbortController`                        | HaijunBot user interaction, haijun-code signal mechanism |

### 2.4 Error Handling

| Dimension              | HaijunBot                            | haijun-code                     | Analysis                            |
| --------------------- | --------------------------------- | ------------------------------- | ----------------------------------- |
| **Tool parse error**  | Returns error + tool usage hint  | Type validation + error codes   | HaijunBot user-friendly, haijun-code structured |
| **Tool execution exception** | try-catch + error message print | `ToolResult<T>` type wrapper    | HaijunBot simple catch, haijun-code type-safe |
| **Consecutive no-tool-call** | `_track_no_tool_call()` + LLM fix | Not explicitly implemented     | HaijunBot has auto-fix mechanism      |
| **Permission denial** | `user_confirm()` interactive confirm | `PermissionResult` + denial tracking | haijun-code permission system more complete |
| **API error**         | Not analyzed in detail           | `categorizeRetryableAPIError()` | haijun-code has error categorization |

---

## 3. Architecture Design Differences

### 3.1 Module Division

**HaijunBot architecture**:

```
haijunbot/
├── haijunbot_agent/          # Agent core
│   ├── haijunbot.py          # CLI entry
│   ├── run_loop.py        # Execution loop
│   ├── tool_executor.py   # Tool executor
│   └── agent_manager.py   # Agent management
├── haijunbot_tools/          # Tool system
│   ├── registry.py        # Tool registry
│   └── base.py            # Tool base class
└── haijunbot_utils/          # Utility functions
```

**haijun-code architecture**:

```
src/
├── Tool.ts                # Tool type definitions
├── tools.ts               # Tool registration
├── QueryEngine.ts         # Query engine
├── query.ts               # Query implementation
├── tools/                 # Tool implementations
│   ├── BashTool/
│   ├── FileEditTool/
│   └── ...
└── utils/                 # Utility functions
```

### 3.2 Interface Design

**HaijunBot tool interface**:

```python
class OutputHandlerProtocol(Protocol):
    def name(self) -> str: ...
    def can_handle(self, response: str) -> bool: ...
    def prompt(self) -> str: ...
    def handle(self, response: str, agent: Any) -> Tuple[bool, Any]: ...
```

**haijun-code tool interface**:

```typescript
type Tool<Input, Output, P> = {
  aliases?: string[]
  searchHint?: string
  call(args: z.infer<Input>, context: ToolUseContext, ...): Promise<ToolResult<Output>>
  description(input: z.infer<Input>, options: {...}): Promise<string>
  readonly inputSchema: Input
  outputSchema?: z.ZodType<unknown>
}
```

### 3.3 Dependency Relationships

**HaijunBot dependencies**:
- External: typer, rich, yaml, pyte
- Internal: haijunbot_utils, haijunbot_mcp, haijunbot_config

**haijun-code dependencies**:
- External: @juglow-ai/sdk, zod, lodash-es, react, ink
- Internal: services/, utils/, components/

---

## 4. Performance Optimization Comparison

### 4.1 Context Management

| Dimension         | HaijunBot                        | haijun-code              |
| ---------------- | ----------------------------- | ------------------------ |
| **Token monitoring** | `get_remaining_token_count()` | Built-in usage tracking  |
| **Compression trigger** | 25% remaining tokens or rounds | Similar mechanism        |
| **Compression strategy** | Call `summarize_context()`    | snip + compaction       |
| **File state cache** | Not explicitly implemented   | `FileStateCache` LRU     |

### 4.2 Resource Utilization

| Dimension        | HaijunBot          | haijun-code                  |
| --------------- | --------------- | ---------------------------- |
| **Concurrency model** | Single-thread + async IO | Async generators + AbortController |
| **Memory management** | Python GC      | Bun runtime optimization    |
| **Tool execution** | Sequential     | Supports parallel execution |

---

## 5. Extensibility Analysis

### 5.1 Plugin System

**HaijunBot**:
- MCP protocol support: `McpClient`, `SSEMcpClient`, `StdioMcpClient`, `StreamableMcpClient`
- Dynamic tool loading: `get_all_tools()` loads from config directory
- Role system: `get_roles_dirs()` supports multi-role configs

**haijun-code**:
- Conditional import: `feature()` function controls feature flags
- Agent definitions: `AgentDefinition` supports subagents
- Track system: `TrackTool` supports dynamic track discovery

### 5.2 Configuration Management

**HaijunBot**:
- YAML config files
- Environment variable overrides
- Command line args take precedence

**haijun-code**:
- `QueryEngineConfig` centralized config
- `AppState` immutable state
- Functional state updates

### 5.3 Third-Party Integration

**HaijunBot**:
- MCP protocol: supports multiple transport types
- Git integration: auto-detect repo, switch to code mode
- Tmux integration: dispatch tasks to tmux windows

**haijun-code**:
- MCP protocol: `MCPServerConnection`
- LSP integration: `LSPTool`
- Web tools: `WebFetchTool`, `WebSearchTool`

---

## 6. Strengths and Weaknesses

### 6.1 HaijunBot Strengths

1. **Comprehensive MCP protocol support**: Supports SSE, Stdio, Streamable multiple transports
2. **Auto-fix mechanism**: Auto-fix with LLM when consecutive no-tool-calls occur
3. **User-friendly interaction**: Rich library provides beautiful terminal output
4. **Auto Git repo detection**: Auto-switches to code development mode
5. **Tmux integration**: Supports task dispatch to tmux windows
6. **Jsonnet format**: Supports comments and trailing commas, more flexible

### 6.2 HaijunBot Weaknesses

1. **Insufficient type safety**: Python dynamic typing, lacks compile-time checks
2. **Simple permission system**: Only boolean flag for confirmation
3. **Tool interface not rich enough**: Lacks aliases, progress callbacks etc.
4. **Mutable state management**: Global singleton, potential thread-safety issues
5. **Limited async support**: Primarily sync model

### 6.3 haijun-code Strengths

1. **Type safety**: TypeScript + Zod provides complete type checking
2. **Comprehensive permission system**: `ToolPermissionContext` supports fine-grained control
3. **Rich tool interface**: Supports aliases, search hints, progress callbacks
4. **Functional state management**: Immutable state + pure function updates
5. **Async generators**: Supports streaming responses and parallel processing
6. **Feature flags**: Supports conditional compilation and feature toggles

### 6.4 haijun-code Weaknesses

1. **Steep learning curve**: Complex type system and functional programming
2. **Hard to debug**: Async generators and immutable state increase debugging complexity
3. **More dependencies**: React/Ink increases package size
4. **MCP support relatively simple**: Mainly focuses on Stdio transport

---

## 7. Optimization Recommendations

### 7.1 Optimizations HaijunBot Can Adopt from haijun-code

#### 7.1.1 Enhance Type Safety

**Recommendation**: Introduce type hints and static checking

```python
# Current
def handle(self, response: str, agent: Any) -> Tuple[bool, Any]:
    ...

# Suggested
from typing import Protocol, TypeVar, Generic
from dataclasses import dataclass

Input = TypeVar('Input')
Output = TypeVar('Output')

@dataclass
class ToolResult(Generic[Output]):
    data: Output
    new_messages: Optional[List[Message]] = None
    context_modifier: Optional[Callable[[AgentContext], AgentContext]] = None

class Tool(Protocol[Input, Output]):
    @property
    def name(self) -> str: ...
    @property
    def aliases(self) -> List[str]: ...
    @property
    def input_schema(self) -> Type[Input]: ...
    async def call(
        self,
        args: Input,
        context: ToolUseContext,
        on_progress: Optional[Callable[[ToolProgress], None]] = None
    ) -> ToolResult[Output]: ...
```

#### 7.1.2 Improve Permission System

**Recommendation**: Introduce fine-grained permission control

```python
# Suggested
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Set

class PermissionMode(Enum):
    DEFAULT = "default"
    BYPASS = "bypass"
    AUTO = "auto"

@dataclass
class ToolPermissionContext:
    mode: PermissionMode
    always_allow_rules: Dict[str, Set[str]]  # tool_name -> allowed_params
    always_deny_rules: Dict[str, Set[str]]
    always_ask_rules: Dict[str, Set[str]]
    is_bypass_permissions_mode_available: bool
    should_avoid_permission_prompts: bool  # for background agent

class PermissionResult:
    behavior: Literal["allow", "deny", "ask"]
    reason: Optional[str] = None
    updated_input: Optional[Dict] = None  # allow modifying input params
```

#### 7.1.3 Add Rich Tool Interface Features

**Recommendation**: Support aliases, search hints, progress callbacks

```python
# Suggested
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    aliases: List[str] = field(default_factory=list)  # backward compatibility
    search_hint: Optional[str] = None  # keyword search hint

    async def call(
        self,
        args: Dict[str, Any],
        context: ToolUseContext,
        on_progress: Optional[Callable[[ToolProgress], None]] = None
    ) -> ToolResult:
        ...
```

#### 7.1.4 Improve State Management

**Recommendation**: Introduce immutable state and functional updates

```python
# Suggested
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar('T')

@dataclass(frozen=True)
class AgentState:
    messages: Tuple[Message, ...]  # immutable tuple
    tool_permission_context: ToolPermissionContext
    file_state_cache: FileStateCache

class AgentStateManager:
    def __init__(self, initial_state: AgentState):
        self._state = initial_state

    @property
    def state(self) -> AgentState:
        return self._state

    def update_state(
        self,
        updater: Callable[[AgentState], AgentState]
    ) -> None:
        """Functional state update"""
        self._state = updater(self._state)
```

#### 7.1.5 Support Async Generators

**Recommendation**: Use async generators for streaming responses

```python
# Suggested
from typing import AsyncGenerator
import asyncio

class QueryEngine:
    async def submit_message(
        self,
        prompt: str,
        options: Optional[Dict] = None
    ) -> AsyncGenerator[AgentMessage, None]:
        """Async generator for streaming responses"""
        # Initialize
        yield AgentMessage(type="status", content="Processing...")

        # Call model
        async for chunk in self._call_model_stream(prompt):
            yield AgentMessage(type="content", content=chunk)

        # Execute tools
        for tool_call in tool_calls:
            yield AgentMessage(type="tool_start", content=tool_call)
            result = await self._execute_tool(tool_call)
            yield AgentMessage(type="tool_result", content=result)
```

### 7.2 Optimizations haijun-code Can Adopt from HaijunBot

#### 7.2.1 Enhance MCP Protocol Support

**Recommendation**: Support multiple transport types

```typescript
// Suggested
type MCPTransport = "stdio" | "sse" | "streamable";

interface MCPServerConfig {
  transport: MCPTransport;
  url?: string; // for SSE/Streamable
  command?: string; // for Stdio
  args?: string[];
}

class MCPClientFactory {
  static create(config: MCPServerConfig): MCPClient {
    switch (config.transport) {
      case "stdio":
        return new StdioMCPClient(config);
      case "sse":
        return new SSEMCPClient(config);
      case "streamable":
        return new StreamableMCPClient(config);
    }
  }
}
```

#### 7.2.2 Add Auto-Fix Mechanism

**Recommendation**: Implement auto-fix for consecutive no-tool-calls

```typescript
// Suggested
class QueryEngine {
  private noToolCallCount = 0;
  private readonly MAX_NO_TOOL_CALLS = 3;

  private async handleNoToolCall(): Promise<void> {
    this.noToolCallCount++;

    if (this.noToolCallCount >= this.MAX_NO_TOOL_CALLS) {
      // Fix with LLM
      const fixPrompt = this.buildFixPrompt();
      const fixedResponse = await this.callLLM(fixPrompt);
      this.noToolCallCount = 0;
      return fixedResponse;
    }
  }
}
```

#### 7.2.3 Add Auto Git Repo Detection

**Recommendation**: Auto-switch to code development mode

```typescript
// Suggested
class GitIntegration {
  static async detectAndSwitchMode(cwd: string): Promise<AgentMode> {
    const isGitRepo = await this.isGitRepository(cwd);

    if (isGitRepo) {
      const hasCode = await this.hasSourceCode(cwd);
      if (hasCode) {
        return "code";
      }
    }

    return "general";
  }
}
```

---

## 8. Conclusion

### 8.1 Key Findings

1. **Architecture differences**: HaijunBot uses modular monolithic architecture; haijun-code uses OOP + functional hybrid
2. **Type system**: haijun-code's TypeScript + Zod provides stronger type safety
3. **Tool system**: HaijunBot has more comprehensive MCP support; haijun-code has richer tool interface
4. **State management**: haijun-code's functional state management is safer
5. **Extensibility**: Both have good extension mechanisms, different approaches

### 8.2 Optimization Priority

**High priority**:
1. HaijunBot enhance type safety (introduce TypeHint and Protocol)
2. HaijunBot improve permission system (fine-grained control)
3. haijun-code enhance MCP protocol support

**Medium priority**:
1. HaijunBot add tool aliases and progress callbacks
2. HaijunBot improve state management (immutable state)
3. haijun-code add auto-fix mechanism

**Low priority**:
1. HaijunBot support async generators
2. haijun-code add auto Git repo detection

### 8.3 Next Steps

1. Write SDD spec document based on this report
2. Select high-priority optimizations for detailed design
3. Develop implementation plan and timeline