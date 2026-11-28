# -*- coding: utf-8 -*-
"""TrackHub track discovery source implementation

Discovery source for the open TRACK.md ecosystem hosted on
https://github.com/track-md and indexed at https://tracks.web.id.

All tracks point to a single GitHub account (track-md); each repository is
one track whose TRACK.md file carries the procedural knowledge.
"""

import aiohttp
from typing import List, Optional, Dict
from .base import ITrackSource, TrackResult


class TrackHubSource(ITrackSource):
    """TrackHub track discovery source (github.com/track-md)"""

    GITHUB_API = "https://api.github.com"
    TRACK_ACCOUNT = "track-md"
    TRACKS_WEB = "https://tracks.web.id"

    @property
    def name(self) -> str:
        return "trackhub"

    @property
    def priority(self) -> int:
        return 10  # High priority

    def _calc_quality_score(self, repo: dict) -> float:
        """Derive a 0-10 quality score from GitHub stars."""
        stars = repo.get("stargazers_count", 0) or 0
        if stars >= 10000:
            return 9.0
        elif stars >= 1000:
            return 8.0
        elif stars >= 100:
            return 7.0
        elif stars >= 10:
            return 6.0
        elif stars >= 1:
            return 5.0
        else:
            return 4.0

    async def search(self, query: str, limit: int = 20) -> List[TrackResult]:
        """Search tracks hosted under the track-md GitHub account."""
        results: List[TrackResult] = []

        if not query.strip():
            return results

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.GITHUB_API}/users/{self.TRACK_ACCOUNT}/repos",
                    params={"per_page": 100, "sort": "updated"},
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={"Accept": "application/vnd.github+json"},
                ) as resp:
                    if resp.status != 200:
                        return results

                    repos = await resp.json()
                    if not isinstance(repos, list):
                        return results

                    for repo in repos:
                        name = repo.get("name", "") or ""
                        description = repo.get("description") or ""
                        clone_url = repo.get("clone_url") or f"https://github.com/{self.TRACK_ACCOUNT}/{name}.git"
                        html_url = repo.get("html_url") or f"https://github.com/{self.TRACK_ACCOUNT}/{name}"

                        # repo_info used by the installer (git clone + TRACK.md)
                        repo_info = {
                            "clone_url": clone_url,
                            "subdir": "",
                            "owner": self.TRACK_ACCOUNT,
                            "repo": name,
                        }

                        results.append(
                            TrackResult(
                                name=name,
                                description=description,
                                download_url=clone_url,
                                source_url=html_url,
                                relevance_score=self._calc_relevance(
                                    query, f"{name} {description}"
                                ),
                                quality_score=self._calc_quality_score(repo),
                                popularity=int(repo.get("stargazers_count", 0) or 0),
                                platform=self.name,
                                author=repo.get("owner", {}).get("login", self.TRACK_ACCOUNT),
                                tags=repo.get("topics", []) or [],
                                _raw_data={**repo, "repo_info": repo_info},
                            )
                        )

        except Exception:
            # Fail silently without affecting other sources
            pass

        # Filter by relevance threshold is handled by the engine; here keep all
        # candidates whose name/description contain at least one query word.
        query_words = [w for w in query.lower().split() if len(w) > 1]
        if query_words:
            filtered = []
            for r in results:
                haystack = (r.name + " " + (r.description or "")).lower()
                if any(w in haystack for w in query_words):
                    filtered.append(r)
            if filtered:
                results = filtered

        results.sort(key=lambda r: r.composite_score, reverse=True)
        return results[:limit]