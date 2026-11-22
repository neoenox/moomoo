from __future__ import annotations

import pytest

from moomoo_bot.retry import with_retries, with_retry_context


def test_context_preserves_original_exception_and_does_not_repeat_body() -> None:
    attempts = []
    with pytest.raises(RuntimeError, match="original failure"):
        with with_retry_context("demo", max_retries=3, base_delay=0):
            attempts.append("called")
            raise RuntimeError("original failure")
    assert attempts == ["called"]


def test_context_success_executes_once() -> None:
    attempts = []
    with with_retry_context("demo"):
        attempts.append("called")
    assert attempts == ["called"]


def test_function_decorator_retries_transient_failures() -> None:
    attempts = []

    @with_retries(max_retries=2, base_delay=0)
    def flaky() -> int:
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("temporary failure")
        return 42

    assert flaky() == 42
    assert len(attempts) == 3


def test_function_decorator_preserves_exhausted_original() -> None:
    attempts = []

    @with_retries(max_retries=1, base_delay=0)
    def always_fails() -> None:
        attempts.append(1)
        raise RuntimeError("root cause")

    with pytest.raises(RuntimeError, match="root cause"):
        always_fails()
    assert len(attempts) == 2
