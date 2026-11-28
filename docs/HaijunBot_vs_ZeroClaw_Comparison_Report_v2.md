# HaijunBot vs ZeroClaw Comparison Report

## Executive Summary

HaijunBot and ZeroClaw are both AI Agent-related projects, but their core positioning is not the same.

- **HaijunBot** leans more toward a developer-facing code engineering Agent platform, with a focus on landing Agent capabilities into research and development workflows such as code reading, modification, verification, commit, rule reuse, and experience accumulation.
- **ZeroClaw** leans more toward a runtime foundation for general-purpose Agents, with a focus on model access, channel access, tool extension, memory, security, gateway, and runtime abstraction.

Therefore, the two are not well understood as simple substitutes for each other. A more accurate statement is: they overlap, but their core strengths lie at different layers. HaijunBot is stronger in the research and development workflow closed loop, while ZeroClaw is stronger in runtime infrastructure and multi-environment adaptation.

## Project Positioning

### HaijunBot

HaijunBot's overall structure is closer to a "developer workbench." It does not merely provide conversational Agent capabilities; it layers code engineering capabilities on top of the general Agent, such as code analysis, file modification, build verification, static checking, Git workflows, rule loading, methodology reuse, and specialized toolchains.

From the actual module organization, HaijunBot's focus is on:

- Making the Agent participate in code tasks more stably
- Incorporating research and development standards, experience, and processes into the execution process
- Providing specialized capabilities for specific engineering tasks, such as security analysis, C→Rust migration, Windows GUI automation, etc.

### ZeroClaw

ZeroClaw's overall structure is closer to an "Agent Runtime." It emphasizes low-level abstraction capabilities more, splitting model providers, messaging channels, tools, memory, runtime, security, and gateway into composable subsystems so that they can be reused in different environments, with different access methods, and for different deployment goals.

From the architectural intent, ZeroClaw is better suited to take on the following roles:

- Serving as the operational foundation for general-purpose Agents
- Being deployed across multiple channels, environments, and access methods
- Maintaining strong control over resources, performance, security, and module boundaries

## Core Comparison Matrix

### High-Level Overview Comparison Table

| Dimension    | HaijunBot                                  | ZeroClaw                                         |
| ------------ | --------------------------------------- | ------------------------------------------------ |
| Project role | Code engineering Agent platform         | General-purpose Agent Runtime                    |
| Core focus   | Development workflow closed loop, rule and experience reuse | Runtime abstraction, multi-channel access, lightweight deployment |
| Representative capabilities | CodeAgent, rules system, methodology, specialized toolchain | Provider/Channel/Tool/Memory/Runtime, security and gateway |
| More prominent advantages | Engineering rigor, operability, developer experience | Modularity, portability, performance and resource efficiency |
| Clearer boundaries | Weak general-purpose runtime abstraction, limited multi-channel capability | Weak code engineering closed loop, insufficient development workflow encapsulation |

### Core Capability Comparison Table

| Capability dimension | HaijunBot         | ZeroClaw       | Explanation                                                                  |
| -------------------- | -------------- | -------------- | ---------------------------------------------------------------------------- |
| General Agent capability | Supported  | Supported      | Both possess foundational Agent execution capabilities.                      |
| Code engineering closed loop | Strong  | Not a focus    | HaijunBot has CodeAgent, build verification, Lint, impact analysis, and Git workflows. |
| Multi-model support  | Supported      | Supported      | HaijunBot leans toward platform configuration and model groups; ZeroClaw leans toward Provider abstraction and routing. |
| Multi-channel access | Limited        | Strong         | HaijunBot is mainly reflected as Web/Gateway; ZeroClaw has an independent Channel subsystem. |
| Tool extension       | Supported      | Supported      | HaijunBot is based on a tool registry; ZeroClaw is based on Tool Trait.         |
| Memory system        | Supported      | Supported      | HaijunBot leans toward task memory and organization; ZeroClaw leans toward runtime memory infrastructure. |
| Security capability  | Supported      | Supported      | HaijunBot leans toward security analysis and execution confirmation; ZeroClaw leans toward the runtime security control plane. |
| Rules system         | Supported      | No clear correspondence | The rules system is an important differentiating capability of HaijunBot.       |
| Methodology system   | Supported      | No clear correspondence | HaijunBot reuses historical experience in a structured way.                     |
| Specialized capability extension | Strong | Yes, but in a different direction | HaijunBot has specialized modules such as C→Rust migration and security analysis; ZeroClaw has extension directions such as hardware and peripherals. |
| Observability subsystem | No independent peer module | Supported | ZeroClaw has an independent observability subsystem.                         |

### Architecture Style Comparison Table

| Architecture dimension | HaijunBot                               | ZeroClaw                                           |
| ---------------------- | ------------------------------------ | -------------------------------------------------- |
| Architecture style     | Layered (Agent → CodeAgent → specialized capabilities) | Trait-driven pluggable architecture |
| Extension mechanism    | Tools + rules + methodology + specialized modules | Provider / Channel / Tool / Memory / Runtime Trait |
| Module boundaries      | Oriented toward business capability organization | Oriented toward runtime subsystem organization |
| Maintainability characteristics | Closer to actual task flows and development processes | More emphasis on abstraction boundaries and low-level replaceability |

## HaijunBot Core Capability Overview

HaijunBot's foundational capabilities are provided by the general Agent layer, on top of which an enhancement layer oriented toward code tasks is further formed.

### 1. General Agent and Task Execution

HaijunBot provides foundational Agent execution capabilities, including task processing, context management, tool invocation, user confirmation, and session saving and restoration. This enables it not only to hold conversations but also to continuously advance the execution process around specific tasks.

### 2. CodeAgent and the Code Engineering Closed Loop

HaijunBot's core differentiating capability lies in CodeAgent. Compared with a general-purpose Agent, it emphasizes completing task closed loops around a code repository, mainly including:

- Code context analysis
- File reading and modification
- diff display
- Build verification
- Static checking
- Git workflow assistance
- Impact scope analysis
- worktree support

This makes HaijunBot better suited to directly participating in development, fixing, refactoring, and review-type tasks.

### 3. Rules System

HaijunBot treats the rules system as part of the execution process, rather than existing merely as documentation. Rules can participate in task understanding, execution constraints, and output style control. This makes HaijunBot more outstanding in "standard reuse" and "team experience codification."

### 4. Methodology System

In addition to rules, HaijunBot also emphasizes methodology reuse. Its goal is not just to save static knowledge, but to turn historical task experience into reusable execution methods, thereby reducing repeated trial and error.

### 5. Tools and Specialized Capabilities

HaijunBot connects capabilities such as file reading, file editing, script execution, rule loading, memory management, and Web search through its tool system. At the same time, it also provides several specialized modules, for example:

- A specialized workflow for C→Rust migration
- A specialized workflow for code security analysis
- A specialized capability for Windows GUI automation
- A Gateway capability for Web access

## ZeroClaw Core Capability Overview

ZeroClaw's focus is not on doing deep encapsulation around a certain kind of business scenario, but on providing a more complete Agent runtime foundation.

### 1. Provider Abstraction

ZeroClaw independently abstracts model providers. Such a design is more conducive to uniformly handling model access, switching, routing, and extension.

### 2. Channel Abstraction

ZeroClaw has a clear channel subsystem for connecting to different communication entry points. This is also an important difference from HaijunBot: HaijunBot has a gateway and interaction entry points, but ZeroClaw emphasizes large-scale channelized access capability more.

### 3. Tool, Memory, and Runtime

ZeroClaw organizes tools, memory, and runtime as independent subsystems. This way of splitting makes it more like a low-level platform rather than a single-scenario application:

- Tool is responsible for capability extension
- Memory is responsible for state and knowledge memory
- Runtime is responsible for execution environment abstraction

### 4. Security, Gateway, and Observability

ZeroClaw also presents a more foundation-oriented structure in terms of security, gateway, and observability:

- Security leans more toward the runtime control and policy layer
- Gateway leans more toward the unified access layer
- Observability leans more toward system-level observation and tracing

This shows that ZeroClaw's main advantage lies in systematized low-level capabilities, rather than the code engineering workflow itself.

## Core Module Mapping

The two are not a simple one-to-one correspondence. The more accurate expression should be "direct correspondence / functionally similar / no clear correspondence."

### Correspondence of HaijunBot's Core Modules in ZeroClaw

| HaijunBot core module                            | Corresponding ZeroClaw module              | Correspondence | Explanation                                                                                              |
| --------------------------------------------- | ------------------------------------------ | -------------- | -------------------------------------------------------------------------------------------------------- |
| `haijunbot_agent`                                | `agent` + `runtime`                        | Functionally similar | Both undertake the Agent main loop and execution orchestration responsibilities, but ZeroClaw leans more toward runtime abstraction, while HaijunBot leans more toward task execution flow and context management. |
| `haijunbot_code_agent`                           | No clear complete correspondence           | No clear correspondence | This is HaijunBot's most core differentiating capability. No dedicated layer encapsulating a code engineering closed loop is seen in ZeroClaw. |
| Rules system                                  | `tracks` / `trackforge` / `plugins` are analogous | Functionally similar | ZeroClaw has track and plugin extension, but HaijunBot's rule system emphasizes constraints and prompt construction more. |
| Methodology system                            | No clear correspondence                    | No clear correspondence | HaijunBot turns historical experience into execution methods; no clearly equivalent module is seen in ZeroClaw. |
| `haijunbot_tools`                                | `tools`                                    | Direct correspondence | Both have clear tool abstractions and registration/execution mechanisms.                                |
| `haijunbot_platform` / `haijunbot_platform_manager` | `providers` + `auth`                       | Functionally similar | Both support multi-model access; ZeroClaw leans more toward the runtime Provider system, while HaijunBot leans more toward platform configuration and management. |
| `haijunbot_mcp`                                  | MCP-related tool capabilities              | Direct correspondence | Both can extend external tool capabilities through MCP.                                                  |
| `haijunbot_web_gateway` / `haijunbot_gateway`       | `gateway`                                  | Direct correspondence | Both have a gateway layer, but the emphasis of their specific responsibilities differs.                  |
| `haijunbot_memory_organizer`                     | `memory`                                   | Functionally similar | Both support memory, but HaijunBot leans more toward post-task organization and long-term reuse, while ZeroClaw leans more toward the infrastructure layer. |
| `haijunbot_sec`                                  | `security`                                 | Functionally similar | HaijunBot leans more toward code-repository-oriented security analysis, while ZeroClaw leans more toward runtime security control. |
| `haijunbot_c2rust`                               | No clear correspondence                    | No clear correspondence | This is HaijunBot's specialized engineering capability; no equivalent module is currently seen in ZeroClaw. |
| `haijunbot_smart_shell` / Git auxiliary modules  | Shell / Git-type tools                     | Functionally similar | Both can perform shell or Git-type operations, but HaijunBot emphasizes developer workflows more.            |

### Correspondence of ZeroClaw's Core Modules in HaijunBot

| ZeroClaw core module                            | Corresponding HaijunBot module                       | Correspondence | Explanation                                                       |
| ----------------------------------------------- | ------------------------------------------------- | -------------- | ----------------------------------------------------------------- |
| `providers`                                     | `haijunbot_platform` / `haijunbot_platform_manager`     | Functionally similar | HaijunBot also supports multi-model platforms, but its abstraction level leans more toward configuration and platform management. |
| `channels`                                      | `haijunbot_web_gateway` / `haijunbot_gateway` (partial correspondence) | Partial correspondence | HaijunBot has Web access, but no channel matrix of the same magnitude as ZeroClaw's. |
| `tools`                                         | `haijunbot_tools`                                    | Direct correspondence | This is the module where the two are most easily aligned.         |
| `memory`                                        | Memory management-related modules                 | Functionally similar | HaijunBot has a memory system, but its degree of foundation-ization is less clear than ZeroClaw's. |
| `runtime`                                       | The internal execution flow of `haijunbot_agent` / `haijunbot_code_agent` | Functionally similar | HaijunBot has execution capability, but it has not become an independent peer runtime subsystem. |
| `observability`                                 | No clear independent corresponding module         | No clear correspondence | HaijunBot lacks an observability subsystem at the same level as ZeroClaw's, independently systematized. |
| `security`                                      | `haijunbot_sec` + execution confirmation mechanism   | Functionally similar | HaijunBot also has security-related capabilities, but leans more toward the tool and process layer. |
| `approval` / `auth`                             | Tool confirmation, platform authentication, gateway authentication | Functionally similar | HaijunBot's related capabilities are more scattered, while ZeroClaw's are more systematized. |
| `plugins` / `tracks` / `trackforge`             | Rules system, tool extension, MCP extension       | Functionally similar | Both can extend, but their extension philosophies differ.         |
| `gateway`                                       | `haijunbot_web_gateway` / `haijunbot_gateway`           | Direct correspondence | Both undertake the responsibilities of external access entry point and session bridging. |
| `hardware` / `peripherals`                      | No clear correspondence                           | No clear correspondence | ZeroClaw has extended toward hardware and peripheral control, which is not HaijunBot's main direction. |
| `cron` / `daemon`                               | No clear independent correspondence               | No clear correspondence | HaijunBot has task automation capabilities, but no independent, systematized background scheduling subsystem was found. |
| `rag` / `knowledge_graph` / `verifiable_intent` | No complete equivalent module                     | No clear correspondence | HaijunBot can be enhanced through rules, memory, and tools, but no independent peer subsystem was found. |

### Module Mapping Conclusion

- HaijunBot's strength is not in the general-purpose runtime foundation, but in upper-layer workflow encapsulation oriented toward code engineering.
- ZeroClaw's strength is not in the code engineering closed loop, but in the generality and modularity of runtime infrastructure.
- The areas where the two truly overlap are mainly model access, tool system, memory, gateway, and some security capabilities.
- The areas where the two truly diverge are mainly:
  - **HaijunBot**: rules, methodology, code engineering closed loop, specialized engineering capabilities
  - **ZeroClaw**: multi-channel connectivity, runtime abstraction, observability, security foundation, hardware and edge extension

## Applicable Scenario Comparison

### Scenarios Better Suited to Choosing HaijunBot

- Code development, refactoring, review, and fixing
- Automated and semi-automated collaboration in research and development workflows
- Scenarios requiring rule accumulation, experience reuse, and standard execution
- Scenarios requiring specialized engineering capabilities, such as C→Rust migration, security analysis, Windows GUI automation

### Scenarios Better Suited to Choosing ZeroClaw

- General-purpose Agent systems requiring multi-channel access
- Scenarios with high requirements for startup speed, resource usage, and runtime portability
- Edge computing, long-running, and low-resource deployment scenarios
- Scenarios requiring more complete runtime security, gateway, and observability capabilities

### Areas That Should Not Be Simply Conflated

- HaijunBot's focus is not on building an extremely lightweight general-purpose Runtime, nor on covering a large number of messaging channels.
- ZeroClaw's focus is not on building a complete development closed loop around code engineering, nor on making rule and methodology accumulation a core capability.

## Summary

HaijunBot and ZeroClaw represent two different directions of AI Agent productization.

- **HaijunBot** is more like a "developer workbench," focusing on embedding Agent capabilities into the code engineering workflow.
- **ZeroClaw** is more like an "Agent runtime foundation," focusing on making Agent capabilities into composable, portable, and extensible infrastructure.

Comparing the two in terms of "whether they have the same number of features" easily leads to distorted conclusions. A more reasonable way to compare is to return to their respective design goals and applicable scenarios:

- When the goal is research and development workflows, code task execution, rule reuse, and specialized engineering capabilities, HaijunBot is more targeted.
- When the goal is to build a general-purpose Agent operating platform, connecting multiple channels, deploying across multiple environments, and emphasizing foundational capabilities, ZeroClaw is more representative.

Therefore, the final conclusion of this comparison is not "who replaces whom," but "the two occupy different positions, have different focuses, and suit different scenarios."
