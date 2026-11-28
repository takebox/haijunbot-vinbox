# -*- coding: utf-8 -*-
"""Unified orchestration file loader (layer 1: structure generation).

Dispatch by file suffix, parsing both orchestration sources (YAML and Python DSL) into a **homogeneous structure**:

    {"agents": [...], "flow": [...], "spec": str(optional), "default_on_error": str(optional)}

The two suffixes correspond to two orchestration intents:

- `.yaml` / `.yml`: **organization orchestration** - declares a set of Agents (agents), used for batch creation.
- `.flow`: **flow orchestration** - uses the Python DSL (orchestration_dsl) to declare the DAG structure
  (agents + flow); the script content is Python code, taking the top-level variable `pipeline` (a Pipeline instance)
  to export its structure. The script is expected to **only declare structure and produce no side effects** (trusted environment).

Design approach (see docs/design/orchestration-python-dsl.md for details):
- **Single parsing entry point**: parsing in all three places - pipeline_runner / app.py / node_manager.py - goes through this module,
  avoiding drift from multiple duplicate implementations.
- **Homogeneous with YAML**: the return value can be consumed directly by pipeline_runner's `_build_dag`,
  so the execution engine, scheduling, events, frontend visualization, and cross-node distribution all remain unchanged.
"""

from pathlib import Path
from typing import Any
from typing import Dict
from typing import Union

import yaml

# Supported orchestration file suffixes
_YAML_SUFFIXES = (".yaml", ".yml")
_FLOW_SUFFIXES = (".flow",)

# Top-level variable name expected by flow orchestration scripts (a Pipeline instance)
_PIPELINE_VAR = "pipeline"


def load_orchestration(path: Union[str, Path]) -> Dict[str, Any]:
    """Load an orchestration file by suffix, returning a dict homogeneous with the YAML parsing result.

    Args:
        path: Orchestration file path (str or Path).

    Returns:
        {"agents": list, "flow": list, "spec": str(optional), "default_on_error": str(optional)}

    Raises:
        ValueError: The file does not exist, the suffix is unsupported, YAML parsing fails, the Python script fails to execute,
            or the script is missing the `pipeline` variable or it has the wrong type. The caller uniformly converts this into an error return.
    """
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise ValueError(f"Orchestration file does not exist: {path}")

    suffix = file_path.suffix.lower()
    if suffix in _YAML_SUFFIXES:
        return _load_yaml(file_path)
    if suffix in _FLOW_SUFFIXES:
        return _load_flow(file_path)
    raise ValueError(
        f"Unsupported orchestration file type '{suffix}' (only .yaml/.yml/.flow are supported): {path}"
    )


def _load_yaml(file_path: Path) -> Dict[str, Any]:
    """Load a YAML orchestration file (consistent with existing behavior)."""
    try:
        content = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse orchestration YAML: {e}") from e
    except OSError as e:
        raise ValueError(f"Failed to read orchestration file: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("Orchestration file content must be a mapping")
    return data


def _load_flow(file_path: Path) -> Dict[str, Any]:
    """Execute a flow orchestration script (.flow), taking the top-level `pipeline` variable to export the structure.

    In a trusted environment the script is executed directly (the script is expected to only declare structure without side effects).
    It executes in an isolated namespace, and exceptions are uniformly converted into clear ValueErrors.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Failed to read orchestration script: {e}") from e

    namespace: Dict[str, Any] = {
        "__file__": str(file_path),
        "__name__": "__orchestration__",
    }
    try:
        code = compile(source, str(file_path), "exec")
        exec(code, namespace)  # pylint: disable=exec-used
    except Exception as e:  # pylint: disable=broad-except
        raise ValueError(f"Orchestration script execution failed: {type(e).__name__}: {e}") from e

    pipeline = namespace.get(_PIPELINE_VAR)
    if pipeline is None:
        raise ValueError(
            f"Orchestration script is missing the top-level variable '{_PIPELINE_VAR}' (must be a Pipeline instance)"
        )
    # Prefer to_dict() (Pipeline's export contract); otherwise fall back to reading attributes.
    to_dict = getattr(pipeline, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
    else:
        data = {
            "agents": getattr(pipeline, "agents", None),
            "flow": getattr(pipeline, "flow", None),
            "spec": getattr(pipeline, "spec_text", ""),
            "default_on_error": getattr(pipeline, "default_on_error_value", ""),
        }
    if not isinstance(data, dict):
        raise ValueError(
            f"The '{_PIPELINE_VAR}' export result of the orchestration script must be a dict, but is actually {type(data).__name__}"
        )
    return data
