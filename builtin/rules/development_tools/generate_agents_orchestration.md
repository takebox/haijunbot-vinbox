---
name: generate_agents_orchestration
description: Triggered when there is a need to generate an Agents orchestration file to batch-create Agents. Triggered whenever the user mentions "orchestration file", "batch create Agents", "Agent orchestration", or "OrganizeAgents configuration". Not triggered: only creating a single Agent; only viewing the Agent list; inter-Agent communication that does not involve orchestration.
---

# Agents Orchestration File Generation Rule

## Rule Overview

This rule guides the user in creating YAML-format Agents orchestration files that, combined with the `@OrganizeAgents` command, implement batch Agent creation.

> **Two kinds of orchestration files (distinguish the semantics)**:
>
> - **`.yaml` / `.yml` (this rule)** = **organizational orchestration**: batch-creates Agents, generates no `flow`, and does not run pipeline scheduling.
> - **`.flow`** = **process orchestration**: uses the Python DSL to generate a DAG (`agents` + `flow`), executed through pipeline scheduling. The DSL library is in `src/haijunbot/haijunbot_tools/orchestration_dsl.py`, and the design document is in `docs/design/orchestration-python-dsl.md`.
>
> This rule only covers `.yaml` organizational orchestration; when "multi-stage dependencies/pipeline scheduling" is needed, use `.flow`.
>
> **`.flow` also supports the runtime loop primitive** `loop(name, body, until, max_iterations)`: `body` is a subgraph composed of declared stage names, and the whole section re-runs until `until` is satisfied or the limit is reached; `until` can use the whitelisted functions `file(path)` (reads the body text of the product within work_dir) and `contains(text, substr)`. See chapter 11 of the design document for details.

## The Principles You Must Follow

### 1. File format requirements

**Requirements:**

- **Must**: use YAML format
- **Must**: use UTF-8 encoding
- **Must**: the file root node contains an `agents` list
- **Forbidden**: using Tab indentation in orchestration files (YAML does not support Tabs)

### 2. Field definitions

#### The agents list (required)

`agents` is a list; each element defines the configuration of one Agent.

#### Agent configuration fields

| Field name            | Type   | Required | Default value | Description                                                       |
| --------------------- | ------ | -------- | ------------- | ----------------------------------------------------------------- |
| `name`                | string | no       | `agent_N`     | Agent name, used for identification and display                   |
| `type`                | string | no       | `code_agent`  | Agent type, e.g. `agent`, `code_agent`, etc.                      |
| `working_dir`         | string | **yes**  | -             | Working directory, the Agent's working path                       |
| `llm_group`           | string | no       | `default`     | Model group name                                                  |
| `tool_group`          | string | no       | `default`     | Tool group name                                                   |
| `config_file`         | string | no       | -             | Configuration file path                                           |
| `task`                | string | no       | -             | Initial task description                                          |
| `additional_args`     | string | no       | -             | Additional arguments                                              |
| `worktree`            | bool   | no       | `false`       | Whether to use a git worktree                                     |
| `quick_mode`          | bool   | no       | `false`       | Whether to enable quick mode                                      |
| `no_interaction_mode` | bool   | no       | `false`       | Whether to enable no-interaction mode (when enabled, task is required; **not recommended**) |
| `node_id`             | string | no       | the node the executor is on | Target node ID, specifying which node the Agent is created on    |
| `proxy_node`          | string | no       | -             | Proxy node ID                                                     |
| `access_acl`          | object | no       | -             | Access control, shaped like `{read: [user_id...], interact: [user_id...]}` |

**About ownership (owner):**

The orchestration file **does not provide** an `owner_id` field. The ownership of the created Agents is determined by the **owner of the Agent that executes `@OrganizeAgents`**, regardless of the author of the orchestration file. This design prevents "the file writer gaining control of someone else's Agents out of thin air".

### 3. Field constraints

**Must follow:**

- `working_dir` must be a valid directory path
- `type` must be a supported Agent type (`agent` or `code_agent`)
- **Forbidden**: using `no_interaction_mode: true` by default; prefer interaction mode so that manual confirmation and adjustment are possible
- When `no_interaction_mode: true`, the `task` field is required
- `name` should be descriptive for easy identification

### Operation 1: Determine the orchestration requirements

Before creating an orchestration file, the following information must be clear:

1. How many Agents need to be created?
2. What is the type of each Agent?
3. What is the working directory of each Agent?
4. Is a model group required?
5. Is an initial task required?
6. Is no-interaction mode required? (enable it only when unattended execution is explicitly needed; not enabled by default)
7. Is a target node (`node_id`) required? (default: created on the executor's node)
8. Is access control (`access_acl`) required?

### Operation 2: Write the orchestration file

Write the YAML-format orchestration file according to the requirements.

**Basic template (recommended, interaction mode):**

```yaml
agents:
  - name: "agent_name"
    type: "code_agent"
    working_dir: "/path/to/project"
```

**Complete template (interaction mode):**

```yaml
agents:
  - name: "agent_1"
    type: "code_agent"
    working_dir: "/home/user/project1"
    llm_group: "default"
    tool_group: "default"
    task: "implement the user login feature"

  - name: "agent_2"
    type: "agent"
    working_dir: "/home/user/project2"
    llm_group: "gpt4"
    task: "analyze the requirements document"

  - name: "agent_3"
    type: "code_agent"
    working_dir: "/home/user/project3"
    worktree: true
    quick_mode: true
```

**Unattended template (use only when unattended operation is explicitly needed):**

```yaml
agents:
  - name: "agent_1"
    type: "code_agent"
    working_dir: "/home/user/project1"
    task: "implement the user login feature"
    no_interaction_mode: true
```

### Operation 3: Validate the orchestration file

After creating the orchestration file, verify the following:

1. The YAML syntax is correct
2. The `agents` list exists and is not empty
3. Each Agent configuration contains the required field `working_dir`
4. Agents in no-interaction mode contain the `task` field

## Orchestration File Examples

### Example 1: Simple orchestration

Create two code Agents with the default configuration:

```yaml
agents:
  - name: "frontend_dev"
    type: "code_agent"
    working_dir: "/home/user/frontend"

  - name: "backend_dev"
    type: "code_agent"
    working_dir: "/home/user/backend"
```

### Example 2: Orchestration with tasks (interaction mode, recommended)

Create multiple Agents and assign initial tasks, using interaction mode for manual confirmation:

```yaml
agents:
  - name: "feature_auth"
    type: "code_agent"
    working_dir: "/home/user/myapp"
    task: "implement the user authentication module, including login, registration, and password reset"

  - name: "feature_api"
    type: "code_agent"
    working_dir: "/home/user/myapp"
    task: "design and implement the RESTful API"

  - name: "docs_writer"
    type: "agent"
    working_dir: "/home/user/myapp"
    task: "write the API documentation"
```

### Example 3: Multi-project orchestration

Create Agents across multiple projects:

```yaml
agents:
  - name: "project_a_dev"
    type: "code_agent"
    working_dir: "/home/user/projects/project_a"
    llm_group: "haijun"

  - name: "project_b_dev"
    type: "code_agent"
    working_dir: "/home/user/projects/project_b"
    llm_group: "gpt4"

  - name: "shared_lib_dev"
    type: "code_agent"
    working_dir: "/home/user/projects/shared_lib"
    worktree: true
```

## Best Practices

### 1. Naming conventions

- Use descriptive names, such as `frontend_dev`, `api_designer`
- Avoid meaningless names, such as `agent_1`, `test`

### 2. Working directory

- Use absolute paths to avoid path ambiguity
- Ensure the directory exists and is accessible

### 3. Task description

- Task descriptions should be specific and executable
- Include clear goals and scope
- Avoid overly general descriptions

### 4. Interaction mode first

- **Must**: use interaction mode by default (do not set `no_interaction_mode` or set it to `false`)
- Interaction mode allows manual confirmation and adjustment of Agent behavior, improving controllability
- Enable `no_interaction_mode: true` only when unattended operation is explicitly needed

### 5. Model group selection

- Choose an appropriate model group according to the task complexity
- Simple tasks can use the default model group
- Complex tasks are recommended to use an advanced model group

## Checklist

After creating the orchestration file, be sure to confirm:

- [ ] The file uses YAML format
- [ ] The file contains an `agents` list
- [ ] Each Agent configuration contains the `working_dir` field
- [ ] Interaction mode is used by default (no `no_interaction_mode` is set or it is set to `false`)
- [ ] If an Agent uses `no_interaction_mode: true`, confirm it contains the `task` field
- [ ] All paths use the correct format
- [ ] The YAML syntax is correct (no indentation errors)
- [ ] If creating across nodes is needed, confirm the node corresponding to `node_id` is online
- [ ] The `owner_id` field is not used (ownership is determined by the executor)

## Usage

1. Create an orchestration file (e.g. `orchestration.yaml`)
2. Enter `@OrganizeAgents` in HaijunBot
3. Enter the orchestration file path as prompted
4. Wait for the batch creation to complete

## Related Resources

- OrganizeAgents command: a built-in command for batch-creating Agents
- gateway_manager tool: the underlying implementation, supporting the create_agent operation
