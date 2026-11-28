"""Context recommendation data structures and basic utilities.

Retains the data structures and formatting methods for recommendation results.
"""

from dataclasses import dataclass
from typing import List

from .symbol_extractor import Symbol


@dataclass
class ContextRecommendation:
    """Context recommendation result

    Recommends the location information of symbols in files.
    """

    recommended_symbols: List[Symbol]  # The recommended list of symbols (including file paths and line numbers)
