# -*- coding: utf-8 -*-
"""Track discovery module

Provides on-demand automatic discovery, evaluation, and installation capabilities
for the global AI Track ecosystem.

Core components:
   - TrackSearchEngine: multi-source search engine
   - TrackEvaluator: LLM track evaluator
   - TrackInstaller: Git Clone installer
   - ITrackSource: discovery source abstract interface
   - TrackResult: unified result model

Usage example:
   >>> from haijunbot.haijunbot_agent.track_discovery import TrackSearchEngine, TrackEvaluator, TrackInstaller
   >>>
   >>> # Search for tracks
   >>> engine = TrackSearchEngine()
   >>> results = engine.search("PDF reader")
   >>>
   >>> # Evaluate tracks using an LLM
   >>> evaluator = TrackEvaluator(llm_client=llm_client)
   >>> evaluations = evaluator.evaluate_batch("I need to read PDF files", results)
   >>>
   >>> # Install recommended tracks
   >>> installer = TrackInstaller(rules_manager=rules_manager)
   >>> for eval_result in evaluations:
   ...     if eval_result.should_install:
   ...         installer.install(eval_result.track)
"""

from .search_engine import TrackSearchEngine
from .installer import TrackInstaller
from .track_evaluator import TrackEvaluator, TrackEvaluation
from .sources.base import ITrackSource, TrackResult

__all__ = [
    "TrackSearchEngine",
    "TrackEvaluator",
    "TrackEvaluation",
    "TrackInstaller",
    "ITrackSource",
    "TrackResult",
]
