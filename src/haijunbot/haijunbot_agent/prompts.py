# -*- coding: utf-8 -*-

DEFAULT_SUMMARY_PROMPT = """<report>
Write a concise task summary (in English, plainly narrated; no classical style and no piled-up formatting), so that whoever takes over can continue without digging through the history. Section and bullet it as needed; keep the language concise.

1. **Goal and progress**: the overall goal and which step has been reached so far; if the goal changed midway, point out the change and the reason; distinguish "completed / in progress / to do", do not conflate them.
2. **Verified results and changes**: list the key files and changes; anything marked "completed" must be able to provide verification evidence—for code development, be sure to state whether compilation/build passed, the test results, and whether it was actually run and verified. If you cannot, you are not allowed to mark it "completed".
3. **Errors, debugging, and known issues**: still-existing errors (including key error messages/stack highlights), disproven approaches and the reasons for their failure.
4. **Unfinished work and next steps**: outstanding items and to-dos, noting dependencies, risks, and suggested priorities.
5. **My constraints and preferences**: code conventions, user preferences, and prohibited areas that affect subsequent execution.

Requirements: state only facts that actually happened and were verified; do not fabricate or speculate; prefer few and accurate over many and vague.
</report>"""


SUMMARY_REQUEST_PROMPT = """<summary_request>
Compress the previous conversation into a condensed context that can be used to "directly continue working" (in English, plainly narrated; no classical style and no piled-up formatting). There is no need to recount the process, but preserve the information needed to continue deciding and executing. Bullet it as needed.

1. **Goal and progress**: the current overall/phase goal and the state reached, clearly distinguishing "verified complete / in progress / to do"; if the goal changed midway, take the latest as authoritative and point out the change.
2. **Verified key facts and changes**: file paths/functions/interfaces that were changed, the conclusions of compilation and tests that passed, key technical decisions and their rationale, reproducible information worth remembering (key errors/stacks/parameters).
3. **Key user information**: distill the key information from user input; there is no need to restate it item by item verbatim. Focus on keeping content that affects subsequent execution—constraints, preferences, corrections, and negative feedback added or modified midway, as well as the key points of requirement changes—this is the information most easily lost after compression and most likely to cause deviation.
4. **Current work**: what was being done right before compression—the file/function being modified, the hypothesis being verified, the command just issued and its result, and what is planned next.
5. **Unresolved problems**: still-existing errors and blockers, methods tried but failed and the reasons for failure, and missing tests/documentation/edge cases.
6. **Next steps and constraints**: to-dos and suggested priorities, dependencies and risks, user preferences and prohibited areas.

Requirements: be faithful to the original conversation; add no facts and make no guesses; for code development content, "completed" must correspond to verification evidence (compilation/test/run); if not, do not mark it complete; keep the language concise, preferring to keep key details and drop pleasantries and process recaps.

Now output the summary body directly, without calling any tools.
</summary_request>
"""


def get_task_analysis_prompt(
    has_memory_tool: bool = False, has_generate_new_tool: bool = False
) -> str:
    """Return the task analysis prompt according to the configuration

    Args:
        has_memory_tool: Whether the memory tool is available (tool availability)
        has_generate_new_tool: Whether the meta_agent tool is available (formerly generate_new_tool, a self-bootstrapping tool generator)
    """
    # Step two: the memory saving part
    if not has_memory_tool:
        # If there is no memory tool, memory cannot be saved
        memory_step = """Step two: record information worth saving
1. Identify the key information and knowledge points in the task
2. Assess whether there is project long-term memory or global long-term memory worth saving
3. Note: the current environment does not support the memory tool, so memory cannot be saved. Just state the key information identified."""
    else:
        # There is a memory tool
        memory_step = """Step two: record information worth saving
1. Identify the key information and knowledge points in the task
2. Assess whether there is project long-term memory or global long-term memory worth saving
3. If valuable, use the memory tool (action=save) to save the valuable information:
   - project_long_term: save long-term information related to the current project (such as project configuration, architecture decisions, development conventions, etc.)
   - global_long_term: save general information, user preferences, knowledge, or methods (such as technical knowledge, best practices, user habits, etc.)"""

    # Step one: the rule system analysis part
    rule_analysis_step = """Step one: analyze the rule system
1. Check whether the current project's global or project rules (the .haijunbot/rules/ directory, excluding the builtin/rules/ built-in rules) have anything that needs improvement
2. Focus on rule coverage in the following areas:
   - Project-level conventions (such as code style, module design conventions)
   - CI/CD-related rules
   - Documentation conventions
   - Performance benchmark rules
   - Security check process conventions
   - Other project-specific conventions or processes
3. If a rule is found missing or in need of improvement:
   - Use the load_rule tool to load builtin:rule to view the existing rule system
   - Assess whether the missing rule needs to be created
   - If a new rule is needed, explain it in the subsequent steps
4. If the existing rules are already complete, just state so"""

    # Step three: the tool/rule analysis part
    if has_generate_new_tool:
        solution_step = """Step three: analyze the task solution
1. Check whether existing tools or rules can already complete the task; if so, just state it, no need to generate new content
2. If existing tools/rules are insufficient, assess whether the current task can be solved by writing a new tool to automate it
3. If it can be solved with a tool, use the meta_agent tool to create or improve a tool:
   - Use the meta_agent tool, passing the tool_name and function_description parameters
   - The tool will use CodeAgent/Agent to intelligently analyze the requirement and automatically generate or improve complete tool code with self-bootstrapping and self-evolving capabilities
   - The generated/improved tool will be automatically integrated into the HaijunBot ecosystem, supporting orchestration of Agent and CodeAgent to handle complex tasks
4. If none of the above is feasible, give a detailed reason"""
    else:
        solution_step = """Step three: analyze the task solution
1. Check whether existing tools or rules can already complete the task; if so, just state it, no need to generate new content
2. If existing tools/rules are insufficient, assess whether the current task can be solved by writing a new tool to automate it
3. If it can be solved with a tool, give priority to using the meta_agent tool to create/improve a new tool (if the environment supports it); otherwise provide the tool code manually
4. If none of the above is feasible, give a detailed reason"""

    # The output requirements part
    if has_generate_new_tool:
        output_requirements = """<output_requirements>
Based on the analysis result, output one of the following two cases:
1. If existing tools/rules can solve it, directly output the statement:
Existing tools/rules can solve this problem; no need to create new content.
Available tools/rules: [list the tool names or rule names]
Usage: [briefly explain how to use it]
2. Create a tool (if a new tool is needed):
```json
{
  "want": "Create a new tool to solve the XXX problem",
  "name": "meta_agent",
  "arguments": {
    "tool_name": "tool name",
    "function_description": "A detailed functional description of the tool, explaining the specific problem it solves and the expected behavior"
  }
}
```

If neither of the above two cases applies, directly output the rationale analysis without using the tool-call format.
</output_requirements>"""
    else:
        output_requirements = """<output_requirements>
Based on the analysis result, output one of the following two cases:
1. If existing tools/rules can solve it, directly output the statement:
Existing tools/rules can solve this problem; no need to create new content.
Available tools/rules: [list the tool names or rule names]
Usage: [briefly explain how to use it]
2. Create a tool (if a new tool is needed):
Note: if the environment supports it, use the meta_agent tool to create/improve a new tool; if not, provide the complete tool code and description, and I will manually create the tool file.

If neither of the above two cases applies, directly output the rationale analysis without using the tool-call format.
</output_requirements>"""

    return f"""<task_analysis>
<request>
The current task has ended. Please analyze this task according to the following steps:

{rule_analysis_step}

{memory_step}

{solution_step}

Please take the corresponding action based on the analysis result.

Important note: only one operation can be performed at a time!
- If there is memory to save, you may call the memory tool (action=save) once to batch-save multiple memories
- After saving all memories, proceed to create or describe tools/rules
- Do not call multiple tools in a single response (such as saving memory and creating a tool at the same time)
</request>
<evaluation_criteria>

Existing resource assessment: check whether existing tools/rules/combinations can solve the problem
Tool assessment: generality, automation, reliability, simplicity
<tool_requirements>
Tool code requirements:
1. The tool class name matches the tool name, includes name, description, and parameters attributes, and implements the execute method
2. Parameter definitions follow JSON Schema; tool calls use the Jsonnet format (trailing commas supported)
3. Use print to show the execution process and return a {{success, stdout, stderr}} structured result
4. Handle exceptions properly and clean up resources on failure. If a large model needs to be called, create an independent instance to avoid interfering with the main flow
</tool_requirements>
{output_requirements}
</task_analysis>"""


# Kept for backward compatibility (uses default parameters, assuming the memory tool is present)
TASK_ANALYSIS_PROMPT = get_task_analysis_prompt(has_memory_tool=True)
