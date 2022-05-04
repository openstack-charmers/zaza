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

# __NOTE__
#
# Whenever this file is changed, make sure to update the copy of it in
# ``zaza-openstack-tests``.
#
# The ``zaza`` and ``zaza-openstack-tests`` projects are related, and currently
# the latter is installed as a package inside the former.  As a consequence
# ``zaza-openstack-tests`` needs to carry a copy of this file
# (``zaza/__init__.py``) as this file will be overwritten by the copy in
# ``zaza-openstack-tests`` on install.
#
# We of course want a better solution to this, but in the interest of time
# this note is left here until we get around to fixing it properly.
#
# __NOTE__

"""Functions to support converting async function to a sync equivalent."""
import asyncio
import concurrent.futures
import logging
import time
import threading
from pkgutil import extend_path
from sys import version_info


__path__ = extend_path(__path__, __name__)

# This flag is for testing, but can be used to control whether libjuju runs in
# a background thread or is simplified.
RUN_LIBJUJU_IN_THREAD = True

# Hold the libjuju thread so we can interact with it.
_libjuju_thread = None
_libjuju_loop = None
_libjuju_run = False

# Timeout for loop to close.  This is set to 30 seconds.  If there is a non
# async all in the async thread then it could stall the thread for more than 30
# seconds (e.g. an errant subprocess call).  This will cause a runtime error if
# the timeout is exceeded.  This shouldn't normally be the case as there is
# only one 'start' and 'stop' of the thread during a zaza runtime
LOOP_CLOSE_TIMEOUT = 30.0


def get_or_create_libjuju_thread():
    """Get (or Create) the thread that libjuju asyncio is running in.

    :returns: the thread that libjuju is running in.
    :rtype: threading.Thread
    """
    global _libjuju_thread, _libjuju_loop, _libjuju_run
    if _libjuju_thread is None:
        _libjuju_run = True
        _libjuju_thread = threading.Thread(target=libjuju_thread_run)
        _libjuju_thread.start()
        # There's a race hazard for _libjuju_loop becoming available, so let's
        # wait for that to happen.
        now = time.time()
        while True:
            if (_libjuju_loop is not None and _libjuju_loop.is_running()):
                break
            time.sleep(.01)
            # allow 5 seconds for thead to start
            if time.time() > now + 5.0:
                raise RuntimeError("Async thread didn't start!")
    return _libjuju_thread


def libjuju_thread_run():
    """Run the libjuju async thread.

    The thread that contains the runtime for libjuju asyncio futures.

    zaza runs libjuju in a background thread so that it can make progress as
    needed with the model(s) that are connect.  The sync functions run in the
    foreground thread, and the asyncio libjuju functions run in the background
    thread. `run_coroutine_threadsafe` is used to cross from sync to asyncio
    code in the background thread to enable access to the libjuju.

    Note: it's very important that libjuju objects are not updated in the sync
    thread; it's advisable that they are copied into neutral objects and handed
    back.  e.g. always use unit_name, rather than handling a libjuju 'unit'
    object in a sync function.
    """
    global _libjuju_loop

    async def looper():
        global _libjuju_run
        while _libjuju_run:
            # short spinner to ensure that foreground tasks 'happen' so that
            # background tasks can complete (e.g. during model disconnection).
            # loop.run_forever() doesn't work as there is no foreground async
            # task to make progress, and thus the background tasks do nothing.
            await asyncio.sleep(0.1)

    _libjuju_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_libjuju_loop)
    try:
        _libjuju_loop.run_until_complete(_libjuju_loop.create_task(looper()))
    finally:
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
                        _libjuju_loop.run_until_complete(pending_task)
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logging.error(
                            "A pending task caused an exception: {}"
                            .format(str(e)))
            else:
                break
    _libjuju_loop.close()


def join_libjuju_thread():
    """Stop and cleanup the asyncio tasks on the loop, and then join it."""
    global _libjuju_thread, _libjuju_loop, _libjuju_run
    if _libjuju_thread is not None:
        logging.debug("stopping the event loop")
        _libjuju_run = False
        # wait up to 30 seconds for loop to close.
        now = time.time()
        while not(_libjuju_loop.is_closed()):
            logging.debug("Closing ...")
            time.sleep(.1)
            if time.time() > now + LOOP_CLOSE_TIMEOUT:
                raise RuntimeError(
                    "Exceeded {} seconds for loop to close"
                    .format(LOOP_CLOSE_TIMEOUT))
        logging.debug("joining the loop")
        _libjuju_thread.join(timeout=30.0)
        if _libjuju_thread.is_alive():
            logging.error("The thread didn't die")
            raise RuntimeError(
                "libjuju async thread didn't finish after 30seconds")
        _libjuju_thread = None


def clean_up_libjuju_thread():
    """Clean up the libjuju thread and any models that are still running."""
    global _libjuju_loop, _libjuju_run
    if _libjuju_loop is not None:
        # circular import; tricky to remove
        from . import model
        sync_wrapper(model.remove_models_memo)()
        join_libjuju_thread()
        _libjuju_run = False
        _libjuju_loop = None


def sync_wrapper(f, timeout=None):
    """Convert the async function into one that runs in the async thread.

    This is only to be called from sync code.  It wraps the given async
    co-routine in some sync logic that allows it to be injected into the async
    libjuju thread.  This is then waited until there is a result, in which case
    the result is returned.

    :param f: The async co-routine to wrap.
    :type f: Coroutine
    :param timeout: The timeout to apply, None for no timeout
    :type timeout: Optional[float]
    :returns: The de-async'd function
    :rtype: function
    """
    def _wrapper(*args, **kwargs):
        global _libjuju_loop

        async def _runner():
            return await f(*args, **kwargs)

        if not RUN_LIBJUJU_IN_THREAD:
            # run it in this thread's event loop:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(_runner())

        # ensure that the thread is created
        get_or_create_libjuju_thread()
        assert _libjuju_loop is not None and _libjuju_loop.is_running(), \
            "Background thread must be running by now, so this is a bug"

        # Submit the coroutine to a given loop
        future = asyncio.run_coroutine_threadsafe(_runner(), _libjuju_loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError:
            logging.error(
                'The coroutine took too long, cancelling the task...')
            future.cancel()
            raise

    return _wrapper
