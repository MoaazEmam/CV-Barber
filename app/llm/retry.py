import asyncio
import functools

import structlog

from app.llm.exceptions import LLMValidationError

logger = structlog.get_logger()


def async_retry_llm(max_retries: int = 3):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except LLMValidationError as e:
                    if attempt == max_retries - 1:
                        raise
                    wait = 2 ** attempt
                    logger.warning(
                        "llm_validation_retry",
                        attempt=attempt + 1,
                        wait=wait,
                        error=str(e),
                    )
                    await asyncio.sleep(wait)
        return wrapper
    return decorator
