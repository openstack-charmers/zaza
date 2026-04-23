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

"""Compatibility shims for the jubilant-based (sync) rewrite of zaza.

The async machinery (libjuju background thread, event loop management) has
been removed now that zaza uses jubilant, which is fully synchronous.

``sync_wrapper`` is kept as a transparent pass-through so that downstream
consumers (e.g. zaza-openstack-tests) that call::

    foo = sync_wrapper(async_foo)

continue to work without modification.  The wrapped function is called
directly; no async scheduling takes place.
"""
import inspect
import logging
from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)

# ---------------------------------------------------------------------------
# Legacy compatibility flags – kept so that existing code that reads or
# patches these names does not break with an AttributeError.
# ---------------------------------------------------------------------------

#: No longer meaningful; retained for backwards compatibility only.
RUN_LIBJUJU_IN_THREAD = False


def sync_wrapper(f, timeout=None):
    """Return a synchronous callable that calls *f* directly.

    Previously this scheduled an async coroutine on a background event loop.
    Now that zaza uses jubilant (a fully synchronous library) this shim simply
    calls the wrapped function in the current thread.

    The *timeout* parameter is accepted for API compatibility but is ignored.

    :param f: The function to wrap.  May be a plain function or a coroutine
        function (``async def``); both are handled transparently.
    :type f: callable
    :param timeout: Ignored; kept for API compatibility.
    :type timeout: Optional[float]
    :returns: A synchronous wrapper around *f*.
    :rtype: callable
    """
    def _wrapper(*args, **kwargs):
        result = f(*args, **kwargs)
        # If f is still an async coroutine function (e.g. not yet migrated),
        # run it synchronously so callers are not broken.
        if inspect.iscoroutine(result):
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(result)
            finally:
                loop.close()
        return result

    return _wrapper


def run(*steps):
    """Run the given steps sequentially and return the result of the last one.

    Previously this drove an asyncio event loop.  Now steps are executed
    directly in the calling thread.  Async coroutines and coroutine functions
    are still accepted for backwards compatibility and are run synchronously
    via a temporary event loop.

    :param steps: Functions, coroutines, or plain values to execute in order.
    :type steps: List
    :returns: The result of the last step.
    :rtype: Any
    """
    if not steps:
        return None

    import asyncio

    def _call(f):
        if inspect.iscoroutine(f):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(f)
            finally:
                loop.close()
        elif inspect.iscoroutinefunction(f):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(f())
            finally:
                loop.close()
        elif inspect.isfunction(f):
            return f()
        else:
            return f

    result = None
    for step in steps:
        result = _call(step)
    return result


# ---------------------------------------------------------------------------
# Stubs for the old async-thread lifecycle functions.
# These are no-ops; they exist only so that code that calls them (e.g. test
# tearDownModule hooks) does not raise AttributeError.
# ---------------------------------------------------------------------------

def get_or_create_libjuju_thread():
    """No-op stub retained for API compatibility."""
    logging.debug("get_or_create_libjuju_thread: no-op (jubilant migration)")


def join_libjuju_thread():
    """No-op stub retained for API compatibility."""
    logging.debug("join_libjuju_thread: no-op (jubilant migration)")


def clean_up_libjuju_thread():
    """No-op stub retained for API compatibility."""
    logging.debug("clean_up_libjuju_thread: no-op (jubilant migration)")
