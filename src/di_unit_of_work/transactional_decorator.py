from collections.abc import Callable
from typing import ParamSpec, TypeVar

from python_di_application.di_container import DIContainer

from .session_aspect import SessionAspect

P = ParamSpec("P")
R = TypeVar("R")


def transactional(func: Callable[P, R]) -> Callable[P, R]:
    """DI post-init decorator that applies SessionAspect.transactions."""
    return DIContainer.post_init_wrap(wrap_func=SessionAspect.transactional)(func)
