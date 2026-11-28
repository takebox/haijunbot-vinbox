# -*- coding: utf-8 -*-
"""Track evaluator - uses an LLM to evaluate the relevance and value of remote tracks"""

import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass
from .sources.base import TrackResult


@dataclass
class TrackEvaluation:
    """Track evaluation result"""

    track: TrackResult
    score: float  # 0-10 score
    recommendation: str  # Reason for the recommendation
    concerns: List[str]  # Potential issues
    should_install: bool  # Whether installation is recommended


class TrackEvaluator:
    """
    Uses an LLM to evaluate the relevance and value of remote tracks

    Evaluation dimensions:
    1. Relevance: how well the track matches the task description
    2. Practicality: whether the track can solve a real problem
    3. Safety: whether the track poses potential risks
    4. Completeness: whether the track documentation and quality are reliable
    """

    EVALUATION_PROMPT = """You are a professional AI track evaluation expert. Please evaluate whether the following track is suitable for solving the user's task.

## User task description
{task_description}

## Track to be evaluated
- Name: {track_name}
- Description: {track_description}
- Source platform: {platform}
- Author: {author}
- Tags: {tags}
- Quality score: {quality_score}/10
- Popularity (stars): {popularity}

## Evaluation requirements
Please evaluate along the following dimensions (each scored 0-10):
1. **Relevance**: how well the track matches the task description
2. **Practicality**: whether the track can actually solve the problem
3. **Safety**: whether the track poses potential risks (such as executing dangerous commands, accessing sensitive data, etc.)
4. **Completeness**: whether the track documentation is complete and the examples are clear

## Output format
Please output strictly in the following JSON format:
{{
    "scores": {{
        "relevance": 0-10,
        "practicality": 0-10,
        "safety": 0-10,
        "completeness": 0-10
    }},
    "overall_score": 0-10,
    "recommendation": "One sentence stating whether installation is recommended and why",
    "concerns": ["List of potential issues; an empty array if there are none"],
    "should_install": true/false
}}

## Evaluation criteria
- overall_score >= 7.0 and should_install = true: strongly recommend installation
- overall_score >= 5.0 and < 7.0: may consider installation
- overall_score < 5.0 or safety < 6.0: do not recommend installation

Please begin the evaluation:"""

    def __init__(self, llm_client: Any, model: str = "default"):
        """
        Args:
            llm_client: LLM client instance (must support the chat/completions interface)
            model: Name of the model to use
        """
        self.llm_client = llm_client
        self.model = model

    async def evaluate_async(
        self, task_description: str, track: TrackResult
    ) -> TrackEvaluation:
        """
        Asynchronously evaluate a single track

        Args:
            task_description: Task description
            track: The track to be evaluated

        Returns:
            The TrackEvaluation result
        """
        try:
            # Build the evaluation prompt
            prompt = self.EVALUATION_PROMPT.format(
                task_description=task_description,
                track_name=track.name,
                track_description=track.description or "No description",
                platform=track.platform,
                author=track.author or "Unknown",
                tags=", ".join(track.tags) if track.tags else "None",
                quality_score=track.quality_score,
                popularity=track.popularity,
            )

            # Call the LLM
            response = await self._call_llm(prompt)

            # Parse the response
            evaluation_data = self._parse_response(response)

            return TrackEvaluation(
                track=track,
                score=evaluation_data.get("overall_score", 0),
                recommendation=evaluation_data.get("recommendation", ""),
                concerns=evaluation_data.get("concerns", []),
                should_install=evaluation_data.get("should_install", False),
            )

        except Exception as e:
            # Return a conservative evaluation on failure
            return TrackEvaluation(
                track=track,
                score=3.0,
                recommendation=f"Evaluation failed: {str(e)}",
                concerns=["LLM evaluation error; manual review recommended"],
                should_install=False,
            )

    async def evaluate_batch_async(
        self, task_description: str, tracks: List[TrackResult], max_concurrent: int = 3
    ) -> List[TrackEvaluation]:
        """
        Batch-evaluate tracks (concurrent execution)

        Args:
            task_description: Task description
            tracks: List of tracks to be evaluated
            max_concurrent: Maximum concurrency

        Returns:
            List of evaluation results (sorted in descending order by score)
        """
        # Limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def evaluate_with_semaphore(track: TrackResult) -> TrackEvaluation:
            async with semaphore:
                return await self.evaluate_async(task_description, track)

        tasks = [evaluate_with_semaphore(track) for track in tracks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exception results
        evaluations = [r for r in results if isinstance(r, TrackEvaluation)]

        # Sort in descending order by score
        evaluations.sort(key=lambda e: e.score, reverse=True)

        return evaluations

    def evaluate(self, task_description: str, track: TrackResult) -> TrackEvaluation:
        """Synchronous evaluation wrapper"""
        return asyncio.run(self.evaluate_async(task_description, track))

    def evaluate_batch(
        self, task_description: str, tracks: List[TrackResult], max_concurrent: int = 3
    ) -> List[TrackEvaluation]:
        """Synchronous batch evaluation wrapper"""
        return asyncio.run(
            self.evaluate_batch_async(task_description, tracks, max_concurrent)
        )

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM to obtain the evaluation result"""
        try:
            # Try the standard OpenAI-style interface
            if hasattr(self.llm_client, "chat") and hasattr(
                self.llm_client.chat, "completions"
            ):
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional AI track evaluation expert responsible for evaluating the relevance and value of tracks.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,  # Reduce randomness, improve consistency
                    max_tokens=500,
                )
                return response.choices[0].message.content

            # Try calling the create method directly
            elif hasattr(self.llm_client, "create"):
                response = self.llm_client.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional AI track evaluation expert.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=500,
                )
                return response.choices[0].message.content

            else:
                raise ValueError("Unsupported interface type for the LLM client")

        except Exception as e:
            raise RuntimeError(f"LLM call failed: {str(e)}")

    def _parse_response(self, response: str) -> Dict:
        """Parse the LLM response (supports JSON and natural language)"""
        import json
        import re

        # Try to extract JSON
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: try to parse a natural language response
        # Default conservative evaluation
        return {
            "overall_score": 5.0,
            "recommendation": response[:200] if response else "Unable to parse the evaluation result",
            "concerns": ["Abnormal LLM response format"],
            "should_install": False,
        }
