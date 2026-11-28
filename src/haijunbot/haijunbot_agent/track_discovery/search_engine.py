# -*- coding: utf-8 -*-
"""Track search engine - manages multiple discovery sources using dependency injection"""

import asyncio
from typing import List, Dict, Optional
from .sources.base import ITrackSource, TrackResult


class TrackSearchEngine:
    """
    Track search engine

    Uses dependency injection to receive all discovery sources, and is responsible for:
    1. Executing searches on all sources in parallel
    2. Merging, deduplicating, and sorting results
    3. Filtering out low-quality results
    """

    def __init__(
        self,
        sources: Optional[List[ITrackSource]] = None,
        min_relevance: float = 0.5,
        min_quality: float = 5.0,
        max_results: int = 20,
    ):
        """
        Args:
            sources: List of discovery sources (dependency injection)
            min_relevance: Minimum relevance threshold
            min_quality: Minimum quality score threshold
            max_results: Maximum number of results to return
        """
        # Dependency injection: discovery sources
        self.sources = sources or self._default_sources()

        # Configuration
        self.min_relevance = min_relevance
        self.min_quality = min_quality
        self.max_results = max_results

    def _default_sources(self) -> List[ITrackSource]:
        """Default discovery sources (may be overridden as needed)"""
        from .sources.trackhub import TrackHubSource

        return [
            TrackHubSource(),  # High priority
        ]

    async def search_async(self, query: str) -> List[TrackResult]:
        """
        Asynchronously search all sources

        Args:
            query: Search keywords

        Returns:
            List of results sorted by composite score
        """
        # 1. Execute searches on all sources in parallel
        tasks = [source.search(query) for source in self.sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 2. Merge results (filter out exceptions)
        all_tracks: List[TrackResult] = []
        for result in results:
            if isinstance(result, list):
                all_tracks.extend(result)
            elif isinstance(result, Exception):
                # Log but do not interrupt
                pass

        # 3. Deduplicate (by name)
        seen = set()
        unique_tracks = []
        for track in all_tracks:
            if track.name not in seen:
                seen.add(track.name)
                unique_tracks.append(track)

        # 4. Filter out low-quality results
        filtered = [
            s
            for s in unique_tracks
            if s.relevance_score >= self.min_relevance
            and s.quality_score >= self.min_quality
        ]

        # 5. Sort by composite score
        filtered.sort(key=lambda s: s.composite_score, reverse=True)

        # 6. Limit the number of results returned
        return filtered[: self.max_results]

    def search(self, query: str) -> List[TrackResult]:
        """Synchronous search wrapper"""
        return asyncio.run(self.search_async(query))

    async def health_check(self) -> Dict[str, bool]:
        """Check the availability of all sources"""
        tasks = {source.name: source.is_available() for source in self.sources}

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        return {name: (result is True) for name, result in zip(tasks.keys(), results)}

    def add_source(self, source: ITrackSource) -> None:
        """Dynamically add a discovery source"""
        self.sources.append(source)
        # Sort by priority
        self.sources.sort(key=lambda s: s.priority)

    def remove_source(self, source_name: str) -> bool:
        """Remove a discovery source"""
        for i, source in enumerate(self.sources):
            if source.name == source_name:
                del self.sources[i]
                return True
        return False
