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

"""Events instrumentation test runner integration plugin.

This 'plugin' allows tests to switch on instrumentation of tests as time series
events.  This allows a tests.yaml to configure and enable/disable test
instrumentation at will.

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
    events-logger-name: DEFAULT
    collection-description: ""
    logger-name: DEFAULT
    log-to-stdout: false
    log-to-python-logging: true
    python-logging-level: debug
    finalize-after-each-bundle: true
    raise-exceptions: false
    upload:
      - type: InfluxDB
        url: ${TEST_INFLUXDB_URL}
        user: ${TEST_INFLUXDB_USER}
        password: ${TEST_INFLUXDB_PASSWORD}
        database: charm_upgrade
        timestamp-resolution: us
      - type: S3
        etc.
    log-collection-name: "charm-upgrade-{bundle}-{date}"
    tags:
      tag-name: tag-value
    fields:
      date: "{date}"
    instrument:
      test-classes: true
      test-function: true


Things in ${format} will expand to Environment Variables.
Things like {this} will be expanded with a common dictionary of values.

The plugin values are:

 - bundle_name: the name of the bundle, less the '.yaml' part.
 - date: today's date.
 - datetime: today's date and time.
 - timestamp: the timestamp of the start of the test (in unix epoc non-float)
"""

from collections.abc import Iterable, Mapping
import datetime
import enum
import itertools
import logging
import os
from pathlib import Path
import tempfile

import requests

from zaza.global_options import get_option
import zaza.events.collection as ze_collection
import zaza.events.plugins.logging
from zaza.events.formats import LogFormats
from zaza.notifications import subscribe, NotifyEvent, NotifyType
from zaza.utilities import cached


logger = logging.getLogger(__name__)


def configure(env_deployments):
    """Configure the event for events.

    This grabs the test_options.zaza-events key from the options and configures
    a collection, a logger, and where to put the logs afterwards.

    :param env_deployments: the deployments/tests that will happen.
    :type env_deployments: List[EnvironmentDeploy]
    """
    config = get_option("zaza-events", raise_exception=False)
    if config is None:
        logger.error(
            "zaza.events.configure called, but no configuration found")
        return

    # Note that the subscriptions in the __init__() will keep events_plugin
    # around until the end of the program run.
    EventsPlugin(env_deployments)


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
        collection = _get_collection()
        collection.reset()
        log_collection_name = expand_vars(
            env_deployment,
            get_option('zaza-events.log-collection-name', env_deployment.name))
        description = get_option('zaza-events.collection-description')
        logs_dir = expand_vars(env_deployment, "{{bundle}}-{{date}}")
        Path(logs_dir).mkdir(parents=True, exist_ok=True)
        collection.configure(
            collection=log_collection_name,
            description=description,
            logs_dir=logs_dir)
        logging_manager = get_logging_manager()
        collection.add_logging_manager(logging_manager)
        event_logger = logging_manager.get_logger()
        if get_option('zaza-events.log-to-stdout'):
            zaza.events.plugins.logging.add_stdout_to_logger(event_logger)
        if get_option('zaza-events.log-to-python-logging'):
            level = get_option(
                'zaza-events.python-logging-level', 'debug').upper()
            level_num = getattr(logging, level, None)
            if not isinstance(level_num, int):
                raise ValueError('Invalid log level: "{}"'.format(level))
            event_logger.add_writers(zaza.events.plugins.logging.get_writer(
                LogFormats.LOG,
                zaza.events.plugins.logging.HandleToLogging(level)))
        events = logging_manager.get_event_logger()
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
        events = get_logging_manager().get_event_logger()
        events.log(zaza.events.END_TEST, comment="Test ended")
        collection = _get_collection()
        collection.finalise()

        # 1. Access all the log files:
        for (name, type_, filename) in collection.log_files():
            logger.debug(
                "Found logs for %s type(%s) %s", name, type_, filename)

        # 2. do something with the logs (i.e. upload to a database)
        uploads = get_option('zaza-events.upload', [])
        if isinstance(uploads, str):
            uploads = (uploads, )
        if not isinstance(uploads, Iterable):
            logger.error("No where to upload logs? %s", uploads)
            return
        for upload in uploads:
            if not isinstance(upload, Mapping):
                logger.error(
                    "Ignoring upload; it doesn't seem correcly formatted?",
                    upload)
                continue
            try:
                upload_type = upload['type']
            except KeyError:
                logger.error("No type provided for upload, ignoring: %s",
                             upload)
                continue
            # TODO: this would be nicer as a dict lookup to make it more
            # flexible, but for the moment, we only support InfluxDB
            if not isinstance(upload_type, str):
                logger.error("upload type is not a str, ignoring: %s",
                             upload_type)
                continue
            upload_type = upload_type.lower()
            if upload_type == "influxdb":
                self._upload_influxdb(upload, collection)
            else:
                logger.error("Unknown type %s for uploading; ignoring",
                             upload_type)

        logger.info("Completed event logging and uploads for for %s.",
                    collection.collection)

    def _upload_influxdb(self, upload_spec, collection):
        """Upload a collection of events to an InfluxDB instance.

        This uses a POST to upload data to a named database at a URL with a
        particular timestamp-resolution.  If present, the user and password are
        used to do the upload.  A batch size of events is also used.  Events
        have to be in InfluxDB Line Protocol format, in the collection.

            type: InfluxDB
            url: ${INFLUXDB_URL}
            user: ${INFLUXDB_USER}
            password: ${INFLUXDB_PASSWORD}
            database: charm_upgrade
            timestamp-resolution: us
            batch-size: 1000
            raise-exceptions: false

        Note that this won't generate an exception (e.g. there's no database,
        etc.), unless raise-exceptions is true.  It will just log to the file.

        Note that the timestamp-resolution is one of: ns, us, ms, s.

        The line protocol for 1.8 is one of n, u, ms, s, m, h.  Thus, this
        function maps ns -> n, and us -> u as part of the upload.  m and h are
        not supported.

        :param upload_spec: the upload specification of where to send the logs.
        :type upload_spec: Dict[str, str]
        :param collection: the collection whose logs to upload.
        :type collection: zaza.events.collection.Collection
        """
        assert upload_spec['type'].lower() == "influxdb"
        raise_exceptions = upload_spec.get('raise-exceptions', False)
        user = upload_spec.get('user', None)
        password = upload_spec.get('password', None)
        timestamp_resolution = upload_spec.get('timestamp-resolution', 'u')
        batch_size = upload_spec.get('batch-size', 1000)
        try:
            url = upload_spec['url']
        except KeyError:
            logger.error("No url supplied to upload for InfluxDB.")
            if raise_exceptions:
                raise
            return
        try:
            database = upload_spec['database']
        except KeyError:
            logger.error("No database supplied to upload for InfluxDB.")
            if raise_exceptions:
                raise
            return

        url = os.path.expandvars(url)
        database = os.path.expandvars(database)

        # map the precision to InfluxDB.
        try:
            precision = {'ns': 'n',
                         'us': 'u',
                         'ms': 'ms',
                         's': 's'}[timestamp_resolution]
        except KeyError:
            logger.error("Precision isn't one of ns, us, ms or s: %s",
                         timestamp_resolution)
            if raise_exceptions:
                raise
            return

        if not url.endswith("/"):
            url = "{}/".format(url)
        post_url = "{}write?db={}&precision={}".format(
            url, database, precision)
        if user:
            post_url = "{}&u={}".format(post_url, os.path.expandvars(user))
        if password:
            post_url = "{}&p={}".format(post_url, os.path.expandvars(password))

        # Now got all the possible information to be able to do the uplaods.
        logger.info(
            "Starting upload to InfluxDB, database: %s, user: %s, "
            "precision: %s, batch_size: %s",
            database, user, timestamp_resolution, batch_size)

        with collection.events(precision=timestamp_resolution) as events:
            while True:
                batch_events = itertools.islice(events, batch_size)
                batch = "\n".join(b[1] for b in batch_events)
                if not batch:
                    break
                # Essentially: curl -i -XPOST 'http://172.16.1.95:8086/write?
                #               db=mydb&precision=u' --data-binary @batch.logs
                try:
                    result = requests.post(post_url, data=batch)
                except Exception as e:
                    logger.error("Error raised when uploading batch: %s",
                                 str(e))
                    if raise_exceptions:
                        raise
                    return
                if result.status_code not in (requests.codes.ok,
                                              requests.codes.no_content,
                                              requests.codes.accepted):
                    logger.error(
                        "Batch upload failed.  status_code: %s",
                        result.status_code)
                    if raise_exceptions:
                        result.raise_for_status()
                    logger.error("Abandoning batch upload to InfluxDB")
                    return

        logger.info(
            "Finished upload to InfluxDB, database: %s, user: %s, "
            "precision: %s, batch_size: %s",
            database, user, timestamp_resolution, batch_size)

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
        events = get_logging_manager().get_event_logger()
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


def expand_vars(env_deployment, value):
    """Search the variable and see if variables need to be expanded.

    This expands ${ENV} and {context} variables in a :param:`value` parameter.

    :param env_deployment: the deployment parameters.
    :type env_deployment: environmentdeploy
    :param value: the value to do variable expansion on.
    :type value: str
    :returns: the expanded string
    :rtype: str
    """
    if not isinstance(value, str):
        return value
    value = os.path.expandvars(value)
    context = event_context_vars(env_deployment)
    for k, v in context.items():
        var = "{" + k + "}"
        if var in value:
            value = value.replace(var, v)
    return value


def _get_collection():
    """Return the collection as defined in the plugin specification.

    :returns: the collection for time-series events.
    :rtype: zaza.events.collection.Collection
    """
    return ze_collection.get_collection(
        name=get_option("zaza-events.collection-name", "DEFAULT"))


def get_logging_manager():
    """Return the events logging manager (for the collection).

    This returns the logging manager for logging time-series events from within
    zaza tests.  The advantage of using this is that it taps into the
    global_options to get the 'right' one for the test.

    Note: if there are no zaza-events options configured the 'DEFAULT' event
    logging manager will be returned, which if nothing is configured, won't do
    anything with logs if a logger is requested and then used.

    :returns: the configured logging manager.
    :rtype: zaza.events.plugins.logging.LoggerPluginManager
    """
    name = get_option("zaza-events.events-logger-name", None)
    if name is None:
        name = get_option("zaza-events.collection-name", "DEFAULT")
    return zaza.events.plugins.logging.get_plugin_manager(name)


def get_logger():
    """Get a logger with no prefilled fields.

    This gets the options configured event logger BUT with no prefilled fields.
    You almost certainly want the get_event_logger() version.

    :returns: get a configured, but with no pre-filled fields, EventLogger
    :rytype: zaza.events.plugins.logging.EventLogger
    """
    return get_logging_manager().get_logger()


def get_event_logger():
    """Get an event logger with prefilled fields for the collection.

    This returns an options configured event logger (proxy) with prefilled
    fields.  This is almost CERTAINLY the event logger that you want to use in
    zaza test functions.

    :returns: a configured LoggerInstance with prefilled collection and unit
        fields.
    :rtype: LoggerInstance
    """
    return get_logging_manager().get_event_logger()


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
