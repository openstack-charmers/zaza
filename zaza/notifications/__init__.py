# Copyright 2021 Canonical Ltd.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Notification framework for zaza.

This module provides a pub-sub notification framework within zaza to enable
functions to be called at particular points in the zaza framework's lifecycle.

A function can be subscribed for a notification based on a particular
"interest" in the function.  i.e. before, after, both, exception or all.

    NotifyType.BEFORE: Function is called before something happens.
    NotifyType.AFTER: Function is called after something happens.
    NotifyType.BOTH: Function is called before and after something
                          happens.
    NotifyType.EXCEPTION: Function is called if an exception occurs.
    NotifyType.ALL: Function is called for all of the events.

So a handler can be subscribed for a function.  The handler is called with the
notification event, and the notification type, and then any params that the
notification function provided.
"""


from collections import defaultdict
from collections.abc import Iterable
from contextlib import ContextDecorator
import enum
import logging
import uuid


logger = logging.getLogger(__name__)


# Store Notify events and functions to call against that event
class NotifyEvents(enum.Enum):
    """Notify Events definitions."""

    BUNDLE = "bundle"
    ENV_DEPLOYMENT = "env-deployment"
    PREPARE_ENVIRONMENT = "prepare-env"
    BEFORE_DEPLOY = "before-deploy"
    BEFORE_DEPLOY_FUNCTION = "before-deploy-function"
    CONFIGURE = "configure"
    CONFIGURE_FUNCTION = "configure-function"
    DEPLOY_BUNDLE = "deploy-bundle"
    WAIT_MODEL_SETTLE = "wait-model-settle"
    CONFIGURE_MODEL = "configure-model"
    TESTS = "tests"
    TEST_CASE = "test-case"
    DESTROY_MODEL = "destroy-model"


class NotifyType(enum.Enum):
    """Notify Types to go with the Notify Events."""

    BEFORE = "before"
    AFTER = "after"
    BOTH = "both"
    EXCEPTION = "exception"
    ALL = "all"


_notify_map = {
    NotifyType.BEFORE: defaultdict(list),
    NotifyType.AFTER: defaultdict(list),
    NotifyType.EXCEPTION: defaultdict(list),
}


def subscribe_this(event=None, when=None):
    """Register a function  to call for an NotifyEvents as a decorator.

    The :param:`when` is when the function gets called.
    The :param:`event` is the charm lifecycle event, zaza event, that this
    function should be registered against.

    Use as:

        @subscribe_this(NotifyEvents.DEPLOY_BUNDLE, NotifyType.BOTH)
        def deploy_model_notification_handler(....)

    In this case, two events (NotifyType.BEFORE and .AFTER may be fired)
    when a model is deployed, and this function will get both of them.

    If NotifyType.ALL is used (the default, also None), then the handler is
    called for before, after and exceptions.

    :param event: the event to register the function against.
    :type event: Union[str, Iterable[str], None]
    :param when: when the function should be called.
    :type when: str
    """
    def accept_function(f):
        """Subscribe the decorated function."""
        subscribe(f, event, when)
        return f

    return accept_function


def subscribe(f, event=None, when=None):
    """Suscribe to an event.

    If :param:`event` is None, then all events in NotifyEvents are subscribed
    to.
    If :param:`event` is a list, then those events will be subscribed.
    If :param:`when` is None, then the BEFORE event is subscribed to.

    :param event: the event to register the function against.
    :type event: Union[str, Iterable[str], None]
    :param when: when the function should be called.
    :type when: str
    """
    global _notify_map
    if event is None:
        events = NotifyEvents
    elif isinstance(event, Iterable):
        events = event
    else:
        # make an iterable of a single event
        events = (event, )
    if when == NotifyType.ALL:
        whens = (NotifyType.BEFORE, NotifyType.AFTER, NotifyType.EXCEPTION)
    elif when == NotifyType.BOTH:
        whens = (NotifyType.BEFORE, NotifyType.AFTER)
    elif when is None:
        whens = (NotifyType.BEFORE, )
    elif isinstance(when, Iterable):
        whens = when
    else:
        # make an iterable of a single event
        whens = (when, )
    for when_ in whens:
        for event_ in events:
            if f not in _notify_map[when_][event_]:
                _notify_map[when_][event_].append(f)


def unsubscribe(f, event=None, when=None):
    """Remove a notify function.

    Optinally, constrain to the event and the when.
    The function :param:`f` needs to accept at least two paramters, the event
    being sent, and when it was sent.

    :param f: the function to deregister
    :type f: Callable[[str, *ANY, **ANY], None]
    :param event: the event to register the function against.
    :type event: Union[str, Iterable[str], None]
    :param when: when the function should be called.
    :type when: str
    """
    global _notify_map
    if when is None or when == NotifyType.ALL:
        whens = (NotifyType.BEFORE, NotifyType.AFTER, NotifyType.EXCEPTION)
    elif when == NotifyType.BOTH:
        whens = (NotifyType.BEFORE, NotifyType.AFTER)
    elif isinstance(when, Iterable):
        whens = when
    else:
        whens = (when, )
    if isinstance(event, Iterable):
        events = event
    elif event is not None:
        events = (event, )
    else:
        events = tuple()
    for when_ in whens:
        if event is None:
            events = _notify_map[when_].keys()
        for event_ in events:
            try:
                _notify_map[when_][event_].remove(f)
            except ValueError:
                pass


def notify(event, *args, when=None, **kwargs):
    """Notify registered handler functions.

    Can be called from code to notify handler functions that a notification has
    happened.

    Note that event doesn't have to be a NotifyEvents Enum; it can be anything
    that can be a dictionary key.  The NotifyEvents Enum members are 'special'
    in that subscribers can subscribe to the whole 'set' using None.

    :param event: the event to notify to subscribers.
    :type event: Union[NotifyEvents, str, ANY]
    :param when: the NotifyType event (BEFORE, AFTER, EXCEPTION) -- note
        that 'BOTH' and 'ALL' don't make much sense here!
    :type event: NotifyType
    """
    assert when in (
        None, NotifyType.BEFORE, NotifyType.AFTER, NotifyType.EXCEPTION), \
        "It doesn't make sense to notify on ALL NotifyTypes."
    try:
        functions = _notify_map[when][event]
    except KeyError:
        logger.debug("Invalid when: %s", when)
        return
    for f in functions:
        try:
            f(event, when, *args, **kwargs)
        except Exception as e:
            logger.error("Notification function %s failed with %s, args: %s"
                         ", kwargs:%s", str(f), str(e), args, kwargs)
            import traceback
            logger.error(traceback.format_exc())
            raise


class notify_around(ContextDecorator):
    """class is decorator and context manager.

    In order to match up BEFORE and AFTER events, a uuid field is included in
    the kwargs for loggers/etc.

    If an exception occurs in the wrapped function, then the
    NotifyType.EXCEPTION type is sent is used.
    """

    def __init__(self, event, *args, **kwargs):
        """Initialise a notify_around context/decorator."""
        self.event = event
        self.args = args
        self.kwargs = kwargs
        if 'uuid' not in kwargs:
            kwargs['uuid'] = str(uuid.uuid4())

    def __enter__(self):
        """Enter function for context/decorator."""
        notify(self.event,
               when=NotifyType.BEFORE,
               *self.args,
               **self.kwargs)
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        """Exit function for context/decorator."""
        if exc_type is not None:
            kwargs = self.kwargs.copy()
            kwargs["exc_args"] = (exc_type, exc, exc_tb)
            notify(self.event,
                   *self.args,
                   when=NotifyType.EXCEPTION,
                   **self.kwargs)
        else:
            notify(self.event,
                   *self.args,
                   when=NotifyType.AFTER,
                   **self.kwargs)
        # we don't actually handle the exception
        return False
