# -*- coding: utf-8 -*-
from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Tuple


class OutputHandler(ABC):
    @abstractmethod
    def handle(self, response: str, agent: Any) -> Tuple[bool, Any]:
        """Handle response data

        Args:
            response: The response string to be processed
            agent: The agent instance performing the processing

        Returns:
            Tuple[bool, Any]: A tuple containing the processing result, the first element indicates success, the second is the processed data
        """
        pass

    @abstractmethod
    def can_handle(self, response: str) -> bool:
        """Check if this handler can process the given response

        Args:
            response: The response string to be checked

        Returns:
            bool: Whether this handler can process the response
        """
        pass

    @abstractmethod
    def prompt(self) -> str:
        """Get the prompt information of the handler

        Returns:
            str: The prompt string of the handler
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Get the name of the handler

        Returns:
            str: The name string of the handler
        """
        pass
