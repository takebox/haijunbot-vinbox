# -*- coding: utf-8 -*-
import os
from pathlib import Path
from typing import Any, Dict

from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.output import PrettyOutput


class meta_agent:
    """Meta-Agent tool: responsible for bootstrapping and evolving the HaijunBot tool ecosystem.

    This tool itself uses CodeAgent/Agent to analyze requirements, generate/improve the code of other tools, and automatically complete registration and integration;
    it is a "tool that can create and transform tools", embodying HaijunBot's self-bootstrapping and self-evolution capabilities.
    """

    name = "meta_agent"
    description = (
        "Meta-Agent tool: writes or improves HaijunBot tools on its own according to natural language requirements and completes registration. "
        "Capabilities: 1) Call CodeAgent to generate complete, usable new tool code (including parameter definitions, error handling, and best-practice templates); "
        "2) After generation, automatically write to the data/tools directory and register with ToolRegistry; "
        "3) Support new tools calling the existing Agent (general task orchestration, task_list_manager) and CodeAgent (code changes, build verification, lint, review, etc.); "
        "4) Support repeatedly calling meta_agent to make bootstrapping-style improvements to existing tools (self-analysis and evolution). "
        "Usage: pass tool_name (the tool name/file name) and function_description (a clear description of the target functionality); the return value contains the generation status and the absolute path of the new tool file."
    )

    parameters = {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "description": "Name of the tool to generate or improve; used both as the file name (<name>.py) and the tool class name",
            },
            "function_description": {
                "type": "string",
                "description": "Description of the tool's target functionality and usage scenarios: should be as specific as possible, including the meaning of input parameters, expected output, constraints (e.g., read-only/allow writing files), and whether orchestrating Agent/CodeAgent is needed, etc.",
            },
        },
        "required": ["tool_name", "function_description"],
    }

    @staticmethod
    def check() -> bool:
        """Check whether the tool is available"""
        # Check whether the data directory exists
        data_dir = get_data_dir()
        tools_dir = Path(data_dir) / "tools"

        # If the tools directory does not exist, try to create it
        if not tools_dir.exists():
            try:
                tools_dir.mkdir(parents=True, exist_ok=True)
                return True
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Unable to create the tools directory {tools_dir}: {e}")
                return False

        return True

    def _build_enhanced_prompt(
        self,
        tool_name: str,
        function_description: str,
        haijunbot_dir: Path,
        tools_dir: Path,
    ) -> str:
        """Build an enhanced prompt containing key reference files"""

        key_files = [
            haijunbot_dir / "haijunbot_tools" / "registry.py",
            haijunbot_dir / "haijunbot_tools" / "base.py",
            haijunbot_dir / "haijunbot_agent" / "__init__.py",
            haijunbot_dir / "haijunbot_code_agent" / "code_agent.py",
            haijunbot_dir / "haijunbot_utils" / "config.py",
            haijunbot_dir / "haijunbot_utils" / "output.py",
        ]

        # Convert to absolute paths
        key_files_absolute = [f.resolve() for f in key_files]
        base_tool_file = (haijunbot_dir / "haijunbot_tools" / "base.py").resolve()
        agent_init_file = (haijunbot_dir / "haijunbot_agent" / "__init__.py").resolve()
        code_agent_file = (haijunbot_dir / "haijunbot_code_agent" / "code_agent.py").resolve()
        code_agent_prompts_file = (
            haijunbot_dir / "haijunbot_code_agent" / "code_agent_prompts.py"
        ).resolve()

        files_info = "\n".join([f"- {f}" for f in key_files_absolute])

        return f"""Please generate a new HaijunBot tool based on my requirements.

Tool requirements:
- Tool name: {tool_name}
- Function description: {function_description}
- Generated file name: {tool_name}.py
- File save path: {tools_dir.resolve() / f"{tool_name}.py"}
- Must inherit from the Tool base class (reference: {base_tool_file})
- Must implement the name, description, parameters, and execute methods

Key reference files:
{files_info}

Other files may also be referenced as appropriate.

### Key usage of Agent / CodeAgent (only core points listed; for detailed rules please read the absolute paths of the source code)
- Agent (general-purpose Agent):
  - Responsibility: general task orchestration and conversational workflow, strictly following ARCHER (ANALYZE → RULE → COLLECT → HYPOTHESIZE → EXECUTE → REVIEW).
  - **ARCHER workflow description**:
    - **ANALYZE**: understand my requirements, clarify the task goal, identify constraints and boundaries, and **proactively identify the rule support that may be needed**.
    - **RULE** (load rules): load relevant professional rules and best practices to guide subsequent stages.
    - **COLLECT** (gather information): gather necessary information read-only, locate relevant files and context, and prepare for solution design.
    - **HYPOTHESIZE** (formulate a plan): based on the gathered information, design the optimal technical solution and formulate an executable plan. **Important: after this stage is complete, it must be confirmed by me before entering the EXECUTE stage**.
    - **EXECUTE**: implement precisely according to the plan, ensuring changes are correct and reversible.
    - **REVIEW** (retrospective): thoroughly reflect on the work results: review code quality (syntax/functionality/style), verify whether the functionality is complete, check whether all affected code has been considered, confirm whether there are accompanying changes (such as documentation, tests, configuration, etc.), assess the scope of impact and potential risks, and ensure quality.
  - **Key characteristics**:
    - Stages can interleave and fall back, forming an iterative closed loop
    - Proactively consider rules during the ANALYZE stage to avoid going off track
    - Advance strictly in process order; skipping steps or reordering is forbidden (unless I explicitly request it and the risks are explained)
  - Initialization points: `Agent(system_prompt=..., name=..., use_tools=[...], non_interactive=...)`; most default behaviors (memory, methodology, tool filtering, etc.) are defined in `{agent_init_file}`.
  - Typical usage: start the complete closed loop via `agent.run(user_input)`; internally it automatically handles the system prompt, tool calls, task_list_manager scheduling, and summarization; summarization and return-value behavior are controlled by `summary_prompt` and `need_summary`.
  - For more details (parameter meanings, summarization and return-value strategy, event callbacks, etc.) please read directly: `{agent_init_file}`.
- CodeAgent (code Agent):
  - Responsibility: code analysis and modification, git operations, build verification, lint, diff display, and automatic review.
  - Initialization points: `CodeAgent(need_summary=..., non_interactive=True/False, append_tools=..., rule_names=...)`; the workflow and prompts are defined in `{code_agent_file}` and `{code_agent_prompts_file}`.
  - Typical usage: drive the code modification flow via `agent.run(requirement, prefix=..., suffix=...)`; internally it automatically handles context analysis, patch generation, git commits, build checks, lint, and review; the return value of `run` is usually "a result summary string or None".
  - For more details (review flow, task summary, return-value semantics, etc.) please read directly: `{code_agent_file}` and `{code_agent_prompts_file}`.

In the new tools generated by this tool, it is recommended to:
- Use Agent for the high-level requirement analysis, the ARCHER workflow, and multi-step task orchestration;
- Use CodeAgent for concrete code-level modification, refactoring, and verification.
The generated tool must have the following characteristics:
1. Bootstrapping capability: able to call the Agent and CodeAgent in the existing package
2. Self-evolution: able to leverage the existing CodeAgent functionality
3. Automatic registration: able to register with the tool system immediately after generation
4. Complete functionality: contains a check() static method and an execute() instance method

**Using Agent/CodeAgent is strongly recommended**:
- In the execute() method, CodeAgent should be preferred for handling complex code tasks
- Agent can be used for requirement analysis and task decomposition
- Example code pattern:
  ```python
  from haijunbot.haijunbot_agent import Agent
  from haijunbot.haijunbot_code_agent.code_agent import CodeAgent
  
  # Use CodeAgent to handle code-related tasks
  agent = CodeAgent()
  agent.run("Your code generation requirement")
  
  # Or use a regular Agent to handle analysis tasks
  agent = Agent()
  agent.run("Your analysis requirement")
  ```

Tool template requirements:
```python
class {tool_name}:
    name = "{tool_name}"
    description = "{function_description}"
    
    parameters = {{
        "type": "object",
        "properties": {{
            # Define parameters according to the functionality
        }},
        "required": ["required_param1", "required_param2"]
    }}
    
    @staticmethod
    def check() -> bool:
        # Check whether the tool is available
        return True
        
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Implement the tool functionality
        # You can call:
        # - from haijunbot.haijunbot_agent import Agent
        # - from haijunbot.haijunbot_code_agent.code_agent import CodeAgent
        # - Other haijunbot modules
        
        # Bootstrapping example: use meta_agent to improve itself
        # from haijunbot.haijunbot_tools.meta_agent import meta_agent
        # 
        # # Generate an improved version
        # improver = meta_agent()
        # result = improver.execute({{
        #     "tool_name": "{tool_name}_improved",
        #     "function_description": "An improved version of {tool_name}, optimized based on usage feedback"
        # }})
        
        # Use CodeAgent for self-analysis and improvement
        # agent = CodeAgent()
        # analysis = agent.run("Analyze the current tool's performance bottlenecks and propose improvements")
        
        pass
```

Please generate complete, ready-to-use Python code; after generation there is no need for testing or verification."""

    def _register_new_tool(
        self, agent: Any, tool_name: str, tool_file_path: str
    ) -> bool:
        """Register the newly generated tool"""
        try:
            tool_registry = agent.get_tool_registry()
            result = tool_registry.register_tool_by_file(tool_file_path)
            if not result:
                # Registration failed; clean up the generated file
                try:
                    from pathlib import Path

                    Path(tool_file_path).unlink(missing_ok=True)
                    PrettyOutput.auto_print(
                        f"ℹ️ Cleaned up the tool file that failed to register: {tool_file_path}"
                    )
                except Exception as cleanup_error:
                    PrettyOutput.auto_print(f"⚠️ Failed to clean up file: {cleanup_error}")
            return bool(result)
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to register tool: {e}")
            # Also try to clean up the file when registration raises an exception
            try:
                from pathlib import Path

                Path(tool_file_path).unlink(missing_ok=True)
                PrettyOutput.auto_print(f"ℹ️ Cleaned up the tool file whose registration raised an exception: {tool_file_path}")
            except Exception as cleanup_error:
                PrettyOutput.auto_print(f"⚠️ Failed to clean up file: {cleanup_error}")
            return False

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a new tool and register it with the current tool registry

        Parameters:
            args: a dict containing the tool name and tool code

        Returns:
            Dict: a dict containing the generation result
        """
        tool_file_path = None
        curr_dir = os.getcwd()
        try:
            data_dir = get_data_dir()
            tools_dir = Path(data_dir) / "tools"
            tools_dir.mkdir(parents=True, exist_ok=True)
            os.chdir(tools_dir)

            # Get the tool information from the arguments
            tool_name = args["tool_name"]
            function_description = args["function_description"]

            # Validate the tool name
            if not tool_name.isidentifier():
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Tool name '{tool_name}' is not a valid Python identifier",
                }

            haijunbot_dir = Path(__file__).parent.parent.resolve()

            # Build an enhanced prompt containing key reference files
            enhanced_prompt = self._build_enhanced_prompt(
                tool_name, function_description, haijunbot_dir, tools_dir
            )

            # Use CodeAgent to generate the tool code
            from haijunbot.haijunbot_code_agent.code_agent import CodeAgent

            agent = CodeAgent(
                need_summary=True,
                non_interactive=True,
            )

            try:
                # Run CodeAgent and generate the tool code
                # CodeAgent automatically handles code generation and file writing
                agent.auto_complete = True
                agent.run(enhanced_prompt)

                # Look for the generated tool file
                tool_file_path = tools_dir / f"{tool_name}.py"
                if tool_file_path.exists():
                    # Automatically register the new tool
                    self._register_new_tool(agent, tool_name, str(tool_file_path))

                    return {
                        "success": True,
                        "stdout": f"Successfully generated and registered tool: {tool_name}\nFile path: {tool_file_path}",
                        "stderr": "",
                    }
                else:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "CodeAgent failed to generate the tool file",
                    }

            except Exception as e:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Error occurred while generating the tool: {str(e)}",
                }

        finally:
            if curr_dir:
                os.chdir(curr_dir)
