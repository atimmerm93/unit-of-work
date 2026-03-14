from sqlalchemy.orm import Session

from di_unit_of_work.session_cache import SessionCache


class SessionProvider:
    def __init__(self, session_cache: SessionCache) -> None:
        self._session_cache = session_cache

    def get_session(self) -> Session:
        session = self._session_cache.get_current_session()
        if session is None:
            raise RuntimeError("No active session found in context.")
        return session
