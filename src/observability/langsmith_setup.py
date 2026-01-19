"""LangSmith setup and observability utilities."""

import logging
import os
from functools import wraps
from typing import Any, Callable

from langsmith import Client, traceable

logger = logging.getLogger(__name__)

_langsmith_client: Client | None = None


def setup_langsmith(
    api_key: str | None = None,
    project: str = "python-mcp-agent",
    tracing_enabled: bool = True,
) -> bool:
    """Setup LangSmith for observability.

    Args:
        api_key: LangSmith API key. If None, uses LANGSMITH_API_KEY env var.
        project: Project name for organizing traces.
        tracing_enabled: Whether to enable tracing.

    Returns:
        True if setup was successful, False otherwise.
    """
    global _langsmith_client

    if api_key:
        os.environ["LANGSMITH_API_KEY"] = api_key

    os.environ["LANGSMITH_PROJECT"] = project
    os.environ["LANGSMITH_TRACING"] = str(tracing_enabled).lower()

    # Check if API key is available
    if not os.environ.get("LANGSMITH_API_KEY"):
        logger.warning(
            "LANGSMITH_API_KEY not set. Tracing will be disabled. "
            "Get your API key at https://smith.langchain.com/"
        )
        return False

    try:
        _langsmith_client = Client()
        logger.info(f"LangSmith initialized for project: {project}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize LangSmith: {e}")
        return False


def get_langsmith_client() -> Client | None:
    """Get the LangSmith client instance."""
    return _langsmith_client


def trace_agent_run(name: str | None = None):
    """Decorator to trace agent runs in LangSmith.

    Args:
        name: Optional name for the trace.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            trace_name = name or func.__name__

            # Use LangSmith traceable decorator
            traced_func = traceable(name=trace_name)(func)
            return await traced_func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            trace_name = name or func.__name__
            traced_func = traceable(name=trace_name)(func)
            return traced_func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if hasattr(func, "__wrapped__"):
            return async_wrapper
        return async_wrapper if asyncio_iscoroutinefunction(func) else sync_wrapper

    return decorator


def asyncio_iscoroutinefunction(func: Callable) -> bool:
    """Check if a function is a coroutine function."""
    import asyncio

    return asyncio.iscoroutinefunction(func)


def log_trace_url(run_id: str) -> None:
    """Log the URL to view a trace in LangSmith.

    Args:
        run_id: The run ID from LangSmith.
    """
    project = os.environ.get("LANGSMITH_PROJECT", "default")
    url = f"https://smith.langchain.com/o/default/projects/p/{project}/r/{run_id}"
    logger.info(f"View trace at: {url}")
