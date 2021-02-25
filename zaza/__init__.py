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

    If the tasks spawns other future (tasks) then these are also cleaned up
    after each step is performed.

    :returns: The result of the last asyncio.Task
    :rtype: Any
    """
    print("**** run with steps:", steps)
    print("traceback:")
    import traceback
    traceback.print_stack(limit=5)
    if not steps:
        return
    loop = asyncio.get_event_loop()

    for step in steps:
        print("step: ", step)
        task = loop.create_task(step)
        loop.run_until_complete(asyncio.wait([task], loop=loop))

        # Let's also cancel any remaining running tasks:
        pending_tasks = asyncio.Task.all_tasks()
        for pending_task in pending_tasks:
            # print("Cleaning up pending task: ", pending_task)
            pending_task.cancel()
            # Now we should await task to execute it's cancellation.
            # Cancelled task raises asyncio.CancelledError that we can suppress
            # with suppress(asyncio.CancelledError):
            try:
                loop.run_until_complete(task)
            except Exception:
                pass

    print("*** done run")
    result = task.result()
    print("*** and got task.result()")
    # return task.result()
    return result


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
