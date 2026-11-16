"""Common helpers for CLI commands."""
from __future__ import annotations

import asyncio
from typing import Any, Coroutine


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine synchronously for Click."""
    return asyncio.run(coro)
