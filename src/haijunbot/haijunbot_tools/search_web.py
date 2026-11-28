"""Web search tool."""

from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional
from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-

import html
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
from urllib.parse import urlparse

import requests

try:
    from bs4 import BeautifulSoup
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
import shutil
import subprocess
import sys

# pylint: disable=import-error,missing-module-docstring

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils import vinbox_runtime

# fmt: on

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def _contains_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return bool(_CHINESE_PATTERN.search(text))


_ANTI_SPIDER_MARKERS = (
    "access denied page",
    "access anomaly",
    "please enter captcha",
    "verification code",
    "security verification",
    "antispider",
)


def _is_anti_spider_page(html_content: str) -> bool:
    """Check if the response content is a search engine anti-spider verification page."""
    lowered = html_content.lower()
    return any(marker in lowered for marker in _ANTI_SPIDER_MARKERS)


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication: remove query string, trailing slash, lowercase domain."""
    if not url:
        return ""
    parsed = urlparse(url)
    if not parsed.netloc:
        return url.rstrip("/").lower()
    path = parsed.path.rstrip("/")
    return f"{parsed.netloc.lower()}{path}".lower()


class SearchWebTool:
    """Class handling web search."""

    name = "search_web"
    description = "Search the internet and return results; use when external/latest information or verification is needed, and can be paired with read_webpage to open result details."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keyword or question",
            },
            "site": {
                "type": "string",
                "description": "Search within a specific site, e.g., 'wikipedia.org', 'github.com'",
            },
        },
        "required": ["query"],
    }

    def _search_stackoverflow(self, query: str, limit: int = 5) -> list[Dict[str, str]]:
        """Search StackOverflow technical Q&A via StackExchange API.

        Args:
            query: Search keywords
            limit: Maximum number of results to return

        Returns:
            list[Dict[str, str]]: Each item contains title/url/abstract, returns empty list on failure
        """
        try:
            response = requests.get(
                "https://api.stackexchange.com/2.3/search/advanced",
                params={
                    "order": "desc",
                    "sort": "relevance",
                    "q": query,
                    "site": "stackoverflow",
                    "pagesize": limit,
                },
                headers={
                    "User-Agent": _BROWSER_USER_AGENT,
                    "Accept": "application/json",
                },
                timeout=15,
            )
            response.raise_for_status()
            items = response.json().get("items", [])
            results: list[Dict[str, str]] = []
            for item in items[:limit]:
                title = html.unescape(str(item.get("title", "")))
                url = str(item.get("link", ""))
                if not title or not url:
                    continue
                tags = ",".join(item.get("tags", []) or [])
                score = item.get("score", 0)
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "abstract": f"score={score}, tags={tags}",
                    }
                )
            return results
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_tools.search_web",
                function="_search_stackoverflow",
            )
            return []

    def _search_github(self, query: str, limit: int = 5) -> list[Dict[str, str]]:
        """Search code repositories via GitHub Search API.

        Args:
            query: Search keywords
            limit: Maximum number of results to return

        Returns:
            list[Dict[str, str]]: Each item contains title/url/abstract, returns empty list on failure
        """
        try:
            response = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "per_page": limit},
                headers={
                    "User-Agent": _BROWSER_USER_AGENT,
                    "Accept": "application/vnd.github+json",
                },
                timeout=15,
            )
            response.raise_for_status()
            items = response.json().get("items", [])
            results: list[Dict[str, str]] = []
            for item in items[:limit]:
                title = str(item.get("full_name", ""))
                url = str(item.get("html_url", ""))
                if not title or not url:
                    continue
                description = str(item.get("description") or "")
                stars = item.get("stargazers_count", 0)
                abstract = f"⭐{stars} {description}".strip()
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "abstract": abstract,
                    }
                )
            return results
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_tools.search_web",
                function="_search_github",
            )
            return []

    def _search_360(self, query: str, limit: int = 5) -> list[Dict[str, str]]:
        """Scrape general web results via 360 Search.

        Args:
            query: Search keywords
            limit: Maximum number of results to return

        Returns:
            list[Dict[str, str]]: Each item contains title/url/abstract, returns empty list on failure
        """
        try:
            response = requests.get(
                "https://www.so.com/s",
                params={"q": query},
                headers={
                    "User-Agent": _BROWSER_USER_AGENT,
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                timeout=20,
            )
            response.raise_for_status()
            if _is_anti_spider_page(response.text):
                PrettyOutput.auto_print("⚠️ 360 Search triggered anti-spider verification, skipping this source")
                return []
            soup = BeautifulSoup(response.text, "lxml")
            results: list[Dict[str, str]] = []
            for anchor in soup.select("h3 a"):
                title = anchor.get_text(strip=True)
                url = self._resolve_360_url(str(anchor.get("href", "")))
                if not title or not url:
                    continue
                abstract = self._extract_360_abstract(anchor)
                results.append({"title": title, "url": url, "abstract": abstract})
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_tools.search_web",
                function="_search_360",
            )
            return []

    @staticmethod
    def _resolve_360_url(url: str) -> str:
        """Restore 360 redirect links to real URLs, return non-redirect links as-is."""
        if "so.com/link" not in url:
            return url
        try:
            response = requests.get(
                url,
                headers={"User-Agent": _BROWSER_USER_AGENT},
                timeout=10,
                allow_redirects=True,
            )
            final_url = str(response.url)
            return final_url if "so.com/link" not in final_url else url
        except Exception:
            return url

    @staticmethod
    def _extract_360_abstract(anchor: Any) -> str:
        """Extract abstract text from the title node of a 360 search result entry."""
        parent = anchor.find_parent(["li", "div"])
        if parent is None:
            return ""
        for node in parent.select("p, div.res-desc, span.res-desc"):
            text = node.get_text(strip=True)
            if text and text != anchor.get_text(strip=True):
                return text
        return ""

    def _fallback_search(
        self,
        query: str,
        agent: Agent,
        site: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fallback entry when ddgr fails: try multi-source aggregation first, then fall back to Bing.

        Args:
            query: Search keywords
            agent: Current Agent (for Bing/Playwright fallback)
            site: Site filter (optional)

        Returns:
            Dict[str, Any]: Output structure consistent with execute
        """
        PrettyOutput.auto_print("⚠️ ddgr unavailable, falling back to multi-source aggregation search...")
        try:
            aggregated = self._search_multi_source(query=query, site=site)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_tools.search_web",
                function="_fallback_search",
            )
            aggregated = {"success": False}

        if aggregated.get("success"):
            return aggregated

        PrettyOutput.auto_print("⚠️ Multi-source aggregation returned no results, falling back to Bing search...")
        return self._search_with_playwright(query=query, agent=agent, site=site)

    def _search_multi_source(
        self, query: str, site: Optional[str] = None
    ) -> Dict[str, Any]:
        """Aggregate multiple search sources in parallel, merge and deduplicate results.

        Args:
            query: Search keywords
            site: Site filter (optional)

        Returns:
            Dict[str, Any]: Output structure consistent with _format_search_results
        """
        source_funcs = self._build_source_functions(query, site)
        merged: list[Dict[str, str]] = []
        succeeded: list[str] = []

        with ThreadPoolExecutor(max_workers=len(source_funcs)) as executor:
            futures = {
                name: executor.submit(func) for name, func in source_funcs.items()
            }
            # Collect results in source priority order to ensure stable output order
            for name, future in futures.items():
                try:
                    items = future.result()
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.search_web",
                        function="_search_multi_source",
                    )
                    continue
                if items:
                    succeeded.append(name)
                    for item in items:
                        merged.append({**item, "source": name})

        if not merged:
            return {
                "stdout": "No search results found.",
                "stderr": "No search results found.",
                "success": False,
            }

        deduped = self._dedupe_results(merged)
        backend = " + ".join(succeeded) if succeeded else "None"
        PrettyOutput.auto_print(f"🔍 Multi-source aggregation search (active sources: {backend})")
        return self._format_search_results(deduped, query, site, backend=backend)

    def _build_source_functions(
        self, query: str, site: Optional[str]
    ) -> Dict[str, Callable[[], list[Dict[str, str]]]]:
        """Build a table of search source functions participating in aggregation based on query characteristics."""
        funcs: Dict[str, Callable[[], list[Dict[str, str]]]] = {}
        # Site filter only applies to general web search, not supported by vertical APIs
        if not site:
            funcs["StackOverflow"] = lambda: self._search_stackoverflow(query)
            funcs["GitHub"] = lambda: self._search_github(query)
            funcs["360"] = lambda: self._search_360(query)
        else:
            funcs["360"] = lambda: self._search_360(f"{query} site:{site}")
        return funcs

    @staticmethod
    def _dedupe_results(results: list[Dict[str, str]]) -> list[Dict[str, str]]:
        """Deduplicate by normalized URL while preserving original priority order."""
        seen: set[str] = set()
        deduped: list[Dict[str, str]] = []
        for item in results:
            key = _normalize_url(item.get("url", ""))
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _get_ddgr_command(self) -> list[str]:
        """Get ddgr command, supports multiple invocation methods

        Returns:
            list[str]: ddgr command list
        """
        # Method 1: Try using ddgr command directly (if it's in PATH)
        ddgr_path = shutil.which("ddgr")
        if ddgr_path:
            return [ddgr_path]

        # Method 2: Try using python -m ddgr (for uv tool install etc.)
        try:
            # Check if ddgr module is available
            import importlib.util

            spec = importlib.util.find_spec("ddgr")
            if spec is not None:
                return [sys.executable, "-m", "ddgr"]
        except Exception as e:
            save_exception(
                e, module="haijunbot_tools.search_web", function="_get_ddgr_command"
            )
            pass

        # Method 3: Fall back to using ddgr directly (let subprocess handle errors)
        return ["ddgr"]

    def _search_with_ddgr(
        self,
        query: str,
        agent: Agent,
        site: Optional[str] = None,
    ) -> Dict[str, Any]:
        # pylint: disable=too-many-locals, broad-except
        """Execute web search, scrape content, and summarize results using ddgr command."""
        try:
            # Get ddgr command
            ddgr_cmd = self._get_ddgr_command()

            # Build ddgr command
            cmd = ddgr_cmd + [
                "--json",
                "--np",
                "-x",
            ]  # --np means no prompt, execute directly; -x shows full URL

            # Add site-specific search parameters
            if site:
                cmd.extend(["-w", site])

            # Add search keywords
            cmd.append(query)

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, check=False
            )

            if result.returncode != 0:
                PrettyOutput.auto_print(f"⚠️ ddgr command execution failed: {result.stderr}")
                # Fall back to Playwright
                return self._fallback_search(query=query, agent=agent, site=site)

            try:
                results = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                PrettyOutput.auto_print(f"⚠️ Failed to parse ddgr JSON output: {e}")
                # Fall back to Playwright
                return self._fallback_search(query=query, agent=agent, site=site)

            if not results:
                PrettyOutput.auto_print("⚠️ ddgr found no search results")
                # Fall back to Playwright
                return self._fallback_search(query=query, agent=agent, site=site)

            # Print search results first
            PrettyOutput.auto_print("🔍 Web Search Results")
            PrettyOutput.auto_print(f"📝 Query: {query}")
            PrettyOutput.auto_print(f"📊 Results count: {len(results)}")
            PrettyOutput.auto_print("📄 Search Summary:")

            # Collect search results and format output
            results_text = ""
            visited_urls = []

            for idx, r in enumerate(results[:10], 1):
                title = r.get("title", "")
                url = r.get("url", "")
                abstract = r.get("abstract", "")

                if title:
                    PrettyOutput.auto_print(f"  {idx}. {title}")
                    if url:
                        PrettyOutput.auto_print(f"     URL: {url}")
                        visited_urls.append(url)
                    if abstract:
                        PrettyOutput.auto_print(
                            f"     Abstract: {abstract[:150]}..."
                            if len(abstract) > 150
                            else f"     Abstract: {abstract}"
                        )

                    # Add to return text
                    results_text += f"{idx}. {title}\n"
                    if url:
                        results_text += f"   URL: {url}\n"
                    if abstract:
                        results_text += f"   Abstract: {abstract}\n"
                    results_text += "\n"

            # Add tip information
            results_text += "💡 Tip: To get detailed information, use the read_webpage tool\n"

            return {
                "stdout": results_text,
                "stderr": "",
                "success": True,
            }

        except subprocess.TimeoutExpired:
            PrettyOutput.auto_print("⚠️ ddgr command execution timed out")
            # Fall back to Playwright
            return self._fallback_search(query=query, agent=agent, site=site)
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Error during web search: {e}")
            # Fall back to Playwright
            return self._fallback_search(query=query, agent=agent, site=site)

    def _build_bing_url(self, query: str, site: Optional[str] = None) -> str:
        """Build Bing Search URL.

        Bing degrades access without login state based on query language, so select the corresponding market by language:
        Chinese queries use the default zh-CN market, other queries force en-US market to avoid matching only the first entity word.
        """
        full_query = f"{query} site:{site}" if site else query
        encoded_query = quote_plus(full_query)
        if _contains_chinese(query):
            return f"https://cn.bing.com/search?q={encoded_query}"
        return f"https://cn.bing.com/search?q={encoded_query}&mkt=en-US&setlang=en"

    def _fetch_bing_html(self, url: str, query: str) -> str:
        """Fetch Bing search page HTML using urllib to avoid launching a headless browser."""
        accept_language = (
            "zh-CN,zh;q=0.9,en;q=0.8" if _contains_chinese(query) else "en-US,en;q=0.9"
        )
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": _BROWSER_USER_AGENT,
                "Accept-Language": accept_language,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                ),
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", "ignore")

    @staticmethod
    def _parse_bing_results(html_content: str) -> list[Dict[str, str]]:
        """Parse search results from Bing search page HTML."""
        soup = BeautifulSoup(html_content, "lxml")
        results: list[Dict[str, str]] = []
        for item in soup.select("li.b_algo")[:10]:
            title_elem = item.select_one("h2 a")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            url = title_elem.get("href", "")
            if not title or not url:
                continue
            abstract_elem = item.select_one("p")
            abstract = abstract_elem.get_text(strip=True) if abstract_elem else ""
            results.append(
                {
                    "title": str(title),
                    "url": str(url),
                    "abstract": str(abstract),
                }
            )
        return results

    def _format_search_results(
        self,
        results: list[Dict[str, str]],
        query: str,
        site: Optional[str],
        backend: str = "Bing",
    ) -> Dict[str, Any]:
        """Format search results output (consistent with ddgr)."""
        PrettyOutput.auto_print(f"🔍 Web Search Results (Source: {backend})")
        PrettyOutput.auto_print(f"📝 Query: {query}")
        if site:
            PrettyOutput.auto_print(f"🌐 Site filter: {site}")
        PrettyOutput.auto_print(f"📊 Results count: {len(results)}")
        PrettyOutput.auto_print("📄 Search Summary:")

        results_text = ""
        for idx, r in enumerate(results, 1):
            title = r.get("title", "")
            url = r.get("url", "")
            abstract = r.get("abstract", "")

            PrettyOutput.auto_print(f"  {idx}. {title}")
            if url:
                PrettyOutput.auto_print(f"     URL: {url}")
            if abstract:
                PrettyOutput.auto_print(
                    f"     Abstract: {abstract[:150]}..."
                    if len(abstract) > 150
                    else f"     Abstract: {abstract}"
                )

            results_text += f"{idx}. {title}\n"
            if url:
                results_text += f"   URL: {url}\n"
            if abstract:
                results_text += f"   Abstract: {abstract}\n"
            results_text += "\n"

        results_text += "💡 Tip: To get detailed information, use the read_webpage tool\n"
        return {
            "stdout": results_text,
            "stderr": "",
            "success": True,
        }

    def _search_with_playwright(
        self,
        query: str,
        agent: Agent,
        site: Optional[str] = None,
    ) -> Dict[str, Any]:
        # pylint: disable=too-many-locals, broad-except
        """Use Bing Search as a fallback for ddgr."""
        search_url = self._build_bing_url(query, site)
        PrettyOutput.auto_print("⚠️ ddgr search failed, falling back to Bing search...")
        PrettyOutput.auto_print(f"🌐 Accessing search page: {search_url}")

        try:
            html_content = self._fetch_bing_html(search_url, query)
            results = self._parse_bing_results(html_content)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_tools.search_web",
                function="_search_with_playwright",
            )
            PrettyOutput.auto_print(f"⚠️ Direct fetch failed, falling back to Playwright: {e}")
            results = self._search_bing_with_playwright(search_url)

        if not results:
            return {
                "stdout": "No search results found.",
                "stderr": "No search results found.",
                "success": False,
            }

        return self._format_search_results(results, query, site)

    def _search_bing_with_playwright(self, search_url: str) -> list[Dict[str, str]]:
        """Access Bing with a headless browser and parse results, as fallback when direct fetching fails."""
        if not PLAYWRIGHT_AVAILABLE:
            return []
        try:
            with sync_playwright() as p:
                own_browser = not vinbox_runtime.is_vinbox()
                if own_browser:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                else:
                    # One Chromium per Vinbox: attach over CDP, never launch.
                    browser, page = vinbox_runtime.new_cdp_page(p)
                page.set_default_timeout(30000)
                page.goto(search_url, wait_until="networkidle")
                page.wait_for_selector("li.b_algo", timeout=10000)
                html_content = page.content()
                page.close()
                if own_browser:
                    browser.close()
            return self._parse_bing_results(html_content)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_tools.search_web",
                function="_search_bing_with_playwright",
            )
            PrettyOutput.auto_print(f"❌ Playwright search failed: {e}")
            return []

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the web search.

        Uses ddgr command to search the web and scrape pages for content.
        Supports site-specific search.
        """
        query = args.get("query")
        agent = args.get("agent")

        if not query:
            return {"stdout": "", "stderr": "Missing query parameter.", "success": False}

        if not isinstance(agent, Agent) or not agent.model:
            return {
                "stdout": "",
                "stderr": "Agent or Agent model not found.",
                "success": False,
            }

        # Extract optional parameters
        site = args.get("site")

        return self._search_with_ddgr(query=query, agent=agent, site=site)

    @staticmethod
    def check() -> bool:
        """Check if the tool is available."""
        return True
