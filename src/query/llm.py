"""Groq chat client. The API key is read once and never logged."""

from __future__ import annotations

import logging
import time

from src.config import ConfigurationError, Settings

logger = logging.getLogger(__name__)


class LLMAuthError(Exception):
    """Raised on HTTP 401. Callers must not retry."""


class LLMUnavailable(Exception):
    """Raised when a retryable Groq failure (429, 5xx, timeout) is exhausted."""


class LLMTruncated(LLMUnavailable):
    """Raised when the model stopped at max_tokens, so the text is incomplete.

    Reasoning models bill their deliberation against the same budget as the
    answer, so a run can hit the cap before writing a single sentence. The
    answer is then unusable and must never reach the validators.
    """


class LLMRequestError(Exception):
    """Raised on a non-retryable Groq failure other than 401."""


class GroqClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        key = settings.api_key
        from groq import Groq

        self._client = Groq(api_key=key, timeout=settings.llm_timeout_s, max_retries=0)
        self._budget = settings.llm_max_tokens

    def complete(self, messages: list[dict[str, str]]) -> str:
        delays = (1.0, 2.0)
        last_error: Exception | None = None
        base = self.settings.llm_max_tokens
        for attempt in range(3):
            # Each retry buys more room: a truncated run is usually a reasoning
            # run that needed a larger ceiling, not a bad request.
            self._budget = base * (1 + attempt)
            try:
                return self._complete_once(messages)
            except LLMAuthError:
                raise
            except LLMUnavailable as exc:
                # Keep the concrete type so a caller can still tell an exhausted
                # budget apart from a 429 once every attempt has been used up.
                last_error = exc
                if attempt == 2:
                    break
                time.sleep(delays[attempt])
        logger.info("groq request failed status=%s", last_error)
        raise last_error if last_error else LLMUnavailable("unavailable")

    def _complete_once(self, messages: list[dict[str, str]]) -> str:
        from groq import APIStatusError, APITimeoutError, APIConnectionError

        try:
            response = self._client.chat.completions.create(
                model=self.settings.llm_model,
                messages=messages,
                temperature=self.settings.llm_temperature,
                max_tokens=self._budget,
            )
        except APIStatusError as exc:
            status = getattr(exc, "status_code", 0)
            if status == 401:
                raise LLMAuthError("unauthorized") from None
            if status == 429 or status >= 500:
                raise LLMUnavailable(str(status)) from None
            raise LLMRequestError(str(status)) from None
        except (APITimeoutError, APIConnectionError):
            raise LLMUnavailable("timeout") from None
        choice = response.choices[0]
        text = choice.message.content or ""
        if choice.finish_reason == "length" or not text.strip():
            # finish_reason "length" means the last sentence is cut in half, and
            # an empty body means the budget went entirely to reasoning. Both
            # are truncation for our purposes.
            raise LLMTruncated(f"truncated at {self._budget} tokens")
        return text
