# Copyright 2018 Canonical Ltd.
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

"""Functions to support converting async function to a sync equivalent."""
import asyncio
from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)


def run(*steps):
    """Run the given steps in an asyncio loop.

    :returns: The result of the asyncio.Task
    :rtype: Any
    """
    if not steps:
        return
    loop = asyncio.get_event_loop()

    for step in steps:
        task = loop.create_task(step)
        loop.run_until_complete(asyncio.wait([task], loop=loop))
    return task.result()


def sync_wrapper(f):
    """Convert the given async function into a sync function.

    :returns: The de-async'd function
    :rtype: function
    """
    def _wrapper(*args, **kwargs):
        async def _run_it():
            return await f(*args, **kwargs)
        return run(_run_it())
    return _wrapper
