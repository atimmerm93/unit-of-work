from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from di_unit_of_work.session_cache import SessionCache
from di_unit_of_work.session_factory.abstract_session_factory import (
    AbstractSessionFactory,
)

P = ParamSpec("P")
R = TypeVar("R")


class SessionAspect:
    """Opens/commits/rolls back sessions when no active context session exists."""

    def __init__(
        self,
        session_factory: AbstractSessionFactory,
        session_cache: SessionCache,
    ) -> None:
        self._session_factory = session_factory
        self._session_cache = session_cache

    def transactional(self, func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            current_session = self._session_cache.get_current_session()
            if current_session is not None:
                return func(*args, **kwargs)

            with self._session_factory() as session:
                token = self._session_cache.set_current_session(session=session)
                try:
                    result = func(*args, **kwargs)
                    session.commit()
                    return result
                except Exception:
                    session.rollback()
                    raise
                finally:
                    self._session_cache.reset_to_token(token=token)

        return wrapped
