# -*- coding: utf-8 -*-
"""search_web tool multi-source aggregation and helper function unit tests."""

import time
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from haijunbot.haijunbot_tools.search_web import SearchWebTool
from haijunbot.haijunbot_tools.search_web import _is_anti_spider_page
from haijunbot.haijunbot_tools.search_web import _normalize_url


class TestNormalizeUrl:
    """URL normalization deduplication key tests."""

    def test_strips_query_and_trailing_slash(self):
        assert _normalize_url("https://Example.com/a/b/?x=1") == _normalize_url(
            "https://example.com/a/b"
        )

    def test_empty_returns_empty(self):
        assert _normalize_url("") == ""

    def test_distinct_paths_differ(self):
        assert _normalize_url("https://a.com/x") != _normalize_url("https://a.com/y")


class TestAntiSpiderDetection:
    """Anti-spider verification page detection tests."""

    @pytest.mark.parametrize(
        "content",
        ["Access anomaly page", "Please enter verification code", "Security verification", "antispider"],
    )
    def test_detects_markers(self, content):
        assert _is_anti_spider_page(content) is True

    def test_normal_page_not_detected(self):
        assert _is_anti_spider_page("<html>Normal search results</html>") is False


class TestSearch360:
    """360 search source parsing and error tolerance tests."""

    def test_parses_results(self):
        html = """
        <html><body>
          <li><h3><a href="https://example.com/1">Rust Ownership</a></h3>
              <p>Summary text one</p></li>
          <li><h3><a href="https://example.com/2">Borrow Checker</a></h3>
              <p>Summary text two</p></li>
        </body></html>
        """
        tool = SearchWebTool()
        with patch("haijunbot.haijunbot_tools.search_web.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                text=html, status_code=200, url="https://example.com/1"
            )
            mock_get.return_value.raise_for_status = MagicMock()
            results = tool._search_360("rust", limit=5)

        assert len(results) == 2
        assert results[0]["title"] == "Rust Ownership"
        assert results[0]["url"] == "https://example.com/1"
        assert results[0]["abstract"] == "Summary text one"

    def test_returns_empty_on_anti_spider(self):
        tool = SearchWebTool()
        with patch("haijunbot.haijunbot_tools.search_web.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                text="Access anomaly page Please enter verification code", status_code=200
            )
            mock_get.return_value.raise_for_status = MagicMock()
            assert tool._search_360("rust") == []

    def test_returns_empty_on_exception(self):
        tool = SearchWebTool()
        with patch(
            "haijunbot.haijunbot_tools.search_web.requests.get",
            side_effect=Exception("boom"),
        ):
            assert tool._search_360("rust") == []

    def test_respects_limit(self):
        html = (
            "<html><body>"
            + "".join(
                f'<li><h3><a href="https://e.com/{i}">T{i}</a></h3></li>'
                for i in range(10)
            )
            + "</body></html>"
        )
        tool = SearchWebTool()
        with patch("haijunbot.haijunbot_tools.search_web.requests.get") as mock_get:
            mock_get.return_value = MagicMock(text=html, status_code=200)
            mock_get.return_value.raise_for_status = MagicMock()
            assert len(tool._search_360("x", limit=3)) == 3


class TestDedupeResults:
    """Aggregation result deduplication tests."""

    def test_dedupes_same_normalized_url(self):
        results = [
            {"title": "A", "url": "https://x.com/p?u=1", "abstract": ""},
            {"title": "A2", "url": "https://x.com/p", "abstract": ""},
            {"title": "B", "url": "https://x.com/q", "abstract": ""},
        ]
        deduped = SearchWebTool._dedupe_results(results)
        assert len(deduped) == 2
        assert deduped[0]["title"] == "A"
        assert deduped[1]["title"] == "B"

    def test_skips_empty_url(self):
        results = [{"title": "A", "url": "", "abstract": ""}]
        assert SearchWebTool._dedupe_results(results) == []


class TestSearchMultiSource:
    """Multi-source aggregation dispatch tests."""

    def test_merges_and_marks_sources(self):
        tool = SearchWebTool()
        with (
            patch.object(
                tool,
                "_search_stackoverflow",
                return_value=[
                    {"title": "SO", "url": "https://so.com/1", "abstract": ""}
                ],
            ),
            patch.object(
                tool,
                "_search_github",
                return_value=[
                    {"title": "GH", "url": "https://gh.com/1", "abstract": ""}
                ],
            ),
            patch.object(tool, "_search_360", return_value=[]),
        ):
            result = tool._search_multi_source("rust")

        assert result["success"] is True
        assert "SO" in result["stdout"]
        assert "GH" in result["stdout"]

    def test_single_source_failure_is_tolerated(self):
        tool = SearchWebTool()
        with (
            patch.object(tool, "_search_stackoverflow", side_effect=Exception("fail")),
            patch.object(
                tool,
                "_search_github",
                return_value=[
                    {"title": "GH", "url": "https://gh.com/1", "abstract": ""}
                ],
            ),
            patch.object(tool, "_search_360", return_value=[]),
        ):
            result = tool._search_multi_source("rust")

        assert result["success"] is True
        assert "GH" in result["stdout"]

    def test_results_ordered_by_source_priority(self):
        """Result order follows source priority (StackOverflow > GitHub > 360), independent of completion order."""
        tool = SearchWebTool()

        def slow_so(*_args, **_kwargs):
            time.sleep(0.05)
            return [
                {
                    "title": "StackOverflow result",
                    "url": "https://so.com/1",
                    "abstract": "",
                }
            ]

        with (
            patch.object(tool, "_search_stackoverflow", side_effect=slow_so),
            patch.object(
                tool,
                "_search_github",
                return_value=[
                    {"title": "GitHub result", "url": "https://gh.com/1", "abstract": ""}
                ],
            ),
            patch.object(
                tool,
                "_search_360",
                return_value=[
                    {"title": "360 result", "url": "https://360.com/1", "abstract": ""}
                ],
            ),
        ):
            result = tool._search_multi_source("rust")

        stdout = result["stdout"]
        assert stdout.index("StackOverflow result") < stdout.index("GitHub result")
        assert stdout.index("GitHub result") < stdout.index("360 result")

    def test_all_sources_empty_returns_failure(self):
        tool = SearchWebTool()
        with (
            patch.object(tool, "_search_stackoverflow", return_value=[]),
            patch.object(tool, "_search_github", return_value=[]),
            patch.object(tool, "_search_360", return_value=[]),
        ):
            result = tool._search_multi_source("rust")

        assert result["success"] is False


class TestFallbackSearch:
    """ddgr fallback entry tests."""

    def test_uses_aggregation_when_available(self):
        tool = SearchWebTool()
        with patch.object(
            tool,
            "_search_multi_source",
            return_value={"stdout": "Aggregated results", "stderr": "", "success": True},
        ):
            result = tool._fallback_search("rust", agent=MagicMock())
        assert result["stdout"] == "Aggregated results"

    def test_falls_back_to_bing_when_aggregation_empty(self):
        tool = SearchWebTool()
        with (
            patch.object(tool, "_search_multi_source", return_value={"success": False}),
            patch.object(
                tool,
                "_search_with_playwright",
                return_value={"stdout": "Bing results", "stderr": "", "success": True},
            ) as mock_bing,
        ):
            result = tool._fallback_search("rust", agent=MagicMock())

        assert result["stdout"] == "Bing results"
        mock_bing.assert_called_once()
