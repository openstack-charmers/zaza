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
"""


from collections.abc import Iterable
import datetime
import enum
import logging
import os
from pathlib import Path
import tempfile

import zaza.charm_lifecycle.utils as utils
from zaza.global_options import get_option
import zaza.events.collection as ze_collection
import zaza.events.plugins.logging
from zaza.events.uploaders import upload_collection_by_config
from zaza.events import get_event_logger
from zaza.notifications import subscribe, NotifyEvent, NotifyType
from zaza.utilities import cached, expand_vars


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
        subscribe(self.handle_notifications, event=None, when=None)

        # Handle the BEFORE and AFTER bundle notifications to actually create
        # and finalise the events logger after each deployment.
        subscribe(self.handle_before_bundle,
                  event=NotifyEvent.BUNDLE,
                  when=NotifyType.BEFORE)
        subscribe(self.handle_after_bundle,
                  event=NotifyEvent.BUNDLE,
                  when=NotifyType.AFTER)

    def handle_before_bundle(
            self, event, when, *args, env_deployment=None, **kwargs):
        """Handle when a new bundle is about to be performed.

        This resets/configures the collection. This allows a complete test run
        be a bundle that gets all its logs collected and then saved "somewhere"
        according to the config.

        :param event: This must be NotifyEvent.BUNDLE
        :type event: NotifyEvent
        :param when: This must be NotifyType.BEFORE
        :type when: NotifyType
        :param *args: Any additional args passed; these are ignored.
        :type *args: Tuple(ANY)
        :param env_deployment: The deployment details for this model.
        :type env_deployment: EnvironmentDeploy
        :param **kwargs: Any additional kwargs; these are ignored.
        :type **kwargs: Dict[str, ANY]
        """
        assert event is NotifyEvent.BUNDLE
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
        logs_dir = os.path.join(self.logs_dir_base, logs_dir_name)
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
                module, config = module_spec.items()[0]
                if not isinstance(config, dict):
                    logger.error(
                        "Module key %s has invalid config %s", module, config)
                    continue
            elif isinstance(module_spec, str):
                module, config = (module_spec, {})
            else:
                logger.error("Can configure with %s.", module_spec)
                continue
            configure_func = ("zaza.events.plugins.{}.auto_configure_with"
                              .format(module))
            try:
                logger.debug("Running autoconfigure for zaza-events func %s.",
                             configure_func)
                utils.get_class(configure_func)(collection, config)
            except Exception as e:
                logger.error(
                    "Error running autoconfigure for zaza-events %s: %s",
                    configure_func, str(e))
                if get_option('zaza-events.raise-exceptions', False):
                    raise

        # logging_manager = get_logging_manager()
        # events = logging_manager.get_event_logger()
        events = get_event_logger()
        events.log(zaza.events.START_TEST,
                   comment="Starting {}".format(log_collection_name))

    def handle_after_bundle(
            self, event, when, env_deployment=None, *args, **kwargs):
        """Handle when the test run is complete.

        This is the stage when the logs are finalised, processed, and then
        uploaded to where they should be stored (according to the config).

        :param event: This must be NotifyEvent.BUNDLE
        :type event: NotifyEvent
        :param when: This must be NotifyType.AFTER
        :type when: NotifyType
        :param *args: Any additional args passed; these are ignored.
        :type *args: Tuple(ANY)
        :param env_deployment: The deployment details for this model.
        :type env_deployment: EnvironmentDeploy
        :param **kwargs: Any additional kwargs; these are ignored.
        :type **kwargs: Dict[str, ANY]
        """
        assert event is NotifyEvent.BUNDLE
        assert when is NotifyType.AFTER
        # events = get_logging_manager().get_event_logger()
        events = get_event_logger()
        events.log(zaza.events.END_TEST, comment="Test ended")
        collection = ze_collection.get_collection()
        collection.finalise()

        # 1. Access all the log files:
        for (name, type_, filename) in collection.log_files():
            logger.debug(
                "Found logs for %s type(%s) %s", name, type_, filename)

        # 2. do something with the logs (i.e. upload to a database)
        upload_collection_by_config(
            collection, context=event_context_vars(env_deployment))

        logger.info("Completed event logging and uploads for for %s.",
                    collection.collection)

    @staticmethod
    def handle_notifications(event, when, *args, **kwargs):
        """Handle a notification event fromt zaza.notifications.

        By definition, the config for zaza-events must be available as
        otherwise this function can't be called.

        The event (a NotifyEvent) is used as it's str version of the event
        logger.  A before or after is added if the NotifyType is BEFORE or
        AFTER.

        TODO: There probably needs to be filtering as kwargs may end up having
        params that just don't map to time-series events.  e.g. more work is
        needed here (probably) to translate between notifications and
        time-series events.

        :param event: the event that has been notified
        :type event: NotifyEvent
        :param when: the 'place' of the event (NotifyType.?)
        :type when: NotifyType
        """
        # don't log events that are already handled.
        if event == NotifyEvent.BUNDLE:
            return
        logger.debug("handle_notifications: %s, %s, %s, %s",
                     event, when, args, kwargs)
        # events = get_logging_manager().get_event_logger()
        events = get_event_logger()
        if isinstance(event, enum.Enum):
            event = event.value
        if when in (NotifyType.BEFORE, NotifyType.AFTER):
            if isinstance(when, enum.Enum):
                when = when.value
            event = "{}-{}".format(event, when)
        # TODO: filter/transform kwargs to be valid for Time-series events?
        events.log(event, **kwargs)


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
