"""
InstrumentedGraph -- StateGraph subclass that intercepts add_node()
to wrap every node function with before/after/error hooks and middleware.

Two extension points:
  - Interceptor: observe-only (logging, metrics, tracing). Cannot modify results.
  - Middleware: transform node results (state mediation, envelope routing).
    Middleware.transform() receives the node result and returns a (possibly modified) result.
    Middleware chains run in registration order after interceptor.after() hooks.

Design principles (from READ_THIS_FIRST.md):
  - functools.wraps preserves __name__, __doc__, __module__, __qualname__, __wrapped__
  - Defensive try/except around every interceptor hook -- broken interceptor cannot crash the graph
  - Broken middleware DOES propagate (it modifies data; silent failure would corrupt state)
  - Thread-safe by convention -- interceptors key by (node_name, thread_id) if they hold state
  - Forward-compatible add_node(**kwargs) -- passes through any future LangGraph parameters
"""

from __future__ import annotations

import functools
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Sequence

from langgraph.graph import StateGraph

logger = logging.getLogger(__name__)


# -- Interceptor protocol (observe only) ------------------------------

class Interceptor(ABC):
    """
    Base class for node-level cross-cutting concerns (observe only).

    Subclass and override the hooks you need.
    All hooks receive the node name so interceptors can be stateless.
    Interceptors CANNOT modify the node result -- use Middleware for that.
    """

    @abstractmethod
    def before(self, node_name: str, state: Any) -> None:
        """Called before the node function executes."""
        ...

    @abstractmethod
    def after(self, node_name: str, state: Any, result: Any) -> None:
        """Called after the node function returns successfully."""
        ...

    @abstractmethod
    def on_error(self, node_name: str, state: Any, error: Exception) -> None:
        """Called when the node function raises."""
        ...


# -- Middleware protocol (transform results) --------------------------

class Middleware(ABC):
    """
    Base class for node-level result transformers.

    Unlike Interceptor, Middleware CAN modify the node's return value.
    Use this for state mediation, envelope routing, result augmentation.

    Middleware errors propagate (not swallowed) because silent data
    corruption is worse than a loud failure.
    """

    @abstractmethod
    def transform(self, node_name: str, state: Any, result: Any) -> Any:
        """
        Transform the node result before it is applied to state.

        Args:
            node_name: Name of the node that produced the result.
            state: The current graph state (read-only by convention).
            result: The node's return value (dict for state updates).

        Returns:
            The (possibly modified) result dict.
        """
        ...


# -- InstrumentedGraph ------------------------------------------------

class InstrumentedGraph(StateGraph):
    """
    Drop-in replacement for StateGraph that wraps every node with
    interceptor hooks and middleware.

    Usage:
        graph = InstrumentedGraph(
            MyState,
            interceptors=[LoggingInterceptor()],
            middleware=[StateMediator(rules)],
        )
        graph.add_node("my_node", my_func)   # automatically instrumented
    """

    def __init__(
        self,
        state_schema: Any,
        *,
        interceptors: Sequence[Interceptor] | None = None,
        middleware: Sequence[Middleware] | None = None,
        **kwargs: Any,
    ):
        super().__init__(state_schema, **kwargs)
        self._interceptors: list[Interceptor] = list(interceptors or [])
        self._middleware: list[Middleware] = list(middleware or [])

    # -- public API ---------------------------------------------------

    def add_interceptor(self, interceptor: Interceptor) -> None:
        """Add an interceptor after construction."""
        self._interceptors.append(interceptor)

    def add_middleware(self, mw: Middleware) -> None:
        """Add a middleware after construction."""
        self._middleware.append(mw)

    def add_node(self, node: str, action: Callable | None = None, **kwargs: Any) -> None:
        """Override: wrap *action* with interceptor hooks + middleware, then delegate to super()."""
        if action is not None and (self._interceptors or self._middleware):
            action = self._wrap(node, action)
        super().add_node(node, action, **kwargs)

    # -- internals ----------------------------------------------------

    def _wrap(self, node_name: str, fn: Callable) -> Callable:
        interceptors = self._interceptors
        middleware = self._middleware

        @functools.wraps(fn)
        def wrapper(state: Any) -> Any:
            # -- before hooks (observe only) --
            for ic in interceptors:
                try:
                    ic.before(node_name, state)
                except Exception:
                    logger.exception("Interceptor %s.before() failed for node '%s'", type(ic).__name__, node_name)

            # -- execute node --
            try:
                result = fn(state)
            except Exception as exc:
                for ic in interceptors:
                    try:
                        ic.on_error(node_name, state, exc)
                    except Exception:
                        logger.exception("Interceptor %s.on_error() failed for node '%s'", type(ic).__name__, node_name)
                raise

            # -- after hooks (observe only) --
            for ic in interceptors:
                try:
                    ic.after(node_name, state, result)
                except Exception:
                    logger.exception("Interceptor %s.after() failed for node '%s'", type(ic).__name__, node_name)

            # -- middleware chain (transforms result) --
            # Middleware errors propagate -- silent data corruption is worse than a crash
            for mw in middleware:
                result = mw.transform(node_name, state, result)

            return result

        return wrapper
