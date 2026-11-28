# -*- coding: utf-8 -*-
"""Prompt-building logic for the LLM module planning Agent."""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List

from haijunbot.haijunbot_c2rust.llm_module_agent_utils import resolve_created_dir
from haijunbot.haijunbot_utils.jsonnet_compat import loads as json_loads
from haijunbot.haijunbot_utils.tag import ot


class PromptBuilder:
    """Prompt builder."""

    def __init__(
        self,
        project_root: Path,
        loader: Any,  # GraphLoader
        crate_name_func: Callable[[], str],
        has_original_main_func: Callable[[], bool],
        append_additional_notes_func: Callable[[str], str],
    ):
        self.project_root = project_root
        self.loader = loader
        self.crate_name_func = crate_name_func
        self.has_original_main_func = has_original_main_func
        self.append_additional_notes = append_additional_notes_func

    def build_roots_context_from_order(self) -> List[Dict[str, Any]]:
        """
        Based on translation_order.jsonl, generate the context for planning:
        - Use each step's roots tag as the grouping key (usually one root tag per step)
        - The function list comes from the 'name' field of the symbols in each step's items, aggregated and deduplicated by root
        - Skip residual steps without a roots tag (keep only context with an explicit root)
        - If no root group is collected in the end, fall back to a single 'project' group containing the set of function names of all items
        """
        order_path = (
            self.project_root / ".haijunbot" / "c2rust" / "translation_order.jsonl"
        )
        if not order_path.exists():
            raise FileNotFoundError(f"translation_order.jsonl not found: {order_path}")

        def _deduplicate_names(names: List[str]) -> List[str]:
            """Deduplicate and sort the function name list"""
            try:
                return sorted(list(dict.fromkeys(names)))
            except (TypeError, ValueError):
                return sorted(list(set(names)))

        def _extract_names_from_items(items: List[Any]) -> List[str]:
            """Extract function names from items"""
            names: List[str] = []
            for it in items:
                if isinstance(it, dict):
                    nm = it.get("name") or ""
                    if isinstance(nm, str) and nm.strip():
                        names.append(str(nm).strip())
            return names

        groups: Dict[str, List[str]] = {}
        all_names_fallback: List[str] = []  # For fallback scenarios

        try:
            with order_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json_loads(line)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_c2rust.llm_module_agent_prompts",
                            function="_extract_names_from_items",
                        )
                        continue

                    roots = obj.get("roots") or []
                    items = obj.get("items") or []
                    if not isinstance(items, list) or not items:
                        continue

                    # Extract all function names (for fallback scenarios)
                    item_names = _extract_names_from_items(items)
                    all_names_fallback.extend(item_names)

                    # Extract the root tag
                    root_labels = [
                        str(r).strip()
                        for r in roots
                        if isinstance(r, str) and str(r).strip()
                    ]
                    if not root_labels:
                        continue

                    # Deduplicate step_names
                    step_names = _deduplicate_names(item_names)
                    if not step_names:
                        continue

                    # Aggregate by root
                    for r in root_labels:
                        groups.setdefault(r, []).extend(step_names)
        except (OSError, IOError) as e:
            raise RuntimeError(f"Error occurred while reading translation_order.jsonl: {e}") from e

        contexts: List[Dict[str, Any]] = []
        for root_label, names in groups.items():
            names = _deduplicate_names(names)
            contexts.append({"root_function": root_label, "functions": sorted(names)})

        # Fallback: if there is no root group, use all items as a single 'project' group
        if not contexts:
            all_names = _deduplicate_names(all_names_fallback)
            if all_names:
                contexts.append(
                    {"root_function": "project", "functions": sorted(all_names)}
                )

        return contexts

    def build_user_prompt(self, roots_context: List[Dict[str, Any]]) -> str:
        """
        Main dialogue stage: pass in the context without output requirements, only to let the model obtain information and trigger entering the summary stage.
        Ask the model to output only {ot('!!!COMPLETE!!!')} to enter the summary stage. Do not output anything else; the task summary will be requested in a later interaction.
        """
        crate_name = self.crate_name_func()
        has_main = self.has_original_main_func()
        created_dir = resolve_created_dir(self.project_root)
        context_json = json.dumps(
            {
                "meta": {
                    "crate_name": crate_name,
                    "main_present": has_main,
                    "crate_dir": str(created_dir),
                },
                "roots": roots_context,
            },
            ensure_ascii=False,
            indent=2,
        )
        prompt = f"""
Below is the context (JSON) of the project call graph; please read through it first and do not output any planning or JSON content:
<context>
{context_json}
</context>

If you are ready and want to enter the summary stage to complete the output, output only: {ot("!!!COMPLETE!!!")}, without anything else. The task summary will be given when asked later.
""".strip()
        return self.append_additional_notes(prompt)

    def build_system_prompt(self) -> str:
        """
        System prompt: describe the principles for crate planning based on dependencies (not involving the dialogue flow or output format)
        """
        crate_name = self.crate_name_func()
        prompt = (
            "You are a senior Rust architect. Task: based on the given function-level call relations (a table containing only root_function and its reachable function names), plan a suitable Rust crate structure for this project.\n"
            "\n"
            "Planning principles:\n"
            "- Root-oriented: partition top-level modules by each root_function to form clear entry points and responsibility scopes.\n"
            "- Cohesion first: split submodules by call cohesion so that strongly related functions are in the same submodule, reducing cross-module coupling.\n"
            "- Remove cycles and layer: try to eliminate circular dependencies; follow the top-down call direction to keep the dependency direction stable and the layers clear.\n"
            "- Extract shared code: extract content shared by multiple roots into a common/ or shared/ module to avoid duplication and cross dependencies.\n"
            "- Isolate boundaries: put boundary capabilities such as platform/IO/peripherals into separate adapter/ or ffi/ modules (if any).\n"
            "- Naming conventions: use lowercase_with_underscores for directories/files; keep module names concise and readable, avoiding special characters and overly verbose names.\n"
            "- Evolvable: use moderate module granularity and reserve extension points to facilitate later refactoring and gradual replacement of legacy code.\n"
            "- Module organization: each directory's mod.rs declares its subdirectories and .rs submodules; the top-level lib.rs aggregates and exports the main modules and public capabilities.\n"
            "- Entry strategy (must be followed; bin serves only as the entry point and functionality should be implemented in lib as much as possible):\n"
            "  * If the original project contains a main function: do not generate src/main.rs; use src/bin/"
            + crate_name
            + ".rs as the sole executable entry point, keeping only the minimal entry logic (calling the library layer); shared code goes in src/lib.rs;\n"
            "  * If the original project does not contain a main function: do not generate any binary entry point (do not create src/main.rs or src/bin/), and only generate src/lib.rs;\n"
            "  * Multiple executables: use src/bin/<name>.rs only when there really are multiple clear entry points; each bin file serves only as an entry point and should call the library as much as possible;\n"
            "  * Binary naming: <name> uses lowercase_with_underscores, reflects the entry point's meaning, and avoids the same name as a module/file.\n"
        )
        return self.append_additional_notes(prompt)

    def build_summary_prompt(self, roots_context: List[Dict[str, Any]]) -> str:
        """
        Summary stage: output only the JSON of the directory structure.
        Requirements:
        - Output only one <PROJECT> block
        - Between <PROJECT> and </PROJECT> there must be a parseable JSON array
        - A directory is represented as an object, with the key being 'directory_name/' and the value being an array of child items; a file is a string
        - There must be no characters outside the block (including blank lines, comments, Markdown, explanatory text, schema, etc.)
        - Do not output the crate name or other extraneous fields
        """
        has_main = self.has_original_main_func()
        crate_name = self.crate_name_func()
        guidance_common = """
Output specification:
- Output only one <PROJECT> block
- There must be no characters outside the block (including blank lines, comments, Markdown, etc.)
- The block must contain a JSON array:
  - A directory entry is represented as an object, with the key being '<name>/' and the value being an array of child items
  - A file is a string item (for example "lib.rs")
- Do not create placeholder files unrelated to the entry point
""".strip()
        if has_main:
            entry_rule = f"""
Entry conventions (because the original project has main):
- Must include src/lib.rs;
- Must not include src/main.rs;
- Must include src/bin/{crate_name}.rs as the sole executable entry point (serving only as an entry point and calling the library logic);
- If there are not multiple clearly separated entry points, do not create additional bin files.
Positive example (JSON format):
<PROJECT>
[
  "Cargo.toml",
  {{
    "src/": [
      "lib.rs",
      {{
        "bin/": [
          "{crate_name}.rs"
        ]
      }}
    ]
  }}
]
</PROJECT>
""".strip()
        else:
            entry_rule = """
Entry conventions (because the original project has no main):
- Must include src/lib.rs;
- Must not include src/main.rs;
- Must not include a src/bin/ directory.
Positive example (JSON format):
<PROJECT>
[
  "Cargo.toml",
  {
    "src/": [
      "lib.rs"
    ]
  }
]
</PROJECT>
""".strip()
        guidance = f"{guidance_common}\n{entry_rule}"
        prompt = f"""
Based on the <context> already provided in the previous dialogue, complete the summary output (the JSON of the project directory structure). Strictly follow the requirements below:

{guidance}

Your output must contain only the following single block (replace the block content with the project's actual directory structure):
<PROJECT>
[...]
</PROJECT>
""".strip()
        return self.append_additional_notes(prompt)

    def build_retry_summary_prompt(
        self, base_summary_prompt: str, error_reason: str
    ) -> str:
        """
        Based on the original summary_prompt, append error feedback and require a strict retry.
        """
        feedback = (
            "\n\n[Format validation failed; a retry is required]\n"
            f"- Failure reason: {error_reason}\n"
            '- Strictly follow the above "Output specification" and "Entry conventions" and output again;\n'
            "- Output only one <PROJECT> block, with a parseable JSON array inside it; there must be no characters outside the block.\n"
        )
        return base_summary_prompt + feedback
