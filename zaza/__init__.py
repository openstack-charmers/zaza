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
import logging
from pkgutil import extend_path
from sys import version_info


__path__ = extend_path(__path__, __name__)


def run(*steps):
    """Run the given steps in an asyncio loop.

    If the tasks spawns other future (tasks) then these are also cleaned up
    after each step is performed.

    :returns: The result of the last asyncio.Task
    :rtype: Any
    """
    if not steps:
        return
    loop = asyncio.get_event_loop()

    for step in steps:
        task = loop.create_task(step)
        loop.run_until_complete(asyncio.wait([task], loop=loop))

        # Let's also cancel any remaining tasks:
        while True:
            # issue #445 - asyncio.Task.all_tasks() deprecated in 3.7
            if version_info.major == 3 and version_info.minor >= 7:
                try:
                    tasklist = asyncio.all_tasks()
                except RuntimeError:
                    # no running event loop
                    break
            else:
                tasklist = asyncio.Task.all_tasks()
            pending_tasks = [p for p in tasklist if not p.done()]
            if pending_tasks:
                logging.info(
                    "async -> sync. cleaning up pending tasks: len: {}"
                    .format(len(pending_tasks)))
                for pending_task in pending_tasks:
                    pending_task.cancel()
                    try:
                        loop.run_until_complete(pending_task)
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logging.error(
                            "A pending task caused an exception: {}"
                            .format(str(e)))
            else:
                break

    return task.result()


def sync_wrapper(f):
    """Convert the given async function into a sync function.

    This is only to be called from sync code and it runs all tasks (and cancels
    all tasks at the end of each run) for the code that is being given.

    :returns: The de-async'd function
    :rtype: function
    """
    def _wrapper(*args, **kwargs):
        async def _run_it():
            return await f(*args, **kwargs)
        return run(_run_it())
    return _wrapper
