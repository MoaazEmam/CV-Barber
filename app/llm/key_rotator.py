import datetime
import threading
import time
from datetime import datetime

import pytz

from app.config import settings as default_settings
from app.llm.exceptions import LLMRateLimitError, LLMAllKeysExhaustedError

PACIFIC = pytz.timezone("US/Pacific")


class KeyState:
    def __init__(self, key: str):
        self.key = key
        self.is_exhausted_until: float = 0
        self.daily_exhausted_at: float | None = False

    def mark_daily_exhausted(self) -> None:
        self.daily_exhausted_at = time.time()

    def _should_reset_daily(self) -> bool:
        if not self.daily_exhausted_at:
            return False

        exhausted_dt = datetime.fromtimestamp(self.daily_exhausted_at, PACIFIC)
        now = datetime.now(PACIFIC)

        return now.date() > exhausted_dt.date()

    def is_available(self) -> bool:
        if self.daily_exhausted_at and self._should_reset_daily():
            self.reset_daily()

        return (time.time() >= self.is_exhausted_until) and not self.daily_exhausted_at

    def mark_rate_limited(self, retry_after_seconds: int = 60) -> None:
        self.is_exhausted_until = time.time() + retry_after_seconds

    def reset_daily(self) -> None:
        self.daily_exhausted_at = None
        self.is_exhausted_until = 0.0


class KeyRotator:
    def __init__(self, keys: list[str]):
        if not keys:
            raise ValueError("At least one API key is required.")
        self._states_map = {key: KeyState(key) for key in keys}
        self._index = 0
        self._lock = threading.Lock()

    def get_key(self) -> str:
        with self._lock:
            available = self._get_available_states()
            if not available:
                self._raise_unavailable_error()
            return self._select_next(available)

    def _get_available_states(self) -> list[KeyState]:
        return [s for s in self._states_map.values() if s.is_available()]

    def _raise_unavailable_error(self) -> None:
        temporarily_limited = [
            s
            for s in self._states_map.values()
            if not s.daily_exhausted_at and not s.is_available()
        ]
        if temporarily_limited:
            soonest = min(s.is_exhausted_until for s in temporarily_limited)
            retry_in = max(1, int(soonest - time.time()))
            raise LLMRateLimitError(retry_after_seconds=retry_in)

        raise LLMAllKeysExhaustedError(
            "All API keys have hit their daily limit. "
            "Quota resets at midnight Pacific Time."
        )

    def _select_next(self, available: list[KeyState]) -> str:
        state = available[self._index % len(available)]
        self._index = (self._index + 1) % len(available)
        return state.key

    def mark_rate_limited(self, key: str, retry_after_seconds: int = 60) -> None:
        with self._lock:
            state = self._states_map.get(key, "")
            if state:
                state.mark_rate_limited(retry_after_seconds)
                return

    def mark_daily_exhausted(self, key: str) -> None:
        with self._lock:
            state = self._states_map.get(key, "")
            if state:
                state.mark_daily_exhausted()
                return


# Module-level singleton used by GeminiClient.
# Falls back to a placeholder key so the object can always be constructed;
# GeminiClient will only be instantiated by the factory when real keys are present.
_gemini_keys = default_settings.get_all_gemini_keys() or ["__placeholder__"]
_rotator = KeyRotator(_gemini_keys)
