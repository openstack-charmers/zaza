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

"""Integrate zaza.events into zaza.notifications.

The intentions is for the tests.yaml to be used as:

    charm_name: none

    gate_bundles:
    - some-bundle

    tests:
    - zaza.plugins.events.start_auto_events
    - zaza.charm_tests.noop.tests.NoopTest
    - zaza.plugins.events.stop_auto_events

    tests_options:
      plugins:
        - zaza.plugins.events.configure
      zaza-events:
        log-format: InfluxDB
        keep-logs: false
        collection-name: DEFAULT
        collection-description: ""
        finalize-after-each-bundle: true
        raise-exceptions: false
        log-collection-name: "charm-upgrade-{bundle}-{date}"
        modules:
          - conncheck
          - logging:
              logger-name: DEFAULT
              log-to-stdout: false
              log-to-python-logging: true
              python-logging-level: debug
              logger-name: DEFAULT
        upload:
          - type: InfluxDB
            url: ${TEST_INFLUXDB_URL}
            user: ${TEST_INFLUXDB_USER}
            password: ${TEST_INFLUXDB_PASSWORD}
            database: charm_upgrade
            timestamp-resolution: us
          - type: S3
            etc.

    TODO: add these options; it would be nice to tag a collection, also to add
    custom fields.  The instrumentation of classes and functions is not done
    yet, although the test 'class' is run.

        tags:
          tag-name: tag-value
        fields:
          date: "{date}"
        instrument:
          test-classes: true
          test-function: true


Values with ${format} will expand to Environment Variables.
Values with {this} will be expanded with a common dictionary of values.

The plugin values are:

 - bundle_name: the name of the bundle, less the '.yaml' part.
 - date: today's date.
 - TODO: datetime: today's date and time.
 - TOSO: timestamp: the timestamp of the start of the test (in unix epoc
   non-float)

Converting zaza.notifications into zaza.events
==============================================

The zaza.notifications module emits events of enum.Enum type NotifyEvents.
Note that zaza.notifications can be other types, but this module only picks up
the ones it is interested in.

zaza.events events are Enum(str) (Events).  Also there is a strict set of
possible fields that make up an event as listed in list
zaza.event.types.FIELDS.
"""


from collections.abc import Iterable
import datetime
import logging
import os
from pathlib import Path
import tempfile

import zaza.charm_lifecycle.utils as utils
from zaza.global_options import get_option
import zaza.events.collection as ze_collection
from zaza.events.uploaders import upload_collection_by_config
from zaza.events import get_global_event_logger_instance
from zaza.notifications import subscribe, NotifyEvents, NotifyType
from zaza.utilities import cached, expand_vars

from .types import Events


logger = logging.getLogger(__name__)


class EventsPlugin:
    """The Events framework plugin.

    This provides the glue for connecting a tests.yaml to the time-series
    events framework that is in the zaza.events module.  The plugin provides:

     - glue that converts zaza.notifications into zaza.events
     - allowing configuration of the event system from the zaza.global_options
       system.
     - specifying and collecting all of the events
     - TODO: filtering/post-processing the event stream using filters.
     - uploading the events to a InfluxDB instance.
     - TODO: uploading events to an S3 API store.

    Note that the act of subscribing (using the subscribe() function) is what
    causes the EventsPlugin object to be retained for the program's run.  i.e.
    passing self.<function_name> to subscribe() provides the reference which
    holds the object in memory (as part of the notifications module).
    """

    def __init__(self, env_deployments):
        """Initialise the Events Plugin.

        :param env_deployments: the deployments/tests that will happen.
        :type env_deployments: List[EnvironmentDeploy]
        """
        self.env_deployments = env_deployments

        keep_logs = get_option('zaza-events.keep-logs', False)
        if keep_logs:
            self.logs_dir_base = os.path.join(
                tempfile.gettempdir(), "zaza-events")
            Path(self.logs_dir_base).mkdir(parents=True, exist_ok=True)
            logger.debug("Ensuring logs base dir as: %s", self.logs_dir_base)
        else:
            # get a directory that will disappear at the end of the program.
            self.logs_dir_base = tempfile.TemporaryDirectory("-zaza-events")

        # Handle all notifications and turn them into zaza.events for the
        # timeseries event logging.
        subscribe(self.handle_notifications, event=None, when=NotifyType.BOTH)

        # Handle the BEFORE and AFTER bundle notifications to actually create
        # and finalise the events logger after each deployment.
        subscribe(self.handle_before_bundle,
                  event=NotifyEvents.BUNDLE,
                  when=NotifyType.BEFORE)
        subscribe(self.handle_after_bundle,
                  event=NotifyEvents.BUNDLE,
                  when=NotifyType.AFTER)
        logger.info("Configured EventsPlugin.")

    def handle_before_bundle(
            self, event, when, *args, env_deployment=None, **kwargs):
        """Handle when a new bundle is about to be performed.

        This resets/configures the collection. This allows a complete test run
        be a bundle that gets all its logs collected and then saved "somewhere"
        according to the config.

        :param event: This must be NotifyEvents.BUNDLE
        :type event: NotifyEvents
        :param when: This must be NotifyType.BEFORE
        :type when: NotifyType
        :param *args: Any additional args passed; these are ignored.
        :type *args: Tuple(ANY)
        :param env_deployment: The deployment details for this model.
        :type env_deployment: EnvironmentDeploy
        :param **kwargs: Any additional kwargs; these are ignored.
        :type **kwargs: Dict[str, ANY]
        """
        logger.info("handle_before_bundle() called for env_deployment:%s",
                    env_deployment)
        assert event is NotifyEvents.BUNDLE
        assert when is NotifyType.BEFORE
        assert env_deployment is not None
        # Note that get_collection gets a zaza-events.* configured collection
        # if the collection-name key is present.
        collection = ze_collection.get_collection()
        collection.reset()
        context = event_context_vars(env_deployment)
        log_collection_name = expand_vars(
            context,
            get_option('zaza-events.log-collection-name', env_deployment.name))
        description = get_option('zaza-events.collection-description')
        logs_dir_name = expand_vars(context, "{{bundle}}-{{date}}")
        try:
            logs_dir_base = self.logs_dir_base.name
        except AttributeError:
            logs_dir_base = self.logs_dir_base
        logs_dir = os.path.join(logs_dir_base, logs_dir_name)
        Path(logs_dir).mkdir(parents=True, exist_ok=True)
        collection.configure(
            collection=log_collection_name,
            description=description,
            logs_dir=logs_dir)

        # Now configure any additional modules automagically
        modules = get_option('zaza-events.modules', [])
        if isinstance(modules, str) or not isinstance(modules, Iterable):
            logger.error("Option zaza-events.module isn't a list? %s",
                         modules)
            return
        for module_spec in modules:
            # if module is a dictionary then it's a key: spec, otherwise there
            # is no spec for the module.
            if isinstance(module_spec, dict):
                if len(module_spec.keys()) != 1:
                    logger.error(
                        "Module key %s is not formatted as a single-key "
                        "dictionary", module_spec)
                    continue
                module, config = list(module_spec.items())[0]
                if not isinstance(config, dict):
                    logger.error(
                        "Module key %s has invalid config %s", module, config)
                    continue
            elif isinstance(module_spec, str):
                module, config = (module_spec, {})
            else:
                logger.error("Can configure with %s.", module_spec)
                continue
            configure_func = (
                "zaza.events.plugins.{}.auto_configure_with_collection"
                .format(module))
            try:
                logger.info("Running autoconfigure for zaza-events func %s()",
                            configure_func)
                utils.get_class(configure_func)(collection, config)
            except Exception as e:
                logger.error(
                    "Error running autoconfigure for zaza-events %s: %s",
                    configure_func, str(e))
                if get_option('zaza-events.raise-exceptions', False):
                    raise

        # events = logging_manager.get_global_event_logger_instance()
        events = get_global_event_logger_instance()
        events.log(Events.START_TEST,
                   comment="Starting {}".format(log_collection_name))

    def handle_after_bundle(
            self, event, when, env_deployment=None, *args, **kwargs):
        """Handle when the test run is complete.

        This is the stage when the logs are finalised, processed, and then
        uploaded to where they should be stored (according to the config).

        :param event: This must be NotifyEvents.BUNDLE
        :type event: NotifyEvents
        :param when: This must be NotifyType.AFTER
        :type when: NotifyType
        :param *args: Any additional args passed; these are ignored.
        :type *args: Tuple(ANY)
        :param env_deployment: The deployment details for this model.
        :type env_deployment: EnvironmentDeploy
        :param **kwargs: Any additional kwargs; these are ignored.
        :type **kwargs: Dict[str, ANY]
        """
        assert event is NotifyEvents.BUNDLE
        assert when is NotifyType.AFTER
        events = get_global_event_logger_instance()
        events.log(Events.END_TEST, comment="Test ended")
        collection = ze_collection.get_collection()
        collection.finalise()

        for (name, type_, filename) in collection.log_files():
            logger.debug(
                "Found logs for %s type(%s) %s", name, type_, filename)

        upload_collection_by_config(
            collection, context=event_context_vars(env_deployment))

        logger.info("Completed event logging and uploads for for %s.",
                    collection.collection)

    @staticmethod
    def handle_notifications(event, when, *args, **kwargs):
        """Handle a notification event fromt zaza.notifications.

        By definition, the config for zaza-events must be available as
        otherwise this function can't be called.

        The event (a NotifyEvents) is used as it's str version of the event
        logger.  A before or after is added if the NotifyType is BEFORE or
        AFTER.

        TODO: There probably needs to be filtering as kwargs may end up having
        params that just don't map to time-series events.  e.g. more work is
        needed here (probably) to translate between notifications and
        time-series events.

        Note: every NotifyEvents is also an z.e.types.Events event.  This
        converts from NotifyEvents to Events before calling log().

        :param event: the event that has been notified
        :type event: NotifyEvents
        :param when: the 'place' of the event (NotifyType.?)
        :type when: NotifyType
        """
        assert isinstance(event, NotifyEvents)
        # don't log events that are already handled.
        if event == NotifyEvents.BUNDLE:
            return
        logger.debug("handle_notifications: %s, %s, %s, %s",
                     event, when, args, kwargs)
        events = get_global_event_logger_instance()
        if 'span' not in kwargs:
            if when == NotifyType.BEFORE:
                kwargs['span'] = "before"
            elif when == NotifyType.AFTER:
                kwargs['span'] = "after"

        # transform the NotifyEvents into a Events object.
        event_ = _convert_notify_into_events(event)
        kwargs = _convert_notify_kwargs_to_events_args(kwargs)
        events.log(event_, **kwargs)


@cached
def _convert_notify_into_events(notify_event):
    """Convert a NotifyEvents into a Events.

    :param notify_event: the event to downcast
    :type notify_event: NotifyEvents
    :returns: the event, cast as an Events object
    :rtype: Events
    :raises ValueError: if the event can't be converted.
    """
    v = notify_event.value
    for ev in Events:
        if ev.value == v:
            return ev
    raise ValueError(
        "Can't convert {} into an Events object".format(notify_event))


def third(_, __, x):
    """Return the 3rd param, ignoring the first two.

    Return the 3rd param value unchanged, ignoring the first two params.
    """
    return x


def pick(attr):
    """Return a function that picks 'attr' from the 3rd param to that fn.

    If attr doesn't exist on the object, then just return the object.

    :param attr: the attribute to get from the 3rd param of the function that
    will be returned.
    :type attr: str
    :returns: A function that takes 3 params and returns the 3rd with a picked
        attribute
    :rtype: Callable[[Any, Any, object], Any]
    """
    return lambda _, __, x: getattr(x, attr, x)


def dict_item_apply(f):
    """Apply function 'f' to the parameters passed and update the dict.

    This returns a function that takes a (current, key, value) where 'current'
    is the current value, a dictionary or None, key is original field, and
    value is the original value.  'f' gets to transform that value, which is
    then applied to the dictionary, which is then returned.

    :param f: the function to apply
    :type f: Callable[[dict, Any, Any], dict]
    """
    def _inner(current, key, value):
        if current is None:
            current = {}
        current[key] = f(current, key, value)
        return current

    return _inner


def trim(f, size=10):
    """Apply function 'f' to the parameters passed and then trim the str.

    The function returns a function that takes (current, key, value) which is
    passed to the 'f' function.

    :param f: the function to call, and then trim the results of.
    :type f: Callable
    :returns: the trimmed string
    :rtype: str
    """
    def _inner(*args):
        res = f(*args)
        if isinstance(res, str):
            res = res[-size:]
        return res

    return _inner


# map to indicate how to convert from a NotifyEvents field name into an Events
# field name.  The first part of the tuple is the target field, the second is a
# function that takes 3 params (current value of kwargs field, the NotifyEvents
# field name, value of that NoitifyEvent) and should return the new value.
_convert_map = {
    "model_name": ("tags", dict_item_apply(third)),
    "function": ("tags", dict_item_apply(pick("__name__"))),
    "bundle": ("item", trim(third, 20)),
    "model": ("tags", dict_item_apply(third)),
    "model_ctxt": (None, None),
    "force": ("tags", dict_item_apply(third)),
    "testcase": ("item", pick("__name__")),
    "test_name": ("tags", dict_item_apply(pick("__name__"))),
}


def _convert_notify_kwargs_to_events_args(kwargs):
    """Convert the custom parameters into events args.

    This also discards any 'unknown' arguments so that they do not end up in
    the event (and thus potentially break uploaders).  Any non "str" values
    left over are 'str'ed.

    :params kwargs: the key-value args provided for fields and tags
    :type kwargs: Dict[str, Any]
    :returns: key-value pairs compatible with Events events.
    :rtype: Dict[str, str]
    """
    for k, v in kwargs.copy().items():
        if k in _convert_map:
            key, _convert_fn = _convert_map[k]
            if key is not None:
                kwargs[key] = _convert_fn(kwargs.get(key, None), k, v)
            del kwargs[k]
        elif not isinstance(v, str):
            kwargs[k] = str(v)
    return kwargs


@cached
def event_context_vars(env_deployment):
    """Return context variables for zaza-events configuration params.

    Note that it is cached because env_deployment is immutable, and the date
    should only be evaluated the first time.

    The "bundle" var is derived from the first model if there is only ONE
    model, otherwise the Environment name: e.g.:

        EnvironmentDeploy(
            name='default1',
            model_deploys=[
                ModelDeploy(
                    model_alias='default_alias',
                    model_name='zaza-b9413598c856',
                    bundle='conncheck-focal'
                )
            ],
            run_in_series=True
        )

    In the above case the "bundle" will be conncheck-focal.  If there was more
    than one model in the env deployment, the the "bundle" would be "default1".

    :param env_deployment: the deployment parameters.
    :type env_deployment: EnvironmentDeploy
    :returns: context vars for use in expanding a configuation param.
    :rtype: Dict[str, str]
    """
    if len(env_deployment.model_deploys) == 1:
        bundle = env_deployment.model_deploys[0].bundle
    else:
        bundle = env_deployment.name
    return {
        'date': "{}us".format(int(datetime.datetime.now().timestamp() * 1e6)),
        'bundle': bundle,
    }


def start_auto_events():
    """Start event logging on the configured logger.

    TODO: implement starting and stopping logging.
    """
    pass


def stop_auto_events():
    """Stop event logging on the configured logger.

    TODO: implement starting and stopping logging.
    """
    pass
