---
name: reverse_engineering
description: Triggered when there is a need to derive design intent and architecture from existing code. Triggered whenever the user mentions "reverse engineering", "code reverse-construction", "deriving design", "understanding architecture", or "project reverse-construction". Not triggered: forward-designing a new architecture; only reading code without deriving design; code refactoring that does not involve understanding the original design.
---

# Reverse Engineering Rule

Extract design information from existing code and produce a language-agnostic design plan.

## Two Scenarios

| Scenario             | Applicable case                               |
| ---------------- | -------------------------------------- |
| **Project reverse-construction**     | Analyzing the architecture, module relationships, and overall design of an entire project |
| **Code reverse-design** | Analyzing the functionality and design of a single file or code snippet     |

**Expected result**: a complete architecture design plan, clear module division, component dependency graph, data flow analysis, tech stack summary, and language-agnostic design.

---

# Core Principles

## General Principles (applicable to both scenarios)

| Principle         | Requirement                                       |
| ------------ | ------------------------------------------ |
| **Completeness**   | The design plan covers all functional points and provides a feature comparison table for verification |
| **Language-agnostic** | Contains no concrete language syntax, using general design concepts           |
| **Traceability**   | Records the code location corresponding to each design decision             |
| **Clarity**   | Describes with accurate language and provides concrete examples               |

## Project Reverse-Construction-Specific Principles

| Principle       | Requirement                                     |
| ---------- | ---------------------------------------- |
| **Systematic** | Starts from the root directory and organizes the analysis by directory hierarchy           |
| **Hierarchical** | The task hierarchy matches the directory hierarchy, going deeper level by level from top to bottom |
| **Modular** | Clarifies the responsibility boundary of each module and analyzes inter-module dependencies   |

---

# Scenario 1: Project Reverse-Construction Operation Flow

## Operation 1: Project Structure Scan

1. **Scan the root directory** - identify the project type (Rust/Python/JS, etc.), build system (Cargo.toml/package.json, etc.), and configuration files
2. **Identify the directory structure** - source directory (src/), test directory (tests/), documentation directory (docs/), configuration directory (config/)
3. **Analyze the organization pattern** - determine monolith/multi-module, and identify the module division method

**Output**: project structure overview, list of main directory files, tech stack annotations

## Operation 2: Create a Module Analysis Task Tree

1. **Identify the main modules** - according to the directory structure, each main module corresponds to one sub task
2. **Build the hierarchy** - top level → main modules → submodules/components; task naming: `Analyze module: [module name]`
3. **Assign tasks** - each sub task focuses on one module, keeping tasks independent

**Task tree example**:

```text
Project reverse-engineering task
├── Analyze module: Core business logic
│   ├── Analyze submodule: User management
│   └── Analyze submodule: Order processing
└── Analyze module: Infrastructure
    ├── Analyze submodule: Configuration management
    └── Analyze submodule: Logging system
```

## Operation 3: In-Depth Module Analysis

For each module, execute:

1. **Structure analysis** - `list_dir` to list files and count code volume and type distribution
2. **Code reading** - `read_file` to read key files and identify entry points and core classes/functions
3. **Dependency analysis** - identify internal/external dependencies and draw a dependency graph
4. **Pattern recognition** - identify design patterns (factory/strategy, etc.) and architecture patterns (MVC/layered, etc.)

**Output per module**: responsibility description, structure description, core components, dependency graph, design patterns, code source

## Operation 4: Cross-Module Relationship Analysis

1. **Data flow analysis** - trace data flow paths, conversion nodes, and storage locations
2. **Control flow analysis** - analyze request flow, business processes, and exception propagation
3. **Interface analysis** - identify interface definitions, invocation methods (sync/async), and version compatibility
4. **Dependency graph construction** - build a dependency graph and identify circular dependencies and core/peripheral modules

## Operation 5: Documentation Generation

1. **Aggregate results** - integrate the analysis results and unify terminology style
2. **Build the architecture diagram** - draw the overall architecture diagram and annotate module relationships
3. **Create the directory structure** - create the document tree under `{{ git_root_dir }}/.haijunbot/rules/project_info/`
4. **Generate module documents** - generate an independent Markdown file for each submodule
5. **Generate the project overview** - generate `README.md`, containing the project overview, module index, and dependency graph
6. **Verify completeness** - check coverage, document correspondence, and structural consistency

**Document directory structure**:

```text
{{ git_root_dir }}/.haijunbot/rules/project_info/
├── README.md                      # project overview
├── core_business/                 # core business
│   ├── user_management.md
│   └── order_processing.md
├── data_access/                   # data access
│   └── database_models.md
└── infrastructure/                 # infrastructure
    └── logging.md
```

---

# Scenario 2: Code Reverse-Design Operation Flow

## Four-Stage Flow

| Stage            | Content                                               |
| --------------- | -------------------------------------------------- |
| **1. Code reading** | `read_file` to analyze the code and identify the architecture, main modules, and core components     |
| **2. Feature extraction** | Extract core features, process analysis, interface analysis, configuration summary         |
| **3. Design construction** | Build a language-agnostic design, define module boundaries, describe algorithm flows             |
| **4. Verification and confirmation** | Completeness check, feasibility confirmation, suggestions provided                 |

---

# Output Format Requirements

## Document Location Specification

| Type           | Path                                                                           |
| -------------- | ------------------------------------------------------------------------------ |
| **Document root directory** | `{{ git_root_dir }}/.haijunbot/rules/project_info/`                               |
| **Project overview**   | `{{ git_root_dir }}/.haijunbot/rules/project_info/README.md`                      |
| **Module document**   | `{{ git_root_dir }}/.haijunbot/rules/project_info/<module_path>/<module_name>.md` |

**Naming convention**: lowercase letters + underscores, with directories/files consistent with the module name

## Module Document Format

````markdown
# [Module name] Design Document

## Module Overview

- **Responsibility**: the module's main functional scope
- **Code location**: `{{ git_root_dir }}/<module_path>`
- **Code source**:
  - Directory: `{{ git_root_dir }}/<source_dir>`
  - File: `{{ git_root_dir }}/<source_file>` - purpose description

## Module Structure

```text
module_name/
├── sub_component_1/  # subcomponent 1
└── component.rs      # component
```
````

## Core Components

### Component 1: Component name

- **Location**: `module_name/component.rs`
- **Responsibility**: function description
- **Interface**: main interface description

## Dependencies

- **Depends on**: module_a (reason)
- **Depended on by**: module_b (purpose)
- **External dependency**: library name (version and purpose)

## Design Patterns

- **Pattern name**: application location + application scenario + implementation method

## Interface Design

### External interface

- **Interface 1**: function description
  - Input: parameter description
  - Output: return description
  - Error handling: error code description

## Data Flow

```text
Input ──> component1 ──> component2 ──> output
```

## Related Modules

- [Module A](../module_a.md)

````

## Large Module Splitting Strategy

**Splitting conditions** (any one being met):
- Document lines > 500
- Functional points > 5
- Number of files > 20
- High complexity

**Splitting methods**:
- By functional point: `initialization.md`, `message_dispatch.md`
- By layer: `transport_layer.md`, `application_layer.md`
- By component: `render_engine.md`, `event_system.md`

**After splitting, a README.md overview must be generated**, containing: module overview, feature index, dependency graph, data flow diagram, navigation links

---

# Project Reverse-Construction Output Format (Simplified Version)

```markdown
# Project Reverse-Engineering Design Plan

## 1. Project Overview

- **Project name/type/tech stack**: basic information
- **Code source**:
  - Directory: `{{ git_root_dir }}/<dir>`
  - File: `{{ git_root_dir }}/<file>` - description
- **Project structure**:

```text
Project root/
├── src/
│   └── module_a/
└── tests/
````

## 2. Overall Architecture

- **Architecture pattern**: monolith/microservices/layered/event-driven, etc.
- **System layers**:

```text
┌──────────────────┐
│  Presentation layer/interface layer   │
├──────────────────┤
│  Business logic layer     │
├──────────────────┤
│  Data access layer     │
├──────────────────┤
│  Infrastructure layer     │
└──────────────────┘
```

## 3. Module Design

### Module A: Module name

- **Responsibility**: function description
- **Code source**: directory/file
- **Structure**: directory tree
- **Core components**: components and responsibilities
- **Dependencies**: depends-on/depended-on-by/external dependencies
- **Design patterns**: patterns used

### Module Dependency Graph

```text
module_a ──> module_c
module_b ──> module_d ──> module_e
```

## 4. Data Architecture

- **Core entities**: main data entities and relationships
- **Data flow diagram**:

```text
User input ──> interface layer ──> business layer ──> data layer ──> storage
```

## 5. Tech Stack

- **Language/framework**: technologies and versions used
- **Build/test tools**: toolchain
- **Main dependencies**: third-party libraries

## 6. Design Decisions

- **Decision title**: background + approach + impact + code location

## 7. Summary

- **Project characteristics**: strengths and features
- **Potential issues**: technical debt, improvement suggestions
- **Learning points**: core concepts, key code

## Appendix

- **Code reference index**: list of key files
- **Module document index**: links to each module document

````

---

# Code Reverse-Design Output Format (Simplified Version)

```markdown
### Code Reverse-Construction Design Plan

## 1. Project Overview

- **Code functionality**: core function description
- **Code source**:
  - File: `{{ git_root_dir }}/<file>` - description
  - Directory: `{{ git_root_dir }}/<dir>` - description

## 2. Architecture Design

- **Architecture pattern**: layered/microservices/event-driven, etc.
- **Module design**:
  - **Module A**: responsibility + input/output + dependencies
- **Data architecture**: data model + data flow + storage scheme

## 3. Feature Design

- **Functional point 1**: processing flow + business rules + boundary conditions
- **Functional point 2**: same as above
- **Algorithm design**: algorithm principle + implementation steps + complexity analysis

## 4. Interface Design

- **External interface**: name + input + output + error handling
- **Configuration interface**: environment configuration + parameter configuration

## 5. Implementation Guidance

- **Technical suggestions**: language/framework/dependencies
- **Development order**: stage 1 → stage 2 → stage 3
- **Quality assurance**: test strategy + performance requirements + security considerations

## 6. Feature Alignment Verification

- **Feature comparison table**: original code feature ↔ new design plan mapping
- **Difference description**: improvements and optimization points
````

---

# Execution Checklist

## Project Reverse-Construction Checklist

| Stage         | Check item                                  |
| ------------ | --------------------------------------- |
| **Structure scan** | [ ] Root directory scanned to identify the project type              |
|              | [ ] Main directory structure identified                    |
|              | [ ] Project structure overview generated                    |
| **Task tree**   | [ ] All main modules identified                    |
|              | [ ] A sub task created for each module             |
|              | [ ] Task hierarchy matches directory hierarchy              |
| **Module analysis** | [ ] The structure of each module analyzed                  |
|              | [ ] The dependencies of each module identified              |
|              | [ ] Design patterns identified                        |
|              | [ ] Code source recorded                        |
| **Relationship analysis** | [ ] Data flow/control flow analyzed                   |
|              | [ ] Dependency graph constructed                      |
| **Documentation generation** | [ ] Document structure created under `project_info/`   |
|              | [ ] An independent document generated for each module              |
|              | [ ] README.md generated                      |
|              | [ ] Completeness verified                          |

## Code Reverse-Design Checklist

| Stage         | Check item                       |
| ------------ | ---------------------------- |
| **Code analysis** | [ ] The code architecture has been fully read and understood |
|              | [ ] All core features have been extracted       |
|              | [ ] Code source recorded             |
| **Design plan** | [ ] A language-agnostic design plan has been constructed   |
|              | [ ] A clear module division has been defined       |
|              | [ ] Data flow and control flow have been clarified       |
| **Verification and confirmation** | [ ] The design plan completely covers all features |
|              | [ ] A feature comparison table is provided to verify completeness   |

---

# Best Practices

## Project Reverse-Construction

1. **From macro to micro** - first the overall architecture, then the specific modules; first module responsibilities, then implementation details
2. **Modular analysis** - analyze each module independently, focusing on boundaries and responsibility division
3. **Dependency tracing** - trace the call chain from the entry point and identify core/peripheral modules
4. **Code reading** - prioritize reading interface definitions and public APIs, focusing on data structures and key algorithms

## Code Reverse-Design

1. **Feature-oriented** - focus on the feature implementation rather than syntax details
2. **Level of abstraction** - maintain an appropriate abstraction, neither too concrete nor too abstract
3. **Multi-angle verification** - verify whether the understanding is correct from different angles

## FAQ

| Problem         | Solution                                   |
| ------------ | ------------------------------------------ |
| Complex project structure | Start from the build configuration files and check the entry file and main function     |
| Complex dependencies | Draw a dependency graph and identify core/peripheral modules                  |
| Large code volume     | Prioritize analyzing core modules, focusing on interface definitions rather than implementation details   |
| Missing functional points   | Build a feature list and think from the user's perspective                 |
| Design too concrete | Use general terminology and focus on "what to do" rather than "how to do it"       |

---

# Related Resources

- [Architecture diagram generation rule](../architecture_design/architecture-diagram-generation.md)
- [Clean architecture](../architecture_design/clean_architecture.md)
- [SOLID design principles](../architecture_design/solid.md)
