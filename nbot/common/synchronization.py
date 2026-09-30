"""Serialize complete execution transitions against their canonical state store."""
from functools import wraps


def state_transition(method):
    @wraps(method)
    def locked(self, *args, **kwargs):
        state = getattr(self, "state", self)
        with state.mutation_lock:
            return method(self, *args, **kwargs)
    return locked
