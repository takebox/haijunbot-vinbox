# Best Practices for Collaboration Modes

## When to Use

When you have multiple Agents that need to **communicate with each other and advance collaboratively** (rather than being orchestrated by a fixed DAG), or when Agents and humans need to collaborate in the same session, use HaijunBot's collaboration mechanisms:

- **Group**: A collection of Agents whose members can broadcast messages to each other.
- **Chat Room**: A real-time session in the Web interface where Agents and humans can be in the same room.
- **Private Message**: Point-to-point messaging between Agents.

These capabilities are all provided by the built-in tool **`gateway_manager`**, and are forwarded underneath through the Web Gateway.

## Prerequisites

- The Web Gateway has been started (`hwg`, default port 8000).
- Agents are connected to the gateway (created in the Web interface, or started with `--web-gateway`).
- Group / chat room operations require the Agent to have an `agent_id` (assigned by the gateway's AgentManager).

## Steps

### 1. Group collaboration

#### 1. Create a group

```text
gateway_manager(
  action="create_group",
  group_name="Refactoring Team",
  group_description="Collaboration group responsible for module refactoring"
)
```

#### 2. View groups

```text
gateway_manager(action="list_groups")
gateway_manager(action="get_group", group_id="<group_id>")
```

#### 3. Join / leave a group

The Agent joins with `join_group` (as its own `agent_id`):

```text
gateway_manager(action="join_group", group_id="<group_id>")
gateway_manager(action="leave_group", group_id="<group_id>")
```

#### 4. Send a group message

```text
gateway_manager(
  action="send_group_message",
  group_id="<group_id>",
  message="I have finished the planner stage output; the artifact is in .df/plan.md"
)
```

After sending, the tool automatically appends a "how to reply" hint at the end of the message so other members can reply easily. If the sender wants to wait for a reply, it can add `<Wait>` after the output.

### 2. Chat room collaboration (Agents and humans in the same room)

#### 1. View chat rooms and online members

```text
gateway_manager(action="chat_list_rooms")
gateway_manager(action="chat_get_online_clients")
gateway_manager(action="list_sessions")
gateway_manager(action="chat_get_room_members", room_id="<room_id>")
```

#### 2. Send a message to a chat room

```text
gateway_manager(
  action="chat_send_room_message",
  room_id="<room_id>",
  message="The current pipeline has reached the validator stage, waiting for approval"
)
```

Messages automatically get an `[Agent name]` prefix and are sent as the owner, so humans can see them in the Web interface.

### 3. Private chat between Agents

```text
gateway_manager(
  action="chat_send_private_message",
  receiver_id="<client_id or user_id>",
  message="Please send me the pass_rate from .df/report.json"
)
```

It likewise automatically adds an `[Agent name]` prefix.

### 4. Point-to-point task dispatch (without going through a group)

If you just want "a certain Agent to do one thing", use `send_to_agent` directly, and you can **synchronously wait** for it to complete:

```text
gateway_manager(
  action="send_to_agent",
  agent_id="<agent_id>",
  message="Count the number of tests under tests/",
  wait=true,
  status_file="/tmp/agent_done.json"
)
```

- `wait=true`: Polls `status_file` to determine completion (the Agent writes `{"status": "completed"|"failed"}` when finished).
- When `status_file` is not passed, it falls back to polling the `execution_status` of the Agent's `/status` (not entirely reliable; explicitly passing `status_file` is recommended).
- `wait` defaults to `false` (asynchronous fire-and-forget).

## Prompts and Feedback You Will See

- **Group messages**: On successful send it returns the group and message content, along with a hint like "to reply to this group message use ...".
- **Chat room messages**: Returns the `room_id` and the prefixed message content.
- **`send_to_agent(wait=true)`**: Blocks until the target Agent completes or times out, and returns the completion status.
- **Web interface**: Chat room messages are displayed in real time, with the `[Agent name]` prefix to distinguish speakers.

## Best Practices

### 1. Choose the right collaboration form first

| Requirement | What to Use |
| --- | --- |
| Clear stage dependencies, needing artifact passing | `pipeline_runner` orchestration (see [Multi-Agent Orchestration](Multi-Agent_Orchestration_Driving_Pipelines_with_pipeline_runner.md)) |
| Multiple Agents discussing on equal footing / broadcasting | Group (`create_group` + `send_group_message`) |
| Real-time collaboration between Agents and humans | Chat Room (`chat_send_room_message`) |
| One-to-one task assignment and waiting for a result | `send_to_agent(wait=true, status_file=...)` |

### 2. Clarify "who is the coordinator"

Group collaboration easily degenerates into "everyone speaks, no one decides". It is recommended to designate a coordinating Agent (similar to sw-controller) that aggregates each member's output and decides the next step, while other members only report their own part.

### 3. Use `status_file` as the completion signal

`send_to_agent(wait=true)` relies on the completion signal to decide when to finish. Having the target Agent write `status_file` when the task ends is much more reliable than polling `/status`.

### 4. Make messages as structured as possible

Include "stage name / artifact path / conclusion" in collaboration messages, so other Agents can reference them directly and there is less back-and-forth clarification.

### 5. Isolate sensitive information

Groups / chat rooms have broadcast semantics; do not send keys or private data into them. When you need to pass sensitive content point-to-point, use a private message.

## Notes

- Group / chat room operations require the Agent to already have an `agent_id`; when not connected to the gateway, `join_group` / `send_group_message` reports `agent_id is not available`.
- `send_group_message` requires both `group_id` and `message` to be non-empty.
- `chat_send_room_message` requires both `room_id` and `message` to be non-empty.
- The `receiver_id` of `chat_send_private_message` can be a `client_id` or a `user_id`.
- The `agent_id` of `send_to_agent` supports a single string or an array.
- The actions and parameters in the examples all come from `src/haijunbot/haijunbot_tools/gateway_manager.py` and can be used directly.

## Next Steps

- Return to [Multi-Agent Orchestration](Multi-Agent_Orchestration_Driving_Pipelines_with_pipeline_runner.md) to learn about the DAG-driven approach.
- If you run into problems, see [FAQ](../../haijunbot_book/8.FAQ.md).
