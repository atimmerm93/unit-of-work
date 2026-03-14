from abc import ABC, abstractmethod

from sqlalchemy.orm import Session, sessionmaker


class AbstractSessionFactory(ABC):
    def __init__(self) -> None:
        self.initialize_database()
        self._session_maker: sessionmaker[Session] = self.create_session_factory()

    @abstractmethod
    def initialize_database(self) -> None:
        """Prepare the backing store before sessions are created."""
        pass

    @abstractmethod
    def create_session_factory(self) -> sessionmaker[Session]:
        """Build the session factory after initialization is complete."""
        pass

    def __call__(self) -> Session:
        return self._session_maker()
