import unittest
from typing import cast
from unittest.mock import Mock

from sqlalchemy.orm import Session

from di_unit_of_work.session_aspect import SessionAspect
from di_unit_of_work.session_cache import SessionCache
from di_unit_of_work.session_factory.abstract_session_factory import (
    AbstractSessionFactory,
)


class _SessionFactoryContext:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.enter_count = 0
        self.exit_count = 0

    def __call__(self) -> "_SessionFactoryContext":
        return self

    def __enter__(self) -> Session:
        self.enter_count += 1
        return self.session

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.exit_count += 1


class TestSessionAspect(unittest.TestCase):
    def setUp(self) -> None:
        self.session_cache = SessionCache()
        self.session = Mock(spec=Session)
        self.session_factory = _SessionFactoryContext(self.session)
        self.session_aspect = SessionAspect(
            session_factory=cast(AbstractSessionFactory, self.session_factory),
            session_cache=self.session_cache,
        )

    def test_transactional_opens_commits_and_clears_session_on_success(self) -> None:
        observed_sessions: list[Session | None] = []

        def transactional_work() -> str:
            observed_sessions.append(self.session_cache.get_current_session())
            return "committed"

        wrapped = self.session_aspect.transactional(transactional_work)

        result = wrapped()

        self.assertEqual("committed", result)
        self.assertEqual([self.session], observed_sessions)
        self.session.commit.assert_called_once_with()
        self.session.rollback.assert_not_called()
        self.assertEqual(1, self.session_factory.enter_count)
        self.assertEqual(1, self.session_factory.exit_count)
        self.assertIsNone(self.session_cache.get_current_session())

    def test_transactional_rolls_back_and_clears_session_on_error(self) -> None:
        def failing_transaction() -> None:
            self.assertIs(self.session, self.session_cache.get_current_session())
            raise RuntimeError("boom")

        wrapped = self.session_aspect.transactional(failing_transaction)

        with self.assertRaisesRegex(RuntimeError, "boom"):
            wrapped()

        self.session.commit.assert_not_called()
        self.session.rollback.assert_called_once_with()
        self.assertEqual(1, self.session_factory.enter_count)
        self.assertEqual(1, self.session_factory.exit_count)
        self.assertIsNone(self.session_cache.get_current_session())

    def test_nested_transactional_calls_reuse_aspect_managed_session(self) -> None:
        observed_sessions: list[Session] = []

        def inner_transaction() -> Session:
            current_session = self.session_cache.get_current_session()
            assert current_session is not None
            observed_sessions.append(current_session)
            return current_session

        wrapped_inner = self.session_aspect.transactional(inner_transaction)

        def outer_transaction() -> tuple[Session, Session]:
            current_session = self.session_cache.get_current_session()
            assert current_session is not None
            observed_sessions.append(current_session)
            inner_session = wrapped_inner()
            return current_session, inner_session

        wrapped_outer = self.session_aspect.transactional(outer_transaction)

        outer_session, inner_session = wrapped_outer()

        self.assertIs(outer_session, inner_session)
        self.assertEqual([self.session, self.session], observed_sessions)
        self.session.commit.assert_called_once_with()
        self.session.rollback.assert_not_called()
        self.assertEqual(1, self.session_factory.enter_count)
        self.assertEqual(1, self.session_factory.exit_count)
        self.assertIsNone(self.session_cache.get_current_session())


if __name__ == "__main__":
    unittest.main()
