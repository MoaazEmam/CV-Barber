from abc import ABC, abstractmethod
from pydantic import BaseModel


class BaseLLMClient(ABC):
    """
    Abstract base for all LLM provider clients.
    Every provider must implement a single method: complete().
    Parser and scorer depend only on this interface.
    """

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a system + user prompt pair, return the raw response string.
        All providers reduce to this interface regardless of their SDK.
        """
        ...

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Convenience wrapper that appends a JSON reminder to the system prompt.
        Providers may override this if they have native JSON mode support.
        """
        enforced_system = (
            f"{system_prompt}\n\n"
            "IMPORTANT: You must respond with valid JSON only. "
            "No markdown, no code fences, no explanation. Raw JSON only."
        )
        return self.complete(enforced_system, user_prompt)