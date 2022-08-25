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

# import aiounittest


# Prior to Python 3.8 asyncio would raise a ``asyncio.futures.TimeoutError``
# exception on timeout, from Python 3.8 onwards it raises a exception from a
# new ``asyncio.exceptions`` module.
#
# Neither of these are inherited from a relevant built-in exception so we
# cannot catch them generally with the built-in TimeoutError or similar.
try:
    import asyncio.exceptions
    AsyncTimeoutError = asyncio.exceptions.TimeoutError
except ImportError:
    import asyncio.futures
    AsyncTimeoutError = asyncio.futures.TimeoutError

import mock

import unit_tests.utils as ut_utils

import zaza


def tearDownModule():
    zaza.clean_up_libjuju_thread()


class TestModel(ut_utils.BaseTestCase):

    def test_run(self):
        async def one():
            return 1

        async def two():
            return 2

        async def three():
            return 3

        with mock.patch.object(zaza, 'RUN_LIBJUJU_IN_THREAD', new=False):
            self.assertEquals(zaza.run(one), 1)
            self.assertEquals(zaza.run(one, two), 2)
            self.assertEquals(zaza.run(one, two, three), 3)
            self.assertEquals(zaza.run(), None)
