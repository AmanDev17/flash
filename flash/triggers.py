"""
Trigger and hook system for Flash.
Supports before/after hooks for insert, update, delete operations.
"""

from collections import defaultdict
from typing import Callable, Optional


class TriggerRegistry:
    """
    Registry for before/after operation hooks on collections/tables.
    """

    VALID_EVENTS = {"insert", "update", "delete", "select"}
    VALID_TIMINGS = {"before", "after"}

    def __init__(self):
        # Structure: {timing: {event: {table: [callable, ...]}}}
        self._hooks: dict = {
            "before": defaultdict(lambda: defaultdict(list)),
            "after": defaultdict(lambda: defaultdict(list)),
        }

    def register(self, timing: str, event: str, table: str, fn: Callable):
        """Register a hook function for a given timing, event, and table."""
        if timing not in self.VALID_TIMINGS:
            raise ValueError(f"Invalid timing '{timing}'. Choose from: {self.VALID_TIMINGS}")
        if event not in self.VALID_EVENTS:
            raise ValueError(f"Invalid event '{event}'. Choose from: {self.VALID_EVENTS}")

        self._hooks[timing][event][table].append(fn)

    def fire(self, timing: str, event: str, table: str, data, result=None):
        """
        Fire all hooks for a given timing/event/table.

        Args:
            timing: 'before' or 'after'
            event: 'insert', 'update', 'delete', 'select'
            table: collection/table name
            data: the payload (filter or record dict)
            result: the query result (only for 'after' hooks)
        """
        hooks = self._hooks[timing][event].get(table, [])
        for fn in hooks:
            try:
                if timing == "after":
                    fn(data, result)
                else:
                    fn(data)
            except Exception as e:
                print(f"[Flash Warning] Hook '{fn.__name__}' raised an error: {e}")

    def clear(self, table: Optional[str] = None):
        """Clear all hooks, or hooks for a specific table."""
        if table:
            for timing in self.VALID_TIMINGS:
                for event in self.VALID_EVENTS:
                    self._hooks[timing][event].pop(table, None)
        else:
            self.__init__()

    def list_hooks(self) -> dict:
        """Return a summary of all registered hooks."""
        summary = {}
        for timing in self.VALID_TIMINGS:
            for event in self.VALID_EVENTS:
                for table, fns in self._hooks[timing][event].items():
                    key = f"{timing}_{event}:{table}"
                    summary[key] = [fn.__name__ for fn in fns]
        return {k: v for k, v in summary.items() if v}


# Singleton registry shared across a FlashDB instance
def make_trigger_mixin():
    """
    Returns a mixin class providing decorator-style trigger registration.
    Each FlashDB instance gets its own mixin with its own registry.
    """

    class TriggerMixin:
        def _init_triggers(self):
            self._triggers = TriggerRegistry()

        # ── Decorator API ─────────────────────────────────────────────────
        def before_insert(self, table: str):
            def decorator(fn: Callable):
                self._triggers.register("before", "insert", table, fn)
                return fn
            return decorator

        def after_insert(self, table: str):
            def decorator(fn: Callable):
                self._triggers.register("after", "insert", table, fn)
                return fn
            return decorator

        def before_update(self, table: str):
            def decorator(fn: Callable):
                self._triggers.register("before", "update", table, fn)
                return fn
            return decorator

        def after_update(self, table: str):
            def decorator(fn: Callable):
                self._triggers.register("after", "update", table, fn)
                return fn
            return decorator

        def before_delete(self, table: str):
            def decorator(fn: Callable):
                self._triggers.register("before", "delete", table, fn)
                return fn
            return decorator

        def after_delete(self, table: str):
            def decorator(fn: Callable):
                self._triggers.register("after", "delete", table, fn)
                return fn
            return decorator

        def before_select(self, table: str):
            def decorator(fn: Callable):
                self._triggers.register("before", "select", table, fn)
                return fn
            return decorator

        def after_select(self, table: str):
            def decorator(fn: Callable):
                self._triggers.register("after", "select", table, fn)
                return fn
            return decorator

        # ── Programmatic API ──────────────────────────────────────────────
        def add_hook(self, timing: str, event: str, table: str, fn: Callable):
            """Programmatically register a hook without decorators."""
            self._triggers.register(timing, event, table, fn)

        def list_hooks(self) -> dict:
            """List all registered hooks."""
            return self._triggers.list_hooks()

        def clear_hooks(self, table: Optional[str] = None):
            """Remove hooks (all, or for a specific table)."""
            self._triggers.clear(table)

    return TriggerMixin