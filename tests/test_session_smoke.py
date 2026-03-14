import unittest

from python_di_application.dependency import Dependency
from python_di_application.di_container import DIContainer
from sqlalchemy import String, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from di_unit_of_work.session_aspect import SessionAspect
from di_unit_of_work.session_cache import SessionCache
from di_unit_of_work.session_factory.sqlite_session_factory import (
    SQLiteSessionFactory,
    SqlLiteConfig,
)
from di_unit_of_work.session_provider import SessionProvider
from di_unit_of_work.transactional_decorator import transactional


class TestBase(DeclarativeBase):
    pass


class TestDocument(TestBase):
    __tablename__ = "test_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))


class NestedTransactionalServiceB:
    def __init__(self, session_provider: SessionProvider) -> None:
        self._session_provider = session_provider
        self.observed_session: Session | None = None

    @transactional
    def test_b(self) -> Session:
        self.observed_session = self._session_provider.get_session()
        return self.observed_session


class NestedTransactionalServiceA:
    def __init__(
        self,
        session_provider: SessionProvider,
        nested_service_b: NestedTransactionalServiceB,
    ) -> None:
        self._session_provider = session_provider
        self._nested_service_b = nested_service_b
        self.observed_session: Session | None = None

    @transactional
    def test_a(self) -> tuple[Session, Session]:
        self.observed_session = self._session_provider.get_session()
        nested_session = self._nested_service_b.test_b()
        return self.observed_session, nested_session


class RollbackNestedTransactionalServiceB:
    def __init__(self, session_provider: SessionProvider) -> None:
        self._session_provider = session_provider
        self.observed_session: Session | None = None

    @transactional
    def test_b(self) -> None:
        self.observed_session = self._session_provider.get_session()
        raise RuntimeError("trigger rollback")


class RollbackNestedTransactionalServiceA:
    def __init__(
        self,
        session_provider: SessionProvider,
        nested_service_b: RollbackNestedTransactionalServiceB,
    ) -> None:
        self._session_provider = session_provider
        self._nested_service_b = nested_service_b

    @transactional
    def test_a(self, name: str = "created-before-rollback") -> None:
        self.test_successful_write(name=name)
        self._nested_service_b.test_b()

    @transactional
    def test_successful_write(self, name: str = "success-full-write") -> None:
        session = self._session_provider.get_session()
        session.add(TestDocument(name=name))
        session.flush()


class TestSessionSmoke(unittest.TestCase):
    def setUp(self) -> None:
        self.container = DIContainer()
        self.container.register_dependencies(
            dependencies_types_with_kwargs=[
                Dependency(NestedTransactionalServiceA),
                Dependency(NestedTransactionalServiceB),
                Dependency(RollbackNestedTransactionalServiceA),
                Dependency(RollbackNestedTransactionalServiceB),
                Dependency(SessionProvider),
                Dependency(SQLiteSessionFactory),
                Dependency(SessionAspect),
                Dependency(SessionCache),
            ]
        )
        self.container.register_instance(
            instance_obj=SqlLiteConfig(path=":memory:", metadata=TestBase.metadata)
        )

        self.service_a = self.container[NestedTransactionalServiceA]
        self.service_b = self.container[NestedTransactionalServiceB]
        self.rollback_service_a = self.container[RollbackNestedTransactionalServiceA]
        self.rollback_service_b = self.container[RollbackNestedTransactionalServiceB]
        self.session_cache = self.container[SessionCache]
        self.session_factory = self.container[SQLiteSessionFactory]
        self.container.apply_post_init_wrappers()

    def test_nested_transactional_methods_reuse_same_session(self) -> None:
        outer_session, inner_session = self.service_a.test_a()

        self.assertIsNotNone(outer_session)
        self.assertIs(outer_session, inner_session)
        self.assertIs(self.service_a.observed_session, self.service_b.observed_session)
        self.assertIs(self.service_a.observed_session, outer_session)
        self.assertIsNone(self.session_cache.get_current_session())

    def test_write_to_db_successfully_commits_if_no_exceptions(self) -> None:
        self.rollback_service_a.test_successful_write()

        with self.session_factory() as session:
            row_count = session.scalar(select(func.count()).select_from(TestDocument))
            document = session.get(TestDocument, 1)
            assert document is not None
            document_name = document.name
        self.assertEqual(1, row_count)
        self.assertEqual("success-full-write", document_name)

    def test_nested_exception_rolls_back_outer_database_changes(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "trigger rollback"):
            self.rollback_service_a.test_a()

        with self.session_factory() as session:
            row_count = session.scalar(select(func.count()).select_from(TestDocument))

        self.assertEqual(0, row_count)
        self.assertIsNone(self.session_cache.get_current_session())


if __name__ == "__main__":
    unittest.main()
