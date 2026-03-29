class LLMRateLimitError(Exception):
    def __init__(self,retry_after_seconds:int=60):
        self.retry_after_seconds=retry_after_seconds
        super().__init__(
            f"All API keys are currently rate limited."
            f"Please try again in {retry_after_seconds} seconds."
        )
class LLMAllKeysExhaustedError(Exception):
    pass
class LLMValidationError(Exception):
    pass