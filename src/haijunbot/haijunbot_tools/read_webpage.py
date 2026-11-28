# -*- coding: utf-8 -*-
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, Optional, Callable
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup
from markdownify import markdownify as md

if TYPE_CHECKING:
    pass

try:
    from playwright.sync_api import sync_playwright as _sync_playwright

    sync_playwright: Optional[Callable[[], Any]] = _sync_playwright
except ImportError:
    sync_playwright = None

# Fallback dependencies
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from haijunbot.haijunbot_utils.config import calculate_content_token_limit, get_data_dir
from haijunbot.haijunbot_utils import vinbox_runtime
from haijunbot.haijunbot_utils.embedding import get_context_token_count
from haijunbot.haijunbot_utils.input import user_confirm
from haijunbot.haijunbot_utils.output import PrettyOutput


class WebpageTool:
    name = "read_webpage"
    description = "Use a headless browser to fetch the webpage body and convert it to Markdown (supports JS dynamic rendering); used to read documents/articles/search result details."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL of the webpage to read"},
            "mode": {
                "type": "string",
                "description": "Read mode: text=extract only text (remove link URLs, keep the text); complete=complete content (keep links)",
                "default": "text",
            },
        },
        "required": ["url"],
    }

    def __init__(self) -> None:
        self._ensure_playwright_ready(prompt_user=True)

    @staticmethod
    def _install_playwright_package() -> bool:
        PrettyOutput.auto_print("🔧 Playwright Python package not installed; installing automatically...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "playwright"],
                check=True,
                capture_output=True,
                text=True,
            )
            PrettyOutput.auto_print("✅ Playwright Python package installed successfully!")
            return True
        except subprocess.CalledProcessError as e:
            PrettyOutput.auto_print(f"❌ Failed to install Playwright Python package: {e.stderr or e}")
            return False
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Error occurred while installing the Playwright Python package: {e}")
            return False

    @staticmethod
    def _ensure_playwright_ready(prompt_user: bool = False) -> bool:
        global sync_playwright

        # Check whether the user previously declined installation
        declined_flag = os.path.join(get_data_dir(), "playwright_install_declined.flag")
        if os.path.exists(declined_flag):
            return False

        if sync_playwright is None:
            PrettyOutput.auto_print("⚠️ Playwright Python package is not installed")
            if prompt_user and not user_confirm(
                "Install playwright and chromium automatically now?", default=True
            ):
                # Create a flag file to record the user's declined installation
                try:
                    # Use the already-imported get_data_dir
                    declined_flag = os.path.join(
                        get_data_dir(), "playwright_install_declined.flag"
                    )
                    os.makedirs(os.path.dirname(declined_flag), exist_ok=True)
                    with open(declined_flag, "w") as f:
                        f.write(
                            f"User declined playwright installation at {datetime.now().isoformat()}\n"
                        )
                except Exception:
                    pass  # Ignore errors when creating the flag file
                return False
            if not WebpageTool._install_playwright_package():
                return False
            try:
                from playwright.sync_api import (
                    sync_playwright as imported_sync_playwright,
                )

                sync_playwright = imported_sync_playwright
            except ImportError:
                return False

        try:
            with sync_playwright() as p:
                if vinbox_runtime.is_vinbox():
                    # Vinbox owns the one Chromium behind the center panel.
                    # Never launch a second one here.
                    return True
                browser = p.chromium.launch()
                browser.close()
            return True
        except Exception as e:
            error_msg = str(e)
            if "executable doesn't exist" in error_msg or "driver" in error_msg.lower():
                PrettyOutput.auto_print("⚠️ Browser driver not installed detected")
                if prompt_user and not user_confirm(
                    "Install the Chromium browser driver automatically now?", default=True
                ):
                    return False
                try:
                    from haijunbot.scripts.install_playwright import install_chromium

                    install_chromium()
                    return WebpageTool._ensure_playwright_ready(prompt_user=False)
                except SystemExit:
                    return False
                except Exception as install_error:
                    PrettyOutput.auto_print(f"❌ Automatic installation failed: {install_error}")
                    return False
            return False

    @staticmethod
    def _process_html_for_text_mode(html: str) -> str:
        """Use BeautifulSoup to process HTML, removing non-text content and keeping only the plain-text structure.

        Args:
            html: Original HTML content

        Returns:
            Processed HTML with non-text content such as CSS and JavaScript removed
        """
        soup = BeautifulSoup(html, "lxml")

        # Remove all non-text content tags
        non_text_tags = ["style", "script", "noscript", "link", "meta", "head"]
        for tag_name in non_text_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Remove style-related attributes from all elements
        for tag in soup.find_all(True):  # Find all tags
            # Remove the style attribute (inline CSS)
            if tag.has_attr("style"):
                del tag["style"]
            # Remove the class attribute (CSS class names)
            if tag.has_attr("class"):
                del tag["class"]
            # Remove the id attribute (CSS ID selectors)
            if tag.has_attr("id"):
                del tag["id"]
            # Remove data-* attributes (data attributes)
            attrs_to_remove = [attr for attr in tag.attrs if attr.startswith("data-")]
            for attr in attrs_to_remove:
                del tag[attr]

        # Unwrap all <a> tags, keeping the text content
        for a_tag in soup.find_all("a"):
            a_tag.unwrap()

        return str(soup)

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use a headless browser to read webpage content and return the HTML converted to Markdown format.
        Supports content rendered dynamically by JavaScript.
        """
        try:
            url = str(args.get("url", "")).strip()

            if not url:
                return {"success": False, "stdout": "", "stderr": "Missing required argument: url"}

            # Parse the read mode argument
            mode = str(args.get("mode", "text")).strip().lower()
            if mode not in ["text", "complete"]:
                PrettyOutput.auto_print(f"⚠️ Invalid mode value '{mode}'; using the default value 'text'")
                mode = "text"

            # Use the Playwright headless browser to fetch the webpage content
            try:
                if not self._ensure_playwright_ready(prompt_user=True):
                    raise ImportError("Playwright not available")

                assert sync_playwright is not None, (
                    "sync_playwright should not be None after _ensure_playwright_ready"
                )
                with sync_playwright() as p:
                    # Inside Vinbox use the real Chromium over CDP; elsewhere
                    # keep the standalone headless browser.
                    own_browser = not vinbox_runtime.is_vinbox()
                    if own_browser:
                        browser = p.chromium.launch(headless=True)
                        page = browser.new_page()
                    else:
                        browser, page = vinbox_runtime.new_cdp_page(p)

                    # Set the timeout to 30 seconds
                    page.set_default_timeout(30000)

                    PrettyOutput.auto_print(f"🌐 Accessing with headless browser: {url}")

                    # Navigate to the page and wait for loading
                    page.goto(url, wait_until="networkidle")

                    # Get the rendered HTML content
                    html_content = page.content()

                    # Close only what this tool opened; Vinbox keeps its browser.
                    page.close()
                    if own_browser:
                        browser.close()

                # Process the HTML according to the mode
                if mode == "text":
                    html_content = self._process_html_for_text_mode(html_content)

                # Convert the HTML to Markdown
                content_md = md(html_content, strip=["script", "style"])

            except ImportError:
                # Playwright not installed; attempting to fall back to requests
                PrettyOutput.auto_print(
                    "⚠️ Playwright not installed; falling back to the requests approach..."
                )
                if not REQUESTS_AVAILABLE:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "Neither the Playwright nor the requests library is available. Please install at least one: pip install playwright or pip install requests beautifulsoup4",
                    }

                try:
                    PrettyOutput.auto_print(f"📡 Accessing with requests: {url}")
                    PrettyOutput.auto_print(
                        "💡 Note: the requests approach cannot fetch content rendered dynamically by JavaScript"
                    )

                    response = requests.get(
                        url,
                        timeout=30,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        },
                    )
                    response.raise_for_status()

                    # Process the HTML according to the mode
                    html_to_convert = response.text
                    if mode == "text":
                        html_to_convert = self._process_html_for_text_mode(
                            html_to_convert
                        )

                    # Convert with markdownify; the strip argument removes script and style
                    content_md = md(html_to_convert, strip=["script", "style"])

                except Exception as req_error:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"The requests approach also failed: {req_error}",
                    }

            except Exception as e:
                # Playwright runtime error; attempting to fall back to requests
                PrettyOutput.auto_print(
                    f"⚠️ Headless browser error: {e}; falling back to the requests approach..."
                )

                if not REQUESTS_AVAILABLE:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"Headless browser error: {e}\nNote: the requests library is also unavailable, so fallback is not possible. Please install: pip install requests beautifulsoup4",
                    }

                try:
                    PrettyOutput.auto_print(f"📡 Accessing with requests: {url}")
                    PrettyOutput.auto_print(
                        "💡 Note: the requests approach cannot fetch content rendered dynamically by JavaScript"
                    )

                    response = requests.get(
                        url,
                        timeout=30,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        },
                    )
                    response.raise_for_status()

                    # Process the HTML according to the mode
                    html_to_convert = response.text
                    if mode == "text":
                        html_to_convert = self._process_html_for_text_mode(
                            html_to_convert
                        )

                    # Convert with markdownify; the strip argument removes script and style
                    content_md = md(html_to_convert, strip=["script", "style"])

                except Exception as req_error:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"The requests approach also failed: {req_error}",
                    }

            if not content_md or not content_md.strip():
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Unable to fetch valid content from the webpage.",
                }

            # Dynamically calculate the content length limit based on remaining tokens to avoid overly long content
            token_limit = calculate_content_token_limit()

            # Truncate based on the token count
            content_token_count = get_context_token_count(content_md)
            if content_token_count > token_limit:
                # Accumulate chunk by chunk with a fixed small chunk size to make full use of the token limit
                # Set the chunk size to 100 characters to avoid frequent computation while ensuring fine-grained control
                chunk_size = 100
                truncated_text = ""
                truncated_tokens = 0

                for i in range(0, len(content_md), chunk_size):
                    chunk = content_md[i : i + chunk_size]
                    chunk_tokens = get_context_token_count(chunk)

                    # If the current chunk exceeds the remaining limit, skip it and continue processing subsequent chunks
                    if chunk_tokens > token_limit - truncated_tokens:
                        continue

                    truncated_text += chunk
                    truncated_tokens += chunk_tokens

                content_md_truncated = truncated_text
                PrettyOutput.auto_print(
                    f"⚠️ Webpage content is too long ({content_token_count} tokens); truncated to {truncated_tokens} tokens"
                )
            else:
                content_md_truncated = content_md

            # Use print_markdown to print the webpage content
            PrettyOutput.print_markdown(
                content_md_truncated,
                title=f"📄 Webpage content: {url}",
                border_style="bright_blue",
                theme="monokai",
            )

            # Directly return the webpage content in Markdown format
            return {"success": True, "stdout": content_md_truncated, "stderr": ""}

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to read webpage: {str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to parse webpage: {str(e)}",
            }

    @staticmethod
    def check() -> bool:
        """Tool availability check: check whether Playwright or the requests fallback is available."""
        if WebpageTool._ensure_playwright_ready(prompt_user=False):
            return True

        if REQUESTS_AVAILABLE:
            PrettyOutput.auto_print(
                "✅ requests fallback is available (does not support JavaScript dynamic rendering)"
            )
            return True

        PrettyOutput.auto_print("❌ Neither Playwright nor requests is available")
        PrettyOutput.auto_print("💡 Please install at least one approach:")
        PrettyOutput.auto_print("   - pip install playwright")
        PrettyOutput.auto_print("   - pip install requests beautifulsoup4")
        return False
