"""Functions to support converting async function to a sync equivalent."""
import asyncio


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
