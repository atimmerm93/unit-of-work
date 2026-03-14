import asyncio
import multiprocessing
import queue
import threading
import unittest
from unittest.mock import Mock

from sqlalchemy.orm import Session

from di_unit_of_work.session_cache import SessionCache

_PROCESS_CACHE = SessionCache()


def _read_process_cache_state(result_queue: multiprocessing.Queue) -> None:
    result_queue.put(_PROCESS_CACHE.get_current_session())


class TestSessionCache(unittest.TestCase):
    def setUp(self) -> None:
        self.session_cache = SessionCache()

    def test_set_reset_and_clear_session(self) -> None:
        session = Mock(spec=Session)

        token = self.session_cache.set_current_session(session)

        self.assertTrue(self.session_cache.has_active_session())
        self.assertIs(session, self.session_cache.get_current_session())

        self.session_cache.reset_to_token(token)
        self.assertFalse(self.session_cache.has_active_session())
        self.assertIsNone(self.session_cache.get_current_session())

        self.session_cache.set_current_session(session)
        self.session_cache.clear()
        self.assertFalse(self.session_cache.has_active_session())
        self.assertIsNone(self.session_cache.get_current_session())

    def test_session_does_not_leak_into_another_thread(self) -> None:
        session = Mock(spec=Session)
        self.session_cache.set_current_session(session)
        result_queue: queue.Queue[Session | None] = queue.Queue()

        def read_session_in_thread() -> None:
            result_queue.put(self.session_cache.get_current_session())

        thread = threading.Thread(target=read_session_in_thread)
        thread.start()
        thread.join()

        self.assertIsNone(result_queue.get_nowait())
        self.assertIs(session, self.session_cache.get_current_session())

    def test_session_does_not_leak_into_spawned_process(self) -> None:
        parent_session = Mock(spec=Session)
        _PROCESS_CACHE.clear()
        _PROCESS_CACHE.set_current_session(parent_session)

        ctx = multiprocessing.get_context("spawn")
        result_queue = ctx.Queue()
        process = ctx.Process(target=_read_process_cache_state, args=(result_queue,))
        process.start()
        process.join()

        child_session = result_queue.get(timeout=5)

        self.assertEqual(0, process.exitcode)
        self.assertIsNone(child_session)
        self.assertIs(parent_session, _PROCESS_CACHE.get_current_session())


class TestSessionCacheAsync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.session_cache = SessionCache()

    async def test_task_specific_updates_do_not_leak_to_siblings_or_parent(self) -> None:
        task_session = Mock(spec=Session)

        async def override_session_in_task() -> Session | None:
            self.session_cache.set_current_session(task_session)
            await asyncio.sleep(0)
            return self.session_cache.get_current_session()

        async def read_session_in_sibling_task() -> Session | None:
            session = self.session_cache.get_current_session()
            await asyncio.sleep(0)
            return session

        overriding_task = asyncio.create_task(override_session_in_task())
        sibling_task = asyncio.create_task(read_session_in_sibling_task())

        overridden_result, sibling_result = await asyncio.gather(
            overriding_task,
            sibling_task,
        )
        self.assertIsNot(overridden_result, sibling_result)
        self.assertIs(task_session, overridden_result)
        self.assertIsNone(sibling_result)


if __name__ == "__main__":
    unittest.main()
