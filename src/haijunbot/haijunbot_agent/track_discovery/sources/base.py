# -*- coding: utf-8 -*-
"""Track discovery source abstract interface and data model"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TrackResult:
    """Track discovery result (unified data model)"""

    # Core fields
    name: str
    description: str
    download_url: str
    source_url: str

    # Scoring fields
    relevance_score: float = 0.0  # Relevance (0-1)
    quality_score: float = 0.0  # Quality score (0-10)
    popularity: int = 0  # Popularity (stars/downloads)

    # Metadata
    platform: str = "unknown"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    license: Optional[str] = None

    # Internal fields
    _raw_data: Dict[str, Any] = field(default_factory=dict, repr=False)
    _fetched_at: datetime = field(default_factory=datetime.now, repr=False)

    @property
    def composite_score(self) -> float:
        """Composite score = relevance*60% + quality*30% + popularity*10%"""
        popularity_normalized = min(self.popularity / 100000, 1.0)  # Normalize to 0-1
        return (
            self.relevance_score * 0.6
            + (self.quality_score / 10.0) * 0.3
            + popularity_normalized * 0.1
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dict (for serialization)"""
        return {
            "name": self.name,
            "description": self.description,
            "download_url": self.download_url,
            "source_url": self.source_url,
            "relevance_score": self.relevance_score,
            "quality_score": self.quality_score,
            "popularity": self.popularity,
            "platform": self.platform,
            "author": self.author,
            "tags": self.tags,
            "license": self.license,
            "composite_score": self.composite_score,
        }


class ITrackSource(ABC):
    """Track discovery source abstract base class"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Source name (unique identifier)"""
        pass

    @property
    def priority(self) -> int:
        """Priority (the smaller the number, the higher the priority; default 100)"""
        return 100

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> List[TrackResult]:
        """
        Search for tracks

        Args:
            query: Search keywords
            limit: Return count limit

        Returns:
            List of track results
        """
        pass

    async def is_available(self) -> bool:
        """Check whether the service is available (health check)"""
        try:
            # Default implementation: attempt one empty search
            await self.search("", limit=1)
            return True
        except Exception:
            return False

    def _calc_relevance(self, query: str, text: str) -> float:
        """Calculate relevance (subclasses may override)"""
        if not text:
            return 0.0

        query_words = set(query.lower().split())
        text_lower = text.lower()

        matches = sum(1 for word in query_words if word in text_lower)
        return matches / len(query_words) if query_words else 0.0
