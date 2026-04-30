from __future__ import annotations

import math


class TokenEstimator:
    """Token estimator with a tiktoken fast-path and a deterministic fallback."""

    def __init__(self) -> None:
        self._encoding = None
        try:
            import tiktoken  # type: ignore

            self._encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._encoding = None

    def count(self, text: str | None) -> int:
        if not text:
            return 0
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        return max(1, math.ceil(len(text) / 4))
