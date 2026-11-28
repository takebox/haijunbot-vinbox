---
name: self_config
description: Triggered when HaijunBot configuration files need to be modified through natural language. Triggered whenever the user mentions "configuration", "settings", "modify configuration", "HaijunBot configuration", "system settings", "change configuration", or "configuration file". Not triggered: viewing the configuration only without modifying; modifying configuration files that do not belong to HaijunBot; discussing configuration concepts without involving actual modification.
---

# HaijunBot Self-Service Configuration Rule

This rule guides the Agent on how to intelligently modify HaijunBot configuration files through natural language descriptions.

## 📋 Rule Overview

When the user provides a natural language configuration requirement, the Agent should operate according to the following workflow:

1. Read the current configuration file and schema
2. Parse the user's natural language and extract the configuration intent
3. Map the intent to specific configuration paths and values
4. Validate the configuration's legality
5. Safely modify the configuration file

## 🔄 Workflow

### Step 1: Information gathering

**Required operations**:

- Read the user configuration file: `~/.haijunbot/config.yaml`
- Read the configuration schema: `{{ haijunbot_src_dir }}/src/haijunbot/haijunbot_data/config_schema.json`
- If necessary, reference the configuration processing logic: `{{ haijunbot_src_dir }}/src/haijunbot/haijunbot_utils/config.py`

**Purpose**:

- Understand the current configuration structure
- Obtain the definitions and constraints of the configuration items
- Understand the relationships between configuration items

### Step 2: Natural language parsing

**Parsing goals**:

- Identify the configuration items the user wants to modify
- Extract the new values of the configuration
- Determine the operation type: add, modify, delete
- Identify nested structures (such as the specific model configuration inside llms)

**Parsing methods**:

- Use the semantic understanding capability of the LLM
- Identify configuration-related keywords (model, API, switch, path, etc.)
- Understand the hierarchical relationships of the configuration (e.g.: llms -> qwen3-coder-plus -> platform)

**Common configuration types**:

- Model configuration (llms, llm_groups)
- Embedding model configuration (embeddings, rag_groups)
- Feature switches (enable\_\_\*)
- Path configuration (_\_dirs, _\_repo)
- Environment variables (ENV)

### Step 3: Configuration mapping

**Mapping principles**:

- Convert the natural language description into a YAML configuration path
- Preserve the original configuration structure
- Maintain the reference relationships between configuration items

**Mapping examples**:

```yaml
user: "change the default model to qwen3-coder-plus"
mapping: llm_group: "qwen3"

user: "add a new OpenAI model configuration"
mapping: llms.
  new-model:
    platform: openai
    model: gpt-4
    ...
```

**Notes**:

- For reference-type configurations (such as normal_llm in llm_groups), ensure the referenced object exists in the corresponding location
- For nested configurations, keep the correct indentation and hierarchy
- For list configurations, ensure the format is correct

### Step 4: Configuration validation

**Validation content**:

1. **Schema validation**
   - Whether the configuration item name exists in the schema
   - Whether the configuration value type conforms to the schema definition
   - Whether the required fields are complete

2. **Reference validation**
   - Whether the references in llm_groups exist in llms
   - Whether the references in rag_groups exist in embeddings/rerankers

3. **Logical validation**
   - Whether the configuration value is within a reasonable range
   - Whether a boolean value is true/false
   - Whether the path is legal

**Handling validation failure**:

- Clearly state the reason for the validation failure
- Provide correction suggestions
- Ask the user whether to continue or modify

### Step 5: Safe modification

**Modification principles**:

- **Minimal changes**: only modify the configuration items the user explicitly requested
- **Preserve structure**: do not change the overall structure of the configuration file
- **Preserve comments**: keep the comments as much as possible if there are any

**Modification methods**:

1. Back up the original configuration (optional, but recommended)
2. Use the edit_file tool for precise modification (or edit_file_by_line to replace by line number)
3. Provide enough context to ensure a unique match
4. Show the user a summary of the changes before modifying

**Modification examples**:

```python
# modify a single configuration item
search: "llm_group: code"
replace: "llm_group: qwen3"

# modify nested configuration
search: |-
  qwen3:
    normal_llm: qwen3-coder-plus
    cheap_llm: ''
    smart_llm: ''
replace: |-
  qwen3:
    normal_llm: qwen3-coder-plus
    cheap_llm: qwen3-coder-plus
    smart_llm: qwen3-max
```

### Step 6: Result confirmation

**Confirmation content**:

- Show the configuration comparison before and after the modification
- Explain the scope of impact of the modification
- Remind the user that a restart of HaijunBot may be required for the changes to take effect

## ⚠️ Notes

### Handling sensitive configuration

**API keys**:

- If the user provides an API key, use it directly
- If the user requests modifying an existing key, confirm carefully
- Do not leak or expose sensitive information

**Environment variables**:

- The ENV configuration is written into the system environment variables
- Inform the user of the possible impact before modifying

### Configuration integrity

**Reference integrity**:

- When modifying llms, check whether there are llm_groups references
- When modifying embeddings, check whether there are rag_groups references
- If deleting a referenced configuration, update the references at the same time

**Handling default values**:

- If the user does not specify certain fields, use the default values from the schema
- Do not delete original configuration items unless the user explicitly requests it

## 🚨 Error Handling

### Common error types

1. **The configuration item does not exist**
   - Check whether the spelling is correct
   - Provide similar configuration item names
   - Guide the user to view the schema

2. **Reference errors**
   - The referenced configuration does not exist
   - The referenced configuration has been deleted
   - Check the definitions in llms, embeddings, rerankers

3. **Type errors**
   - The configuration value type does not match
   - Fix the type according to the schema definition

4. **Format errors**
   - YAML format errors
   - Indentation errors
   - Quoting or escaping errors

### Rollback mechanism

**Recommended rollback moments**:

- When the modification fails
- When configuration validation does not pass
- When the user is not satisfied

**Rollback methods**:

- Use git to restore (if version control exists)
- Restore the backup file
- Manually undo the modification

## 📝 Interaction Examples

### Example 1: Modify the default model group

**User input**:

```text
change the default model group to qwen3
```

**Agent operations**:

1. Read config.yaml and find the llm_group configuration
2. Understand the user's intent: change the value of llm_group to qwen3
3. Verify whether qwen3 exists in llm_groups
4. Modify the configuration: `llm_group: qwen3`
5. Confirm the modification succeeded

### Example 2: Add a new model configuration

**User input**:

```text
add a new OpenAI model named gpt-4-turbo with the model name gpt-4-turbo-2024-04-09
API address is https://api.openai.com/v1
```

**Agent operations**:

1. Parse the user's intent: add a new configuration under llms
2. Extract the configuration information:
   - name: gpt-4-turbo
   - platform: openai
   - model: gpt-4-turbo-2024-04-09
   - openai_api_base: https://api.openai.com/v1
3. Determine the required fields according to the schema
4. Add the new configuration under llms
5. Validate the configuration's legality
6. Apply the modification

### Example 3: Modify a feature switch

**User input**:

```text
enable the build validation feature
```

**Agent operations**:

1. Understand the user's intent: enable enable_build_validation
2. Look up the configuration item in the schema
3. Modify the configuration: `enable_build_validation: true`
4. Confirm the modification succeeded

## 💡 Best Practices

1. **Fully understand**: make sure you fully understand the user's intent before modifying

2. **Verify step by step**: validate every step, avoiding the accumulation of errors

3. **Communicate clearly**: clearly explain to the user the changes to be made

4. **Safety first**: ask the user first for uncertain operations

5. **Stay consistent**: keep the style and format of the configuration file consistent

## 🎯 Acceptance Criteria

- ✅ Successfully parse the user's natural language configuration requirement

- ✅ Map accurately to the configuration paths and values

- ✅ The configuration modification conforms to the schema definition

- ✅ The reference relationships remain complete

- ✅ Provide a clear before-and-after comparison

- ✅ The configuration file format is correct and can be loaded normally by the system
