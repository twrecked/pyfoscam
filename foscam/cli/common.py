"""Common helpers for CLI commands."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine synchronously for Click."""
    return asyncio.run(coro)
