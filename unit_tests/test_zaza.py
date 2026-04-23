# Copyright 2022 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unit_tests.utils as ut_utils

import zaza


class TestSyncWrapper(ut_utils.BaseTestCase):
    """Tests for the sync_wrapper shim."""

    def test_sync_wrapper_plain_function(self):
        """sync_wrapper passes through a plain (non-async) function."""
        def add(a, b):
            return a + b

        wrapped = zaza.sync_wrapper(add)
        self.assertEqual(wrapped(1, 2), 3)

    def test_sync_wrapper_async_function(self):
        """sync_wrapper transparently runs an async coroutine function."""
        async def async_add(a, b):
            return a + b

        wrapped = zaza.sync_wrapper(async_add)
        self.assertEqual(wrapped(3, 4), 7)

    def test_sync_wrapper_timeout_ignored(self):
        """sync_wrapper accepts a timeout kwarg without error (no-op)."""
        def identity(x):
            return x

        wrapped = zaza.sync_wrapper(identity, timeout=30)
        self.assertEqual(wrapped(42), 42)


class TestRun(ut_utils.BaseTestCase):
    """Tests for the run() helper."""

    def test_run_no_steps(self):
        self.assertIsNone(zaza.run())

    def test_run_plain_function(self):
        def num4():
            return 4

        self.assertEqual(zaza.run(num4), 4)

    def test_run_plain_value(self):
        self.assertEqual(zaza.run(num4()), 4)  # noqa: F821 – defined below

    def test_run_multiple_steps_returns_last(self):
        def one():
            return 1

        def two():
            return 2

        self.assertEqual(zaza.run(one, two), 2)

    def test_run_async_function(self):
        async def async_three():
            return 3

        self.assertEqual(zaza.run(async_three), 3)

    def test_run_async_coroutine(self):
        async def async_add(i):
            return i + 1

        # Pass an already-created coroutine object.
        self.assertEqual(zaza.run(async_add(2)), 3)

    def test_run_mixed_steps(self):
        async def one():
            return 1

        async def two():
            return 2

        async def add1(i):
            return i + 1

        def num4():
            return 4

        self.assertEqual(zaza.run(one), 1)
        self.assertEqual(zaza.run(one, two), 2)
        self.assertEqual(zaza.run(one, two, add1(2)), 3)
        self.assertEqual(zaza.run(), None)
        self.assertEqual(zaza.run(num4), 4)
        self.assertEqual(zaza.run(num4()), 4)


def num4():
    return 4


class TestCompatStubs(ut_utils.BaseTestCase):
    """The old async-thread lifecycle stubs must exist and be callable."""

    def test_clean_up_libjuju_thread_is_noop(self):
        zaza.clean_up_libjuju_thread()

    def test_join_libjuju_thread_is_noop(self):
        zaza.join_libjuju_thread()

    def test_get_or_create_libjuju_thread_is_noop(self):
        zaza.get_or_create_libjuju_thread()

    def test_run_libjuju_in_thread_flag_exists(self):
        self.assertFalse(zaza.RUN_LIBJUJU_IN_THREAD)
