from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.schema import MetaData

from di_unit_of_work.session_factory.abstract_session_factory import AbstractSessionFactory


@dataclass(frozen=True)
class SqlLiteConfig:
    path: str
    metadata: MetaData | None = None


class SQLiteSessionFactory(AbstractSessionFactory):
    """Factory class that creates SQLite-backed SQLAlchemy sessions."""

    def __init__(self, sql_lite_config: SqlLiteConfig) -> None:
        self._config: SqlLiteConfig = sql_lite_config
        self._db_path = Path(self._config.path).expanduser()
        self._engine: Engine | None = None
        super().__init__()

    def _sqlite_url(self, db_path: str | Path) -> str:
        if self._is_in_memory_db(db_path):
            return "sqlite:///:memory:"
        return f"sqlite:///{Path(db_path)}"

    def _is_in_memory_db(self, db_path: str | Path) -> bool:
        return str(db_path) == ":memory:"

    def create_sqlalchemy_engine(self, db_path: str | Path) -> Engine:
        if self._is_in_memory_db(db_path):
            return create_engine(
                self._sqlite_url(db_path),
                future=True,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )

        engine = create_engine(self._sqlite_url(db_path), future=True)
        return engine

    def initialize_database(self) -> None:
        if not self._is_in_memory_db(self._db_path) and self._db_path.parent != Path():
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db_path.touch(exist_ok=True)

        self._engine = self.create_sqlalchemy_engine(self._db_path)

        if self._config.metadata is not None:
            self._config.metadata.create_all(bind=self._engine)

    def create_session_factory(self) -> sessionmaker[Session]:
        if self._engine is None:
            raise RuntimeError("Database engine was not initialized.")
        return sessionmaker(bind=self._engine, future=True, expire_on_commit=False)
