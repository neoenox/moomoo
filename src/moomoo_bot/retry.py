"""Retry utilities for transient failures.

Purpose: Centralize retry logic with exponential backoff for broker API calls.
Related: broker/opend.py, broker/paper.py, notify.py.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default retry configurations
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_MAX_DELAY = 30.0

# Transient exceptions that should be retried
TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    RuntimeError,
    OSError,
)


def with_retries(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    max_delay: float = DEFAULT_MAX_DELAY,
    exceptions: tuple[type[Exception], ...] = TRANSIENT_EXCEPTIONS,
    retry_on_result: Callable[[T], bool] | None = None,
    logger_extra: dict | None = None,
    raise_on_failure: type[Exception] | None = None,
):
    """Decorator to retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (excluding initial call)
        base_delay: Initial delay in seconds before first retry
        backoff_factor: Multiplier for delay after each failure
        max_delay: Maximum delay between retries
        exceptions: Exception types to catch and retry on
        retry_on_result: Optional predicate to determine if result should be retried
        logger_extra: Optional dict to include in log records
        raise_on_failure: Optional exception class to raise when all retries exhausted.
                        If None, the last caught exception is re-raised.

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            delay = base_delay

            for attempt in range(1, max_retries + 2):  # +2: initial + retries
                try:
                    result = func(*args, **kwargs)
                    if retry_on_result is not None and retry_on_result(result):
                        if attempt < max_retries + 1:
                            logger.warning(
                                "Retry triggered by result (attempt %d/%d)",
                                attempt,
                                max_retries + 1,
                                extra=logger_extra or {},
                            )
                            time.sleep(min(delay, max_delay))
                            delay *= backoff_factor
                            continue
                    return result
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries + 1:
                        logger.warning(
                            "%s attempt %d/%d failed: %s; retrying in %.1fs",
                            func.__name__,
                            attempt,
                            max_retries + 1,
                            exc,
                            min(delay, max_delay),
                            extra=logger_extra or {},
                        )
                        time.sleep(min(delay, max_delay))
                        delay *= backoff_factor
                        continue
                    # Exhausted retries
                    logger.error(
                        "%s failed after %d attempts: %s",
                        func.__name__,
                        attempt,
                        exc,
                        extra=logger_extra or {},
                    )
                    if raise_on_failure is not None:
                        raise raise_on_failure(
                            f"{func.__name__} failed after {attempt} attempts: {exc}"
                        ) from exc
                    raise

            # Should not reach here, but just in case
            if last_exc:
                if raise_on_failure is not None:
                    raise raise_on_failure(
                        f"{func.__name__} failed: {last_exc}"
                    ) from last_exc
                raise last_exc
            return None  # type: ignore[unreachable]

        return wrapper

    return decorator


def with_retry_context(
    context_name: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
):
    """Log failures from a *single* with-block execution.

    A contextmanager cannot re-execute the body of a `with` statement; yielding
    again after an exception masks the original error with contextlib's
    "generator didn't stop after throw()" RuntimeError. Use `@with_retries(...)`
    on a callable when retrying its execution is required.

    Retry parameters are retained for compatibility with existing callers but
    cannot apply to a contextmanager's body.
    """
    from contextlib import contextmanager

    @contextmanager
    def retry_context():
        try:
            yield
        except TRANSIENT_EXCEPTIONS:
            logger.exception(
                "%s failed inside a context manager; use with_retries for retry",
                context_name,
            )
            raise

    return retry_context()
