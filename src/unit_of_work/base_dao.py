from sqlalchemy.orm import Session

from unit_of_work.session_provider import SessionProvider


class BaseDao:
    def __init__(self, session_provider: SessionProvider) -> None:
        self._session_provider = session_provider

    @property
    def _session(self) -> Session:
        return self._session_provider.get_session()

    def _add_to_db(self, persistent_object: object) -> None:
        # Add to db logic here using the session
        self._session.add(persistent_object)
        self._session.flush()
        self._session.refresh(persistent_object)
