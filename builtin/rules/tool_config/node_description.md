---
name: node_description
description: Triggered when node description information needs to be set or updated. Triggered whenever the user mentions "node description", "set node information", "update node description". Not triggered: only querying node status; only viewing the node list; discussing node concepts without description configuration.
---

# Node Description Generation Rules

## Rule Introduction

This rule is used to write the node description information provided by the user into the `~/.haijunbot/gateway/node_description.md` file. This file is automatically read by the system information module and reported to the Master node in the Child-Master heartbeat, where it is returned by the `list_nodes` operation of the `gateway_manager` tool.

## Principles You Must Follow

### 1. Source of the Description Content

- **Must**: The description content is provided by the user and must not be fabricated
- **Must**: The user may provide the description in any format; this rule is responsible for writing it to the file
- **Forbidden**: Generate a default description when the user has not provided content

### 2. File Path

- **Must**: The write path is `~/.haijunbot/gateway/node_description.md`
- **Must**: If the directory does not exist, create it first and then write the file
- **Forbidden**: Write to any other path

### 3. Size Limit

- **Must**: The description file must not exceed 10KB (10240 bytes)
- **Must**: If the user-provided description exceeds 10KB, truncate the content and inform the user
- **Recommended**: Keep the description within 1-2KB to remain concise and practical

### 4. File Format

- **Must**: Use Markdown format
- **Must**: Use UTF-8 encoding
- **Recommended**: Include key information such as node name, purpose, hardware configuration, and owner

## Mandatory Operations

### Operation 1: Collect the description content

1. Ask the user to provide the node description content
2. Confirm that the user-provided description content is complete

### Operation 2: Write the description file

1. Check whether the `~/.haijunbot/gateway/` directory exists and create it if it does not
2. Check the size of the description content; truncate and inform the user if it exceeds 10KB
3. Write the description content into `~/.haijunbot/gateway/node_description.md`
4. Confirm the write succeeded

### Operation 3: Verification

1. Read back the written file content and confirm it matches expectations
2. Inform the user that the description will be automatically reported to the Master node at the next heartbeat

## Suggested Description Template

```markdown
# Node Name

## Basic Information

- **Node ID**: xxx
- **Purpose**: xxx
- **Owner**: xxx

## Hardware Configuration

- **CPU**: xxx
- **Memory**: xxx GB
- **Disk**: xxx GB

## Notes

xxx
```

## Checklist

After completing the task, be sure to confirm:

- [ ] The description file has been written to `~/.haijunbot/gateway/node_description.md`
- [ ] The file size does not exceed 10KB
- [ ] The file is UTF-8 encoded
- [ ] The file content matches the user-provided description
- [ ] The user has been informed that the description will be reported automatically at the heartbeat

## Related Resources

- System information module: `{{ haijunbot_src_dir }}/haijunbot_web_gateway/system_info.py`
- Node runtime: `{{ haijunbot_src_dir }}/haijunbot_web_gateway/node_runtime.py`
