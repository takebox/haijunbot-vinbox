# -*- coding: utf-8 -*-
"""Graph loader for the LLM module planning Agent."""

from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple

from haijunbot.haijunbot_c2rust.llm_module_agent_types import FnMeta
from haijunbot.haijunbot_utils.jsonnet_compat import loads as json_loads


class GraphLoader:
    """
    Reads symbols and call relationships only from symbols.jsonl, providing subgraph traversal capabilities:
    - Data source: <project_root>/.haijunbot/c2rust/symbols.jsonl or an explicitly passed .jsonl file
    - No fallback strategies are supported anymore (symbols_raw.jsonl, functions.jsonl, etc. are not considered)
    """

    def __init__(self, db_path: Path, project_root: Path):
        self.project_root = Path(project_root).resolve()

        def _resolve_data_path(hint: Path) -> Path:
            p = Path(hint)
            # Only symbols.jsonl is supported; functions.jsonl or other legacy formats are no longer compatible
            # If a file path is passed directly and it is .jsonl, use it directly (it must contain category/ref fields)
            if p.is_file() and p.suffix.lower() == ".jsonl":
                return p
            # Directory: only <dir>/.haijunbot/c2rust/symbols.jsonl is supported
            if p.is_dir():
                return p / ".haijunbot" / "c2rust" / "symbols.jsonl"
            # Default: project .haijunbot/c2rust/symbols.jsonl
            return self.project_root / ".haijunbot" / "c2rust" / "symbols.jsonl"

        self.data_path = _resolve_data_path(Path(db_path))
        if not self.data_path.exists():
            raise FileNotFoundError(f"symbols.jsonl not found: {self.data_path}")
        # Initialize in-memory graph structures
        self.adj: Dict[int, List[str]] = {}
        self.name_to_id: Dict[str, int] = {}
        self.fn_by_id: Dict[int, FnMeta] = {}

        # Load symbol metadata and adjacency from symbols.jsonl (functions and types are handled uniformly; name adjacency is built from ref)
        rows_loaded = 0
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json_loads(line)
                    except Exception:
                        # Skip invalid JSON lines, but record them for debugging
                        continue
                    # Do not distinguish functions from types; handle all records in symbols.jsonl uniformly
                    rows_loaded += 1
                    fid = int(obj.get("id") or rows_loaded)
                    nm = obj.get("name") or ""
                    qn = obj.get("qualified_name") or ""
                    sg = obj.get("signature") or ""
                    fp = obj.get("file") or ""
                    refs = obj.get("ref")
                    # Not compatible with old data: strictly require a list type; treat missing as empty
                    if not isinstance(refs, list):
                        refs = []
                    refs = [c for c in refs if isinstance(c, str) and c]
                    self.adj[fid] = refs
                    # Build the name index and function metadata for use in subgraph traversal and context construction
                    if isinstance(nm, str) and nm:
                        self.name_to_id.setdefault(nm, fid)
                    if isinstance(qn, str) and qn:
                        self.name_to_id.setdefault(qn, fid)
                    try:
                        rel_file = self._rel_path(fp)
                    except (ValueError, OSError):
                        rel_file = fp
                    self.fn_by_id[fid] = FnMeta(
                        id=fid,
                        name=nm,
                        qname=qn,
                        signature=sg,
                        file=rel_file,
                        refs=refs,
                    )
        except FileNotFoundError:
            raise
        except (OSError, IOError) as e:
            raise RuntimeError(f"An error occurred while reading symbols.jsonl: {e}") from e
        except Exception as e:
            raise RuntimeError(f"An unknown error occurred while parsing symbols.jsonl: {e}") from e

    def _rel_path(self, abs_path: str) -> str:
        """Convert an absolute path to a path relative to the project root."""
        try:
            p = Path(abs_path).resolve()
            return str(p.relative_to(self.project_root))
        except Exception:
            return abs_path

    def collect_subgraph(self, root_id: int) -> Tuple[Set[int], Set[str]]:
        """
        Starting from root_id, collect all reachable internal functions (visited_ids) and external call names (externals)

        Args:
            root_id: Root function ID

        Returns:
            (visited_ids, externals) tuple
        """
        visited: Set[int] = set()
        externals: Set[str] = set()
        stack: List[int] = [root_id]
        visited.add(root_id)
        while stack:
            src = stack.pop()
            for callee in self.adj.get(src, []):
                cid = self.name_to_id.get(callee)
                if cid is not None:
                    if cid not in visited:
                        visited.add(cid)
                        stack.append(cid)
                else:
                    externals.add(callee)
        return visited, externals

    def build_roots_context(
        self,
        roots: List[int],
        max_functions_per_ns: int = 200,  # Parameter retained for compatibility, but currently unused
        max_namespaces_per_root: int = 50,  # Parameter retained for compatibility, but currently unused
    ) -> List[Dict[str, Any]]:
        """
        Build a context for each root function (call relationships by function name only, including no other information):
        - root_function: the simple name of the root function (without signature/qualified name)
        - functions: a list of the simple names of all functions reachable within this root function's subgraph (without signature/qualified name), deduplicated, sorted, optionally truncated
        Note:
        - Contains no file paths, signatures, qualified names, namespaces, external symbols, or any other metadata
        """
        root_contexts: List[Dict[str, Any]] = []
        for rid in roots:
            meta = self.fn_by_id.get(rid)
            root_label = (meta.name or f"fn_{rid}") if meta else f"fn_{rid}"

            visited_ids, _externals = self.collect_subgraph(rid)
            # Collect all simple function names
            fn_names: List[str] = []
            for fid in sorted(visited_ids):
                m = self.fn_by_id.get(fid)
                if not m:
                    continue
                simple = m.name or f"fn_{fid}"
                fn_names.append(simple)

            # Deduplicate and sort (prefer dict.fromkeys to preserve order)
            try:
                fn_names = sorted(list(dict.fromkeys(fn_names)))
            except (TypeError, ValueError):
                # If dict.fromkeys fails (which should not happen in theory), fall back to set
                fn_names = sorted(list(set(fn_names)))

            root_contexts.append(
                {
                    "root_function": root_label,
                    "functions": fn_names,
                }
            )
        return root_contexts
