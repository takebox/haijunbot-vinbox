# -*- coding: utf-8 -*-
"""
Configuration and progress management module
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from pathlib import Path
from typing import Any
from typing import Dict

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_c2rust.constants import CONFIG_JSON
from haijunbot.haijunbot_c2rust.models import FnRecord
from haijunbot.haijunbot_c2rust.utils import read_json
from haijunbot.haijunbot_c2rust.utils import write_json


class ConfigManager:
    """Configuration and progress manager"""

    def __init__(self, data_dir: Path, progress_path: Path) -> None:
        self.data_dir = data_dir
        self.progress_path = progress_path
        self.progress: Dict[str, Any] = read_json(
            self.progress_path, {"current": None, "converted": []}
        )

    def save_progress(self) -> None:
        """Save progress using an atomic write"""
        write_json(self.progress_path, self.progress)

    def load_config(self) -> Dict[str, Any]:
        """
        Load the config from the dedicated config file.
        If the config file does not exist, try migrating the config from progress.json (backward compatible).
        """
        config_path = self.data_dir / CONFIG_JSON
        default_config = {
            "root_symbols": [],
            "disabled_libraries": [],
            "additional_notes": "",
        }

        # Try reading from the config file
        if config_path.exists():
            config = read_json(config_path, default_config)
            if isinstance(config, dict):
                # Ensure all required keys are present (backward compatible)
                if "additional_notes" not in config:
                    config["additional_notes"] = ""
                return config

        # Backward compatible: if the config file does not exist, try migrating from progress.json
        progress_config = self.progress.get("config", {})
        if progress_config:
            # Migrate the config to the dedicated file
            migrated_config = {
                "root_symbols": progress_config.get("root_symbols", []),
                "disabled_libraries": progress_config.get("disabled_libraries", []),
                "additional_notes": progress_config.get("additional_notes", ""),
            }
            write_json(config_path, migrated_config)
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][config] Migrated config from progress.json to {config_path}"
            )
            return migrated_config

        return default_config

    def save_config(
        self,
        root_symbols: list,
        disabled_libraries: list,
        additional_notes: str,
    ) -> None:
        """Save the config to the dedicated config file"""
        config_path = self.data_dir / CONFIG_JSON
        config = {
            "root_symbols": root_symbols,
            "disabled_libraries": disabled_libraries,
            "additional_notes": additional_notes,
        }
        write_json(config_path, config)

    def load_order_index(
        self,
        order_jsonl: Path,
        fn_index_by_id: Dict[int, FnRecord],
        fn_name_to_id: Dict[str, int],
    ) -> None:
        """
        Load all records from the self-contained order.jsonl, establishing:
        - fn_index_by_id: id -> FnRecord
        - fn_name_to_id: name/qname -> id
        If the same id appears multiple times, the first record takes precedence.
        """
        fn_index_by_id.clear()
        fn_name_to_id.clear()
        PrettyOutput.auto_print(
            f"📊 [c2rust-transpiler][index] Loading translation order index: {order_jsonl}"
        )
        try:
            with order_jsonl.open("r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        obj = json.loads(ln)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_c2rust.transpiler_config",
                            function="load_order_index",
                        )
                        continue
                    # Only the new format is supported: items
                    recs = obj.get("items")
                    if not isinstance(recs, list):
                        continue
                    for r in recs:
                        if not isinstance(r, dict):
                            continue
                        # Build FnRecord
                        try:
                            rec_id = r.get("id")
                            if rec_id is None:
                                continue
                            fid = int(rec_id)
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_c2rust.transpiler_config",
                                function="load_order_index",
                            )
                            continue
                        if fid in fn_index_by_id:
                            # Already registered
                            continue
                        nm = r.get("name") or ""
                        qn = r.get("qualified_name") or ""
                        fp = r.get("file") or ""
                        refs = r.get("ref")
                        if not isinstance(refs, list):
                            refs = []
                        refs = [c for c in refs if isinstance(c, str) and c]
                        sr = int(r.get("start_line") or 0)
                        sc = int(r.get("start_col") or 0)
                        er = int(r.get("end_line") or 0)
                        ec = int(r.get("end_col") or 0)
                        sg = r.get("signature") or ""
                        rt = r.get("return_type") or ""
                        pr = (
                            r.get("params")
                            if isinstance(r.get("params"), list)
                            else None
                        )
                        lr = (
                            r.get("lib_replacement")
                            if isinstance(r.get("lib_replacement"), dict)
                            else None
                        )
                        rec = FnRecord(
                            id=fid,
                            name=nm,
                            qname=qn,
                            file=fp,
                            start_line=sr,
                            start_col=sc,
                            end_line=er,
                            end_col=ec,
                            refs=refs,
                            signature=str(sg or ""),
                            return_type=str(rt or ""),
                            params=pr,
                            lib_replacement=lr,
                        )
                        fn_index_by_id[fid] = rec
                        if nm:
                            fn_name_to_id.setdefault(nm, fid)
                        if qn:
                            fn_name_to_id.setdefault(qn, fid)
        except Exception:
            # If index construction fails, keep it empty; subsequent steps will be skipped
            pass
        PrettyOutput.auto_print(
            f"✅ [c2rust-transpiler][index] Index construction complete: ids={len(fn_index_by_id)} names={len(fn_name_to_id)}"
        )
