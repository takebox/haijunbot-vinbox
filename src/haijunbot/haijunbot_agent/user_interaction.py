# -*- coding: utf-8 -*-
"""
UserInteractionHandler: Abstracts user interaction (multiline input and confirmation) logic for easy replacement with TUI/WebUI in the future.

Phase 1 (minimal changes):
- Only provides wrapper, does not directly modify existing Agent calls
- Subsequent steps will be integrated as bypass in Agent, maintaining backward compatibility
"""

from typing import Callable


class UserInteractionHandler:
    def __init__(
        self,
        multiline_inputer: Callable[..., str],
        confirm_func: Callable[[str, bool], bool],
    ) -> None:
        """
        Args:
          - multiline_inputer: Function providing multiline input, prefers (tip, print_on_empty=bool), compatible with (tip) only
          - confirm_func: User confirmation function (tip: str, default: bool) -> bool
        """
        self._multiline_inputer = multiline_inputer
        self._confirm = confirm_func

    def multiline_input(self, tip: str, print_on_empty: bool) -> str:
        """
        Multiline input wrapper: supports two signatures
        1) func(tip, print_on_empty=True/False)
        2) func(tip)
        """
        try:
            return self._multiline_inputer(tip, print_on_empty=print_on_empty)
        except TypeError:
            return self._multiline_inputer(tip)

    def confirm(self, tip: str, default: bool = True) -> bool:
        """
        User confirmation wrapper, delegates directly
        """
        return self._confirm(tip, default)
