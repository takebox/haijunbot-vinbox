# -*- coding: utf-8 -*-
"""OCR text recognition tool

Extract text from images into plain text, so models that do **not support multimodal** can "see" images,
and also usable for extracting text from screenshots, receipts/documents, etc.

Design points (pluggable multiple backends + graceful degradation):
- The project insists on "not adding third-party dependencies", so this tool does not force any OCR dependency.
- All backends are **lazily imported inside functions**; when missing they are skipped automatically, without affecting module import or tool loading.
- `check()` returns True as long as any backend is detected as available; if none is available the tool is not registered.
- Backend priority (auto mode): tesseract → rapidocr → paddleocr → easyocr → vision.

Backend notes:
- tesseract: local engine, requires the system-installed tesseract executable (apt install tesseract-ocr);
  if pytesseract is installed, confidence and coordinates are available (more useful when detail=true).
- rapidocr: pip install rapidocr_onnxruntime, pure onnx, no system dependency.
- paddleocr / easyocr: usable after pip install, relatively large.
- vision: calls the multimodal large model already configured in the project to recognize the image (no local OCR dependency, but requires network and model configuration).
"""

import base64
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from haijunbot.haijunbot_utils.output import PrettyOutput

# Whitelist of supported image extensions
_SUPPORTED_EXTS = {
    "png",
    "jpg",
    "jpeg",
    "bmp",
    "tif",
    "tiff",
    "webp",
    "gif",
    "pbm",
    "pgm",
    "ppm",
}

# Extension -> MIME type (needed by the vision backend when building the data URL)
_MIME_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "bmp": "image/bmp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "webp": "image/webp",
    "gif": "image/gif",
    "pbm": "image/x-portable-bitmap",
    "pgm": "image/x-portable-graymap",
    "ppm": "image/x-portable-pixmap",
}

# Image size upper limit (default 20 MiB, consistent with add_images' max_image_size)
_DEFAULT_MAX_SIZE = 20 * 1024 * 1024

# Timeout for downloading remote images (seconds)
_DOWNLOAD_TIMEOUT = 30


class OcrTool:
    """OCR text recognition tool (pluggable multiple backends)

    Supported operation: recognize one image (local path or URL) per call.

    Typical usage:
    - Recognize a local screenshot: {"image": "/tmp/shot.png"}
    - Mixed Chinese and English: {"image": "a.png", "lang": "chi_sim+eng"}
    - Need coordinate info: {"image": "a.png", "detail": true}
    - Specify backend: {"image": "a.png", "backend": "rapidocr"}

    **Tip**: If the model itself supports multimodal, looking at the original image directly is usually more accurate than OCR;
    this tool is mainly aimed at scenarios where "the model does not support multimodal" or "only plain text is needed".
    """

    name = "ocr"

    @staticmethod
    def check() -> bool:
        """Check whether the tool is available: enabled if any OCR backend is available.

        Note: this method must be **fast and side-effect-free** (no network requests, no exceptions),
        because it is called during the tool loading stage.
        """
        try:
            # 1) tesseract engine (a system executable; pytesseract is just its Python wrapper)
            if shutil.which("tesseract"):
                return True

            # 2) Pure Python backends (detected with find_spec, not actually imported; fast and side-effect-free)
            for module_name in (
                "rapidocr_onnxruntime",
                "paddleocr",
                "easyocr",
            ):
                if OcrTool._module_available(module_name):
                    return True

            # 3) vision backend: only a lightweight check (whether a usable platform config exists)
            if OcrTool._has_vision_config():
                return True

            return False
        except Exception:
            # check never raises exceptions; any exception is treated as unavailable
            return False

    @staticmethod
    def _module_available(module_name: str) -> bool:
        """Determine whether an optional module is importable (using find_spec, not actually importing)."""
        try:
            import importlib.util

            return importlib.util.find_spec(module_name) is not None
        except Exception:
            return False

    @staticmethod
    def _has_vision_config() -> bool:
        """Lightweight check whether a platform usable for visual recognition is configured (does not make any network request)."""
        try:
            from haijunbot.haijunbot_platform.registry import PlatformRegistry

            registry = PlatformRegistry.get_global_platform_registry()
            platform = registry.get_normal_platform()
            return platform is not None
        except Exception:
            return False

    description = """OCR text recognition tool: extract text from an image (local path or http(s) URL) into plain text.

Use cases: "seeing" images when the model does not support multimodal, extracting text from screenshots, receipts/documents/tables text extraction.

One image is recognized per call. Parameters:
- image (required): local image path (supports ~ and relative paths) or http(s) image URL
- backend (optional): auto (default, choose automatically by availability) / tesseract / rapidocr / paddleocr / easyocr / vision
- lang (optional): recognition language, default "eng"; tesseract supports combinations like "chi_sim+eng"
- psm (optional): tesseract page segmentation mode (3=fully automatic, 6=single block of text, 7=single line, 11=sparse text)
- detail (optional): when true, additionally returns per-line info (text/confidence/coordinates, depending on backend capability)
- options (optional): extra parameter object passed through to the backend

Returns: the recognized text (with per-line details when detail=true).
If no OCR backend is installed on this machine, a clear installation hint is returned.

**Tip**: If the model itself supports multimodal, looking at the original image is usually more accurate; this tool targets plain-text extraction scenarios."""

    parameters = {
        "type": "object",
        "properties": {
            "image": {
                "type": "string",
                "description": "Image path (local path or http(s) URL). Local paths support ~ expansion and relative paths",
            },
            "backend": {
                "type": "string",
                "enum": [
                    "auto",
                    "tesseract",
                    "rapidocr",
                    "paddleocr",
                    "easyocr",
                    "vision",
                ],
                "description": "OCR backend; auto means choose automatically by availability (default auto)",
                "default": "auto",
            },
            "lang": {
                "type": "string",
                "description": 'Recognition language, default "eng"; tesseract can take combinations like "chi_sim+eng"',
                "default": "eng",
            },
            "psm": {
                "type": "integer",
                "description": "tesseract page segmentation mode (3=fully automatic, 6=single block, 7=single line, 11=sparse text)",
            },
            "detail": {
                "type": "boolean",
                "description": "Whether to return per-line/per-block info (text+confidence+coordinates, depending on backend capability)",
                "default": False,
            },
            "options": {
                "type": "object",
                "description": "Extra parameters passed through to the backend (keys and values determined by the specific backend)",
            },
        },
        "required": ["image"],
    }

    # ------------------------------------------------------------------
    # Image preparation
    # ------------------------------------------------------------------
    def _resolve_image(self, image: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse the input into a usable local image path.

        Returns (local path, error message): on success the error message is None; on failure the path is None.
        Remote URLs are downloaded to a temporary file (the caller is responsible for cleanup).
        """
        image = str(image or "").strip()
        if not image:
            return None, "image must not be empty"

        # Remote URL: download to a temporary file
        if image.startswith(("http://", "https://")):
            try:
                import requests
            except Exception:
                return None, "Downloading remote images requires the requests library, but it is unavailable in the current environment"

            try:
                resp = requests.get(image, timeout=_DOWNLOAD_TIMEOUT, stream=True)
                resp.raise_for_status()
            except Exception as e:
                return None, f"Failed to download remote image: {e}"

            # Infer the extension (prefer Content-Type, fall back to the URL suffix)
            ext = self._guess_ext_from_url(image, resp.headers.get("Content-Type", ""))
            if ext not in _SUPPORTED_EXTS:
                return None, (
                    f"Remote image format not supported: {ext or 'unknown'}; "
                    f"supported: {', '.join(sorted(_SUPPORTED_EXTS))}"
                )

            try:
                fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}", prefix="haijunbot_ocr_")
                with os.fdopen(fd, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
            except Exception as e:
                return None, f"Failed to save remote image: {e}"
            return tmp_path, None

        # Local path: ~ expansion + relative to absolute
        path = os.path.abspath(os.path.expanduser(image))
        if not os.path.exists(path):
            return None, f"Image file does not exist: {path}"
        if not os.path.isfile(path):
            return None, f"Not a file: {path}"

        ext = os.path.splitext(path)[1].lower().lstrip(".")
        if ext not in _SUPPORTED_EXTS:
            return None, (
                f"Image format not supported: {ext or 'unknown'}; "
                f"supported: {', '.join(sorted(_SUPPORTED_EXTS))}"
            )

        # Size validation
        max_size = self._max_image_size()
        try:
            size = os.path.getsize(path)
        except OSError as e:
            return None, f"Unable to read image size: {e}"
        if size > max_size:
            return None, (
                f"Image too large: {size} bytes, exceeding the limit of {max_size} bytes"
                f"(about {max_size // (1024 * 1024)} MiB)"
            )
        if size == 0:
            return None, f"Image is an empty file: {path}"

        return path, None

    @staticmethod
    def _guess_ext_from_url(url: str, content_type: str) -> str:
        """Infer the image extension from Content-Type or the URL suffix (lowercase, without the dot)."""
        ct = (content_type or "").lower()
        ct_map = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/bmp": "bmp",
            "image/tiff": "tiff",
            "image/webp": "webp",
            "image/gif": "gif",
        }
        for key, ext in ct_map.items():
            if key in ct:
                return ext
        # Fallback: take the suffix from the URL path
        path_part = url.split("?", 1)[0].split("#", 1)[0]
        return os.path.splitext(path_part)[1].lower().lstrip(".")

    @staticmethod
    def _max_image_size() -> int:
        """Read the project-configured image size limit; use the default value if reading fails."""
        try:
            from haijunbot.haijunbot_platform.content_types import CONTENT_CONFIG

            max_size = CONTENT_CONFIG.get("max_image_size", _DEFAULT_MAX_SIZE)
            if isinstance(max_size, int) and max_size > 0:
                return max_size
        except Exception:
            pass
        return _DEFAULT_MAX_SIZE

    @staticmethod
    def _encode_data_url(path: str) -> str:
        """Encode a local image as a data URL (used by the vision backend)."""
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime = _MIME_MAP.get(ext, "application/octet-stream")
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    # ------------------------------------------------------------------
    # Backend detection
    # ------------------------------------------------------------------
    @staticmethod
    def _tesseract_available() -> bool:
        """Whether tesseract is available (the CLI existing is enough; pytesseract is an enhancement)."""
        return shutil.which("tesseract") is not None

    @staticmethod
    def _import_optional(module_name: str):
        """Lazily import an optional module; return None on failure."""
        try:
            import importlib

            return importlib.import_module(module_name)
        except Exception:
            return None

    def _pick_backend(self, requested: str) -> Optional[str]:
        """Select the actual backend by auto priority; return as-is when explicitly specified."""
        requested = (requested or "auto").strip().lower()
        if requested and requested != "auto":
            return requested

        # auto: sort by availability and lightness
        if self._tesseract_available():
            return "tesseract"
        if self._import_optional("rapidocr_onnxruntime") is not None:
            return "rapidocr"
        if self._import_optional("paddleocr") is not None:
            return "paddleocr"
        if self._import_optional("easyocr") is not None:
            return "easyocr"
        if self._has_vision_config():
            return "vision"
        return None

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------
    def _run_tesseract(
        self,
        path: str,
        lang: str,
        psm: Optional[int],
        detail: bool,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """tesseract backend: prefer pytesseract (can get confidence/coordinates), otherwise call the CLI."""
        if not self._tesseract_available():
            return {
                "success": False,
                "stdout": "",
                "stderr": (
                    "tesseract backend unavailable: tesseract executable not found.\n"
                    "Installation:\n"
                    "  - Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-chi-sim\n"
                    "  - macOS: brew install tesseract tesseract-lang\n"
                    "  - Windows: download and install https://github.com/UB-Mannheim/tesseract/wiki\n"
                    "Optional: pip install pytesseract (to get confidence and coordinate info)"
                ),
            }

        pytesseract = self._import_optional("pytesseract")
        if pytesseract is not None:
            try:
                from PIL import Image  # noqa: F401
            except Exception:
                pytesseract = None  # Fall back to CLI if PIL is absent

        if pytesseract is not None:
            return self._run_tesseract_py(pytesseract, path, lang, psm, detail, options)
        return self._run_tesseract_eli(path, lang, psm, detail)

    def _run_tesseract_py(
        self,
        pytesseract,
        path: str,
        lang: str,
        psm: Optional[int],
        detail: bool,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run recognition with pytesseract (can output confidence and coordinates)."""
        from PIL import Image

        config_parts: List[str] = []
        if psm is not None:
            config_parts.append(f"--psm {int(psm)}")
        extra_config = str(options.get("config", "")).strip()
        if extra_config:
            config_parts.append(extra_config)
        config = " ".join(config_parts)

        data: Optional[Dict[str, Any]] = None
        try:
            with Image.open(path) as img:
                if detail:
                    data = pytesseract.image_to_data(
                        img,
                        lang=lang,
                        config=config,
                        output_type=pytesseract.Output.DICT,
                    )
                text = pytesseract.image_to_string(img, lang=lang, config=config)
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"tesseract recognition failed: {e}",
            }

        lines = (
            self._tesseract_lines_from_data(data)
            if (detail and data is not None)
            else []
        )
        return self._format_success(text, lines, "tesseract", detail)

    @staticmethod
    def _tesseract_lines_from_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Organize the DICT output of pytesseract.image_to_data into per-line info."""
        lines: List[Dict[str, Any]] = []
        n = len(data.get("text", []))
        for i in range(n):
            word = str(data["text"][i] or "").strip()
            if not word:
                continue
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                conf = -1.0
            if conf < 0:
                continue
            lines.append(
                {
                    "text": word,
                    "confidence": round(conf, 2),
                    "bbox": {
                        "x": int(data["left"][i]),
                        "y": int(data["top"][i]),
                        "width": int(data["width"][i]),
                        "height": int(data["height"][i]),
                    },
                }
            )
        return lines

    def _run_tesseract_eli(
        self, path: str, lang: str, psm: Optional[int], detail: bool
    ) -> Dict[str, Any]:
        """Run recognition with the tesseract CLI (no confidence/coordinates)."""
        cmd = ["tesseract", path, "stdout", "-l", lang]
        if psm is not None:
            cmd.extend(["--psm", str(int(psm))])
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "tesseract CLI execution timed out (>120s)",
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"tesseract CLI execution failed: {e}",
            }

        if proc.returncode != 0:
            err = (proc.stderr or "").strip()
            hint = ""
            if "Failed loading language" in err or "Error opening data file" in err:
                hint = (
                    f"\nHint: language pack '{lang}' may not be installed. "
                    "On Ubuntu/Debian you can run: sudo apt install tesseract-ocr-chi-sim"
                )
            return {
                "success": False,
                "stdout": "",
                "stderr": f"tesseract returned code {proc.returncode}: {err}{hint}",
            }

        lines: List[Dict[str, Any]] = []
        if detail:
            # CLI mode has no coordinate info; state this honestly
            lines = [
                {"text": ln, "confidence": None, "bbox": None}
                for ln in (proc.stdout or "").splitlines()
                if ln.strip()
            ]
        return self._format_success(proc.stdout or "", lines, "tesseract-cli", detail)

    def _run_rapidocr(
        self, path: str, detail: bool, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """rapidocr_onnxruntime backend."""
        mod = self._import_optional("rapidocr_onnxruntime")
        if mod is None:
            return {
                "success": False,
                "stdout": "",
                "stderr": (
                    "rapidocr backend unavailable: rapidocr_onnxruntime is not installed.\n"
                    "Installation: pip install rapidocr_onnxruntime"
                ),
            }
        try:
            engine = mod.RapidOCR()
            result, _elapse = engine(path)
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"rapidocr recognition failed: {e}",
            }

        lines: List[Dict[str, Any]] = []
        texts: List[str] = []
        for item in result or []:
            # RapidOCR returns [bbox, text, score]
            try:
                bbox, text, score = item[0], item[1], item[2]
            except Exception:
                continue
            text = str(text or "").strip()
            if not text:
                continue
            texts.append(text)
            try:
                conf = round(float(score) * 100, 2)
            except (TypeError, ValueError):
                conf = None
            lines.append({"text": text, "confidence": conf, "bbox": bbox})
        return self._format_success("\n".join(texts), lines, "rapidocr", detail)

    def _run_paddleocr(
        self, path: str, lang: str, detail: bool, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """paddleocr backend (lazy import and adapt to its API)."""
        mod = self._import_optional("paddleocr")
        if mod is None:
            return {
                "success": False,
                "stdout": "",
                "stderr": (
                    "paddleocr backend unavailable: paddleocr is not installed.\n"
                    "Installation: pip install paddleocr paddlepaddle"
                ),
            }
        try:
            # PaddleOCR 3.x and 2.x have different constructor parameters; use the minimal common parameters here
            ocr = mod.PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
            raw = ocr.ocr(path, cls=True)
        except TypeError:
            # Compatible with unsupported parameters (e.g. show_log was removed in 3.x)
            try:
                ocr = mod.PaddleOCR(lang=lang)
                raw = ocr.ocr(path)
            except Exception as e:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"paddleocr recognition failed: {e}",
                }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"paddleocr recognition failed: {e}",
            }

        lines: List[Dict[str, Any]] = []
        texts: List[str] = []
        # Compatible with the 2.x ([[ [bbox,(text,score)], ... ]]) and 3.x ([{"rec_texts":[...]}]) structures
        for page in raw or []:
            if isinstance(page, dict):
                for t in page.get("rec_texts", []) or []:
                    t = str(t or "").strip()
                    if t:
                        texts.append(t)
                        lines.append({"text": t, "confidence": None, "bbox": None})
                continue
            for item in page or []:
                try:
                    bbox, (text, score) = item[0], item[1]
                except Exception:
                    continue
                text = str(text or "").strip()
                if not text:
                    continue
                texts.append(text)
                try:
                    conf = round(float(score) * 100, 2)
                except (TypeError, ValueError):
                    conf = None
                lines.append({"text": text, "confidence": conf, "bbox": bbox})
        return self._format_success("\n".join(texts), lines, "paddleocr", detail)

    def _run_easyocr(
        self, path: str, lang: str, detail: bool, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """easyocr backend (lazy import and adapt to its API)."""
        mod = self._import_optional("easyocr")
        if mod is None:
            return {
                "success": False,
                "stdout": "",
                "stderr": (
                    "easyocr backend unavailable: easyocr is not installed.\n"
                    "Installation: pip install easyocr"
                ),
            }
        try:
            # easyocr language codes differ from tesseract; do common mappings
            lang_map = {
                "eng": "en",
                "chi_sim": "ch_sim",
                "chi_tra": "ch_tra",
                "jpn": "ha",
                "kor": "ko",
            }
            langs = [
                lang_map.get(x.strip(), x.strip()) for x in lang.split("+") if x.strip()
            ]
            reader = mod.Reader(langs, gpu=False)
            raw = reader.readtext(path)
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"easyocr recognition failed: {e}",
            }

        lines: List[Dict[str, Any]] = []
        texts: List[str] = []
        for item in raw or []:
            try:
                bbox, text, score = item[0], item[1], item[2]
            except Exception:
                continue
            text = str(text or "").strip()
            if not text:
                continue
            texts.append(text)
            try:
                conf = round(float(score) * 100, 2)
            except (TypeError, ValueError):
                conf = None
            lines.append({"text": text, "confidence": conf, "bbox": bbox})
        return self._format_success("\n".join(texts), lines, "easyocr", detail)

    def _run_vision(
        self, path: str, detail: bool, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """vision backend: call the project-configured multimodal large model to recognize text in the image."""
        try:
            from haijunbot.haijunbot_platform.registry import PlatformRegistry
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"vision backend unavailable: cannot import the platform module ({e})",
            }

        try:
            registry = PlatformRegistry.get_global_platform_registry()
            platform = registry.get_normal_platform()
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"vision backend unavailable: failed to get platform ({e})",
            }
        if platform is None:
            return {
                "success": False,
                "stdout": "",
                "stderr": (
                    "vision backend unavailable: no usable model platform is configured.\n"
                    "Please configure a model in llm_config and ensure supports_multimodal: true"
                ),
            }

        try:
            if (
                hasattr(platform, "supports_multimodal")
                and not platform.supports_multimodal()
            ):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": (
                        "vision backend unavailable: the current model has not enabled multimodal.\n"
                        "Please set supports_multimodal: true in llm_config"
                    ),
                }
        except Exception:
            pass

        try:
            data_url = self._encode_data_url(path)
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Image encoding failed: {e}",
            }

        prompt = str(
            options.get(
                "prompt",
                "Please extract all text from this image and output plain text in the original reading order, "
                "without adding any explanation, headings, or Markdown markup. If there is no text in the image, output an empty string.",
            )
        )
        # Build the multimodal message content (using the same ContentBlock types as add_images.py)
        try:
            from haijunbot.haijunbot_platform.content_types import (
                ContentBlock,
                ImageURLContent,
                TextContent,
            )

            text_block: TextContent = {"type": "text", "text": prompt}
            image_block: ImageURLContent = {
                "type": "image_url",
                "image_url": data_url,
            }
            content: List[ContentBlock] = [text_block, image_block]
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to build multimodal message: {e}",
            }

        try:
            resp = platform.chat_until_success(content)
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"vision backend model call failed: {e}",
            }

        text = resp if isinstance(resp, str) else str(resp or "")
        lines = (
            [
                {"text": ln, "confidence": None, "bbox": None}
                for ln in text.splitlines()
                if ln.strip()
            ]
            if detail
            else []
        )
        return self._format_success(text, lines, "vision", detail)

    # ------------------------------------------------------------------
    # Result assembly
    # ------------------------------------------------------------------
    @staticmethod
    def _format_success(
        text: str, lines: List[Dict[str, Any]], backend: str, detail: bool
    ) -> Dict[str, Any]:
        """Assemble the success return."""
        text = (text or "").strip()
        out_parts: List[str] = []
        if text:
            out_parts.append(text)
        else:
            out_parts.append("(no text recognized)")

        if detail:
            out_parts.append("")
            out_parts.append(f"--- Per-line details (backend: {backend}) ---")
            if lines:
                for idx, ln in enumerate(lines, 1):
                    conf = ln.get("confidence")
                    bbox = ln.get("bbox")
                    conf_str = f"conf={conf}" if conf is not None else "conf=N/A"
                    bbox_str = f"bbox={bbox}" if bbox else "bbox=N/A"
                    out_parts.append(
                        f"{idx:>4}. {ln.get('text', '')}  [{conf_str} {bbox_str}]"
                    )
            else:
                out_parts.append("(the current backend did not provide per-line/coordinate info)")

        return {
            "success": True,
            "stdout": "\n".join(out_parts),
            "stderr": "",
            "text": text,
            "backend": backend,
            "lines": lines,
        }

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute OCR recognition.

        Params:
            args: tool parameters (image/backend/lang/psm/detail/options)
        Returns:
            Dict[str, Any]: {"success": bool, "stdout": str, "stderr": str, ...}
        """
        # Compatible with the v1.0 protocol: registry may pass the entire parameter dict as args
        if not isinstance(args, dict):
            return {
                "success": False,
                "stdout": "",
                "stderr": "Parameters must be an object",
            }

        image = args.get("image")
        backend = str(args.get("backend") or "auto").strip().lower()
        lang = str(args.get("lang") or "eng").strip() or "eng"
        psm = args.get("psm")
        detail = bool(args.get("detail", False))
        options = args.get("options")
        if not isinstance(options, dict):
            options = {}

        if not image:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing required parameter image (image path or URL)",
            }

        # Prepare the image (URLs are downloaded to a temporary file)
        local_path, err = self._resolve_image(str(image))
        if local_path is None:
            return {"success": False, "stdout": "", "stderr": err or "Image preparation failed"}

        is_temp = str(image).startswith(("http://", "https://"))
        try:
            # Select the backend
            chosen = self._pick_backend(backend)
            if chosen is None:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": (
                        "No OCR backend is available. Please install any one of the following:\n"
                        "  1) system tesseract: sudo apt install tesseract-ocr tesseract-ocr-chi-sim\n"
                        "  2) pip install pytesseract (together with system tesseract)\n"
                        "  3) pip install rapidocr_onnxruntime (pure Python, recommended)\n"
                        "  4) pip install paddleocr paddlepaddle\n"
                        "  5) pip install easyocr\n"
                        "  6) or configure a multimodal-capable model and use backend=vision"
                    ),
                }

            # Clear error when explicitly specified but unavailable
            if backend != "auto":
                avail = {
                    "tesseract": self._tesseract_available(),
                    "rapidocr": self._import_optional("rapidocr_onnxruntime")
                    is not None,
                    "paddleocr": self._import_optional("paddleocr") is not None,
                    "easyocr": self._import_optional("easyocr") is not None,
                    "vision": self._has_vision_config(),
                }
                if not avail.get(backend, False):
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"The specified backend '{backend}' is currently unavailable; please install the corresponding dependency or use auto.",
                    }

            # Dispatch to the specific backend
            if chosen == "tesseract":
                result = self._run_tesseract(local_path, lang, psm, detail, options)
            elif chosen == "rapidocr":
                result = self._run_rapidocr(local_path, detail, options)
            elif chosen == "paddleocr":
                result = self._run_paddleocr(local_path, lang, detail, options)
            elif chosen == "easyocr":
                result = self._run_easyocr(local_path, lang, detail, options)
            elif chosen == "vision":
                result = self._run_vision(local_path, detail, options)
            else:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Unknown backend: {chosen}",
                }

            if result.get("success"):
                PrettyOutput.auto_print(
                    f"✅ OCR done (backend: {result.get('backend', chosen)})"
                )
            return result
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"OCR execution error: {e}",
            }
        finally:
            # Clean up the temporary file downloaded from remote
            if is_temp and local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except OSError:
                    pass
