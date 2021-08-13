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

"""Time Series Orientated Event Logging framework.

This module is designed to be used to capture time series test events during a
series of test runs.

A 'test event' is a distinct from 'logging', in that it allows capturing of
specific events during a test that will then be analysed post test run.

For zaza, as a Juju testing framework, this means:

 * Extract juju hook timings from machine logs on units/machines.
 * Provide a framework for logging TS (time-series) events from the test-code.
   e.g. when a deploy starts and ends to allow deployment timing to be
   assessed.

The key concept is that it provides event loggers and mechanisms to track the
logs of multiple sources and coalasce them into a single TS log that can then
be uploaded to (say) InfluxDB and viewed/analysed using Grafana or a Jupyter
Notebook.

The key idea is loose coupling of various EventLoggerBase classes that,
together, will form the TS event history of a test run.

Ergonomics
==========

// TODO needs re-writing a bit

The module provides a `get_event_logger()` function to allow adding events to
the log for a test run. Note this is not a logging.get_logger()!

Events are ordered by time, and have the following fields:

- datetime | test_run_id | unit | item | event | fields

There is always a "DEFAULT" logger, but other name-spaced loggers can be used;
this is not really expected to be needed, as it would imply more than one
test-run running at the same time.

In the case for, say a charm-upgrade test:

    logger = zaza.events.get_event_logger()
    logger.enable()  # need to enable it, otherwise, no logs.
    events = logger.prefill_with(collection="bionic-queens-charm-upgrade",
                                 unit=test_name)
    charm_events = events.prefill_with(item=charm_name)
    charm_events.log_event(zaza.events.START)
    charm_events.log_event(zaza.events.STAGE, msg="set config to xx")
    ...
    charm_events.log_event(Events.END)

Note that some events are predefined (they are just strings) to help to ensure
that common set of events are used across units and items.

Multiple log sources
--------------------

The events module supports multiple log sources, via EventLoggerBase.

    logger = zaza.events.get_event_logger()
    # create another source of events.
    conncheck = zaza.openstack.utilities.conncheck.ConnCheck(...)
    logger.add_source(conncheck)

    # time passes.
    # at the end of the test run.
    logger.finalise()   # consolidate all the log files and finish it.
    # now access logs a series of events.
    with logger.events() as ev:
        for event in ev:
            # do something with an events.

    # or (ASPIRATIONAL - not done yet!)
    logger.upload_to_influxdb(influx_config)


Structure of Logging plugin
===========================

The main components:

 - LoggerPluginManager:
       This plugs the 'standalone' event logging into the
       zaza.events.collection.Collection class.  This is how the logs from
       tests and zaza can be combined with events generated from other plugins.

 - EventLogger
   - LoggerInstance
       These two classes manage the logging.  The EventLogger object 'holds'
       the WriterBase classes that provide the mechanism for formatting and
       then writing to a logged location.  The 'LoggerInstance' provides the
       log() method that actually does a log; this calls the EventLogger._log()
       method that then calls the writers.

 - WriterFile
       This manages a file on behalf of a Writer.

 - WriterBase
   - WriterCSV
   - WriterDefault
   - WriterLineProtocol
       These are the actual format writers.  WriterDefault is for human
       readable output, whereas the other two are for machine consumption.

 - HandleToLogging
       This small class provides a WriterFile like interface, but provides
       writing to a Python Logger.
"""

import tempfile
import atexit
import datetime
import logging
import os
import sys
import uuid
import weakref

from zaza.events.plugins import PluginManagerBase
from zaza.events.types import LogFormats, Events, Span, FIELDS


logger = logging.getLogger(__name__)


###############################################################################

# Auto-configure a logger according to config.

###############################################################################

def auto_configure_with_collection(collection, config=None):
    """Auto-configure the plugin with the collection.

    This uses the config passed (if any) to auto-configure the logging plugin
    with the collection.  Normally, config is passed as part of global_options.
    This function is called from zaza/events/notifications.handle_before_bundle
    function if the logging module is configured.

    The config looks like:

        logger-name: DEFAULT
        log-to-stdout: false
        log-to-python-logging: true
        python-logging-level: debug
        logger-name: DEFAULT

    These are the default values.

    :param collection: the colletion to auto-configure logging on to.
    :type collection: zaza.events.collection.Collection
    :param config: config to use to perform the auto-configuration.
    :type config: Dict[str, ANY]
    """
    logger.info("autoconfigure_with_collection for logging called.")
    name = config.get("logger-name", "DEFAULT")
    logging_manager = get_plugin_manager(name)

    collection.add_logging_manager(logging_manager)
    event_logger = logging_manager.get_logger()

    if config.get('log-to-stdout', False):
        logger.info("Setting event logging to STDOUT")
        add_stdout_to_logger(event_logger)
    if config.get('log-to-python-logging', False):
        level = config.get('python-logging-level', 'debug').upper()
        level_num = getattr(logging, level, None)
        if not isinstance(level_num, int):
            raise ValueError('Invalid log level: "{}"'.format(level))
        logger.info(
            "Setting event-logging to Python logging system at level %s",
            level)
        event_logger.add_writers(
            make_writer(LogFormats.LOG,
                        HandleToLogging(name="auto-logger",
                                        level=level_num,
                                        python_logger=logger)))


###############################################################################

# Module API functions for getting loggers of various kinds.

###############################################################################

_loggers = dict()


def get_logger(name="DEFAULT"):
    """Get an EventLogger by name.

    The name is the logger to get.  This is global so that it can be fetched
    from any module.  This is probably not useful as there is no 'log' method.
    Use :function:`get_logger_instance` for a useful logger.

    :param name: the name of the logger.
    :type name: str
    :returns: the logger instance
    :rtype: EventLogger
    """
    global _loggers
    if name not in _loggers:
        _loggers[name] = EventLogger(name)
    return _loggers[name]


def get_logger_instance(name="DEFAULT", **kwargs):
    """Get an LoggerInstance by name.

    The name is the logger to get.  This is global so that it can be fetched
    from any module.

    The :param:`kwargs` can be used to prefill the keys on the logger.  See
    also the :method:`prefill_with` available on the :class:`EventLogger` and
    :class:`LoggerInstance` classes.

    :param name: the name of the logger.
    :type name: str
    :param kwargs: key-value pairs to preconfigure fields in the
        LoggerInstance.
    :type kwargs: Dict[str, Any]
    :returns: the logger instance
    :rtype: LoggerInstance
    """
    return get_logger(name).get_logger_instance(**kwargs)


def add_stdout_to_logger(name_or_logger="DEFAULT"):
    """Add a stdout, default logger, to the named logger.

    This adds a Default log writer (to stdout) to an event logger.
    :param name: the name of the logger.
    :type name: Union[str, EventLogger]
    """
    if isinstance(name_or_logger, EventLogger):
        logger = name_or_logger
    else:
        logger = get_logger(name_or_logger)
    logger.add_writers(WriterDefault(sys.stdout))


###############################################################################

# LoggerPluginManager - plug EventLogger into z.e.collection.Collection

###############################################################################

_logger_plugin_managers = dict()


def get_plugin_manager(name="DEFAULT"):
    """Return the Collection Plugin manager for events logging.

    :param name: the name of the logger to be associated with the plugin.
    :type name: str
    :returns:  the Logger plugin manager
    :rtype: LoggerPluginManager
    """
    global _logger_plugin_managers
    try:
        return _logger_plugin_managers[name]
    except KeyError:
        _logger_plugin_managers[name] = LoggerPluginManager(managed_name=name)
        return _logger_plugin_managers[name]


class LoggerPluginManager(PluginManagerBase):
    """The Logger plugin manager to connect to a z.e.collection.Collection.

    This allows the event logger (for use in tests) to be part of a collection
    (and thus be interweaved with other pluggable loggers.)
    """

    def __init__(self, **kwargs):
        """Create a LoggerPluginManager."""
        self.filename = None
        self._managed_writer = None
        self._managed_writer_file = None
        super().__init__(**kwargs)

    def configure_plugin(self):
        """Configure the Event Logger plugin.

        This uses the managed_name to get the same named logger, and configures
        a writer with the log format of the Collection.  It opens the file
        (using the WriterLogFile) and connects it into the logger.

        So there are a few kinds of writer: CSV, LOG, INFLUXDB, and the
        writer.name is the kind of writer.  writer's are differentiated
        according to their handle and name.  The same handle and name can be
        used in multiple loggers, (although that would be unusual)!
        """
        if self.filename is None:
            name = "{}_{}_{}.log".format(
                self.collection, self.log_format, str(uuid.uuid4())[-8:])
            self.filename = os.path.join(self.logs_dir, name)
        self._managed_writer_file = WriterFile(self.log_format, self.filename)
        self._managed_writer = make_writer(
            self.log_format, self._managed_writer_file.handle)
        # now wire it in to the logger
        event_logger = get_logger(self.managed_name)
        event_logger.add_writers(self._managed_writer)

    def get_logger(self):
        """Return the EventLogger associated with this item.

        :returns: an EventLogger instance
        :rtype: EventLogger
        """
        return get_logger(self.managed_name)

    def get_event_logger_instance(self):
        """Return the logger instance associated with this item.

        In particular, the collection is pre-filled on the logger so that it
        doesn't need to be set each time.

        :returns: an LoggerInstance instance
        :rtype: LoggerInstance
        """
        try:
            return self.get_logger().get_logger_instance(
                collection=self.collection, unit=self.managed_name)
        except AttributeError:
            # If it goes bang, it's probably not configured, so just return the
            # default logger.
            return get_logger().get_logger_instance()

    def finalise(self):
        """Finalise the writers in the logger.

        The self.logs_dir (if used) is guarranteed to still exist after this
        function, so logs don't have to be moved; we just have to disable the
        writter in the logger.
        """
        if self._managed_writer is None:
            logger.warning(
                "LoggerPluginManager: doesn't have a managed writer to "
                "finalise.")
            return
        event_logger = get_logger(self.managed_name)
        event_logger.remove_writer(self._managed_writer)
        self._managed_writer_file.close()

    def log_files(self):
        """Return an iterator of (name, log format, filename).

        This is from all of the managers.

        :returns: A list/iterator of tuples of (name, log format, filename)
        :rtype: Iterator[Tuple[str, str, str]]
        """
        yield (self.managed_name, self.log_format, self.filename)

    def clean_up(self):
        """Clean up the log file."""
        pass
        # TODO: have a configurable option to remove the log file.

    def reset(self):
        """Reset the logger so it can be used again."""
        if self._managed_writer is not None:
            self.finalise()
            self._managed_writer_file = None
            self._managed_writer = None
        self.filename = None


###############################################################################

# EventLogger - the core 'logging' class.

###############################################################################

class EventLogger:
    """Event logging class to log events."""

    def __init__(self, name):
        """Initialise an empty EventLogger.

        :param name: the name of this logger; typically DEFAULT
        :type name: str
        """
        self.name = name
        self._writers = []

    def get_logger_instance(self, **kwargs):
        """Return an instance logger for this event logger.

        :param:`kwargs` allows for prefilling fields, and thus allows the user
        of the event logging system to prefill some parameters and then use
        that logger more simply.

        :param kwargs: the fields to prefill.  e.g. unit='my-unit'.
        :type kwargs: Dict[str, Any]
        :returns: A LoggerInstance proxy for the EventLoger.
        :rtype: LoggerInstance
        """
        return LoggerInstance(self, **kwargs)

    def _log(self, event, newline=True, **kwargs):
        """Log an event.

        This writes the log to each of the writers that is attached to the
        logger.

        If "span" is passed in the kwargs and the value is a span() object,
        then the uuid is pulled out and placed as 'uuid' in the log.

        :param event: the event that is being logged.
        :type event: zaza.events.types.Event
        :param newline: Whether to make sure a newline is added.
        :type newline: bool
        :param kwargs: Key=value pairs to include in the log.
        :type kwargs: Dict[str, Any]
        """
        assert isinstance(event, Events), (
            "Mustn't pass a non-Events Enum event '{}', type({}), to {}.log()"
            .format(event, type(event), self.__class__.__name__))
        kwargs['event'] = event.value
        if 'timestamp' not in kwargs:
            kwargs['timestamp'] = datetime.datetime.now()
        if 'span' in kwargs and isinstance(kwargs['span'], span):
            span_ = kwargs.pop('span')
            kwargs['uuid'] = span_.uuid
        self._validate_attrs(kwargs)
        for writer in self._writers:
            writer.write(newline=newline, **kwargs)

    def _validate_attrs(self, kwargs):
        """Valdiate that keys (from the kwargs passed as a Dict).

        The valid keys are those that are typically used as fields.  However,
        InfluxDB is schemaless and so any fields can be used.

        :param kwargs: the params passed to the LoggerInstance.
        :type kwargs: Dict[str, Any]
        """
        invalid_keys = [k for k in kwargs if k not in FIELDS]
        if len(invalid_keys) != 0:
            logger.warning("EventLogger: %s not valid for %s",
                           ",".join(invalid_keys),
                           self.__class__.__name__)

    def add_writers(self, *writers):
        """Add the writers to the logger.

        Any existing writers with the same name are replaced.

        :param writers: The writers (derived from WriterBase)
        :type writers: List[WriterBase]
        """
        _existing_replaced = []
        for w in writers:
            if w in self._writers:
                _existing_replaced.append(w)
            else:
                self._writers.append(w)
        if _existing_replaced:
            logger.warning("Adding existing writers: {}"
                           .format(",".join(_existing_replaced)))

    def remove_writer(self, writer):
        """Remove a writer.

        Logs a warning if the writer doesn't exist.

        :param writer: the writer.
        :type writer: WriterBase
        """
        to_keep = []
        for i, w in enumerate(self._writers):
            if w != writer:
                to_keep.append(i)
        if len(to_keep) == len(self._writers):
            logger.warning("Writer: %s doesn't exist, ignore removing",
                           writer)
            return
        self._writers = to_keep


class LoggerInstance:
    """The logging instance to provide logging.

    Connects to the EventLogger, and can have pre-filled fields to make it
    easier to log things.  Multiple different LoggerInstances can exist that
    all use the same EventLogger to enable different parts of the code to own
    their own (prefilled) logger instances.
    """

    def __init__(self, event_logger, **kwargs):
        """Create a logger instance.

        This allows prefilling of valid fields in a logger.

        Note tht it produces a warning if any other that the _valid_fields keys
        are used. The attributes are stored on the object (self).

        :param event_logger: The event logger this is attached to.
        :type event_logger: EventLogger
        """
        self.event_logger = event_logger
        self.prefilled = {}
        self.prefilled.update(kwargs)

    def _add_in_prefilled(self, kwargs):
        """Add in the prefilled values if they don't exist to a passed dict.

        :param kwargs: the key=value pairs to event log.
        :type kwargs: Dict[str, Any]
        :returns: the original kwargs with any additionally prefilled values.
        :rtype: Dict[str, Any]
        """
        # shallow copy, because update mutates rather than returning a new
        # dict.
        _prefilled = self.prefilled.copy()
        _prefilled.update(kwargs)
        return _prefilled

    def prefill_with(self, **kwargs):
        """Allow further prefilling with fields.

        :param kwargs: key=value pairs to prefill for a log
        :type kwargs: Dict[str, Any]
        :returns: a new LoggerInstance with the existing and new prefilled
            values (allows overwriting existing values.)
        :rtype: LoggerInstance
        """
        return LoggerInstance(self.event_logger,
                              **(self._add_in_prefilled(kwargs)))

    def log(self, event, **kwargs):
        """Call the parent log function.

        Log an event adding in prefilled values if they aren't present in the
        passed keyword arguments.

        :param event: the event to log
        :type event: zaza.events.types.Events
        :param kwargs: The key=value arguments to log
        :type kwargs: Dict[str, Any]
        """
        self.event_logger._log(event, **(self._add_in_prefilled(kwargs)))

    def span(self, comment=None, **kwargs):
        """Return a span event decorator.

        This provides COMMENT events with span=Span.BEFORE and span=Span.AFTER
        fields for the span. An EXCEPTION events is written with a
        span=Span.AFTER if an exception is raised. If called as a normal
        function, then it returns the span() object.  The span() object can
        also be used as a contextmanager and so it can be used as a span.  See
        :class:`span` for more details.

        By default a COMMENT event is used, but this can be overridden by
        providing the "event" as a kwarg.

        :param comment: the optional comment that gets applied to each event.
        :type comment: Optional[str]
        :param kwargs: optional fields/tags to send to the logger.
        :type kwargs: Dict[str, ANY]
        :returns: a span() object.
        :rtype: span
        """
        return span(self, comment=comment, **kwargs)


class span:
    """Provide a new span of logs.

    This is to allow uuid fields to be auto-generated and then indicate a span
    of logs around an activity.

    Can be used as:

        span = events.span()
        events.log(Events.COMMENT, span=span, comment="...")

    or:

        with events.span("comment") as span:
            ...
            events.log(Events.COMMENT, span=span, comment="...")
            ...
    """

    def __init__(self, event_logger, comment=None, event=None, **kwargs):
        """Initialise a span logger.

        :param event_logger: the logger that this will use.
        :type event_logger: Union[EventLogger, LoggerInstance]
        :param comment: the comment that goes with this span.
        :type comment: Optional[str]
        :param event: the Events event to go with the span
        :param kwargs: Additional fields/tags to go with the span log.
        :type kwargs: Dict[str, ANY]
        """
        self.event_logger_ref = weakref.ref(event_logger)
        self.uuid = str(uuid.uuid4())
        self.comment = comment
        self.event = event or Events.COMMENT
        self.kwargs = kwargs

    @property
    def _kwargs(self):
        """Return the kwargs for the log.

        Merges the UUID with the kwargs and comment.

        :returns: the kwargs to pass to the log.
        :rtype: Dict[str, ANY]
        """
        kwargs = self.kwargs.copy()
        kwargs['uuid'] = self.uuid
        if self.comment:
            kwargs['comment'] = self.comment
        return kwargs

    def __enter__(self):
        """Log start event on entry to context."""
        kwargs = self._kwargs
        if 'span' not in kwargs:
            kwargs['span'] = Span.BEFORE.value
        self.event_logger_ref().log(self.event, **kwargs)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log end event on exit from context.

        If there is an exception, log an exception event instead.
        Return False so as to propagate the exception.
        """
        kwargs = self._kwargs
        if 'span' not in kwargs:
            kwargs['span'] = Span.AFTER.value
        if exc_type is None:
            self.event_logger_ref().log(self.event, **kwargs)
        else:
            self.comment = "Exception: {}: {}".format(
                str(exc_type), str(exc_val))
            self.event_logger_ref().log(Events.EXCEPTION, **kwargs)
        return False


###############################################################################

# Writers; turns events into formatted types for writing to log files.

###############################################################################

def make_writer(log_format, handle):
    """Make a writer with the appropirate format.

    :param log_format: A log format in the form of LogFormats
    :type log_format: str
    :param handle: the handle associated with the writer.
    :type handle: IO[str]
    :returns: a Writer
    :rtype: WriterBase
    """
    types = {
        LogFormats.CSV: WriterCSV,
        LogFormats.LOG: WriterDefault,
        LogFormats.InfluxDB: WriterLineProtocol,
    }

    assert log_format in (
        LogFormats.CSV, LogFormats.LOG, LogFormats.InfluxDB), \
        "Log format {} isn't one of {}".format(
            log_format,
            ", ".join((LogFormats.CSV, LogFormats.LOG, LogFormats.InfluxDB)))

    return types[log_format](handle)


class WriterFile:
    """Handle the lifetime of a log file and the handle.

    This wires together a handle and the log file associated with
    it.  The EventLogger doesn't know about filenames, only about writers.
    This is intentional so as to loosely couple log files, how they are written
    and what writes to them.

    This class also automagically handles the log file and cleans up at the
    end (if asked to).
    """

    def __init__(self, writer_name, filename=None, delete=False):
        """Manage a writer's handle as a physical log file.

        If filename is None, then we create a random filename from the writer's
        name and some random chars.

        If filename is not None, then we open the file using "w+b" and stash
        the handle, and add an atexit handler to ensure the file is flushed and
        closed properly when the script exists, unless the file has already
        been closed.  If delete=False (the default) then the file is not
        deleted, only closed; normally, we want the atexit handler to delete
        the file, unless some other tool is going to use the file in someway.

        The log is created in the temporary dir/writers-xxxxx/name-xxxx

        :param writer: The writer for which to handle the logfile
        :type writer: WriterBase
        :param filename: optional filename; one is created if needed.
        :type filename: Optional[str]
        :param delete: Whether to delete the file in the atexit handler.
        :type delete: bool
        """
        if filename is None:
            dir_ = _get_writers_log_dir()
            name = "{}_{}.log".format(writer_name, str(uuid.uuid4())[-8:])
            filename = os.path.join(dir_, name)
        self.writer_ = writer_name
        self.filename = filename
        self.handle = open(filename, "w+t")
        self.delete = delete

        def clean_up():
            if self.handle is not None:
                self.handle.flush()
                self.handle.close()
                self.handle = None
            if self.delete:
                try:
                    os.remove(self.filename)
                except FileNotFoundError:
                    pass

        atexit.register(clean_up)

    def close(self):
        """Close the associated handle."""
        if self.handle is not None:
            self.handle.flush()
            self.handle.close()
            self.handle = None


# Need a global to hold the temporary directory until the program ends.
_log_dir = None


def _get_writers_log_dir():
    """Return the directory for writing log files to.

    :returns: A log dir for writing logs to, if one is not set then a temporary
        one is created; it gets deleted when the script ends!
    :rtype: Path
    """
    global _log_dir
    if _log_dir is not None:
        return _log_dir
    _log_dir = tempfile.TemporaryDirectory()
    return _log_dir.name


class WriterBase:
    """A simple writer class for logging."""

    def __init__(self, name, handle):
        """Initialise writer object with a name and handle.

        :param name: the name of the writer.
        :type name: IO[str]
        :param handle: the handle to write to.
        :type handle: IO[str]
        :param format_str: the format string to write to.
        :type format_str: str
        """
        self.name = name
        self.handle = handle

    def write(self, newline=True, **kwargs):
        """Write to the handle.

        Write a log to the handle by converting the kwargs into a string using
        the :method:`format`.

        By default, if the timestamp is passed as a kwarg, and it is a
        :class:`datetime.datetime`, then it is converted to a ISO8601 format.

        :param kwargs: The key=value pairs that should be formatted using the
            :method:`format`.
        :type kwargs: Dict[str, Any]
        :param newline: if a newline should be issued if not present.
        :type newline: bool
        """
        # convert the timestamp (if it's datetime.datetime) to a string in the
        # form of ISO8601 datetime - 2020-03-20T14:32:16.458361+13:00
        try:
            ts = kwargs['timestamp']
            if isinstance(ts, datetime.datetime):
                kwargs['timestamp'] = ts.isoformat()
        except KeyError:
            pass
        msg = self.format(**kwargs)
        self._write_to_handle(msg, newline=True)

    def format(self, **kwargs):
        """Format the log."""
        raise NotImplementedError()

    def _write_to_handle(self, msg, newline=True):
        """Write to the log file handle and flush it.

        If the message has no newline, it is automatically added, unless
        :paramref:`newline` is False.

        :param msg: the string to write.
        :type msg: str
        :param newline: whether to add a newline if it is missing.
        :type newline: bool
        """
        self.handle.write(msg)
        if not msg.endswith("\n") and newline:
            self.handle.write("\n")
        self.handle.flush()


class WriterCSV(WriterBase):
    """Write CSV format log lines.

    '"{timestamp}","{collection}","{unit}","{item}","{event}","{uuid}",
     "{comment}","{tags}"'

    """

    def __init__(self, handle):
        """Create a WriterCSV."""
        super().__init__("CSV", handle)

    @staticmethod
    def _format_csv(value):
        """Format a csv 'value' to a quoted string, if it is a string.

        If the string has quotes, then they are doubled.  e.g.

          Hello "Jim". -> "Hello ""Jim""."

        :param value: The value to format.
        :type value: _T
        :returns: if passed a str, the quoted str
        :rtype: _T
        """
        assert isinstance(value, str)
        if not(value.startswith('"') and value.endswith('"')):
            if '"' in value:
                value.replace('"', '""')
            value = '"{}"'.format(value)
        return value

    def format(self, **kwargs):
        """Format a CSV log line.

        Note that the fields 'timestamp', 'collection', 'unit', 'item',
        'event', 'uuid', and 'comment' are treated as columes, with any
        remaining key, value pairs being arranged as a single 'tags' column and
        formatted as key value pairs.

        :param kwargs: the key=value pairs to format
        :type kwargs: Dict[str, Any]
        :returns: a formatted string
        :rtype: str
        """
        msg = []
        for field in ('timestamp', 'collection', 'unit', 'item', 'event',
                      'uuid', 'comment'):
            try:
                value = kwargs[field]
                msg.append(self._format_csv(value))
                del kwargs[field]
            except KeyError:
                pass
        try:
            tags = kwargs['tags']
            del kwargs['tags']
        except KeyError:
            tags = {}
        assert isinstance(tags, dict)
        tags.update(kwargs)
        msg.extend(",".join(self._format_csv("{}={}".format(k, v))
                            for k, v in tags.items()))
        return ",".join(msg)


class WriterDefault(WriterBase):
    """Write LOG format log lines.

    '{timestamp} {collection} {unit} {item} {event} {uuid} {comment} {tags}'
    """

    def __init__(self, handle):
        """Create a Default Writer."""
        super().__init__("DEFAULT", handle)

    def format(self, **kwargs):
        """Format a Default Log line.

        Note that the fields 'timestamp', 'collection', 'unit', 'item',
        'event', 'uuid', and 'comment' are treated as columes, with any
        remaining key, value pairs being arranged as a single 'tags' column and
        formatted as key value pairs.

        :param kwargs: the key=value pairs to format
        :type kwargs: Dict[str, Any]
        :returns: a formatted string
        :rtype: str
        """
        msg = []
        for field in ('timestamp', 'collection', 'unit', 'item', 'event',
                      'uuid', 'comment'):
            try:
                value = kwargs[field]
                if field == "comment":
                    value = '"{}"'.format(value)
                msg.append(value)
                del kwargs[field]
            except KeyError:
                pass
        try:
            tags = kwargs['tags']
            del kwargs['tags']
        except KeyError:
            tags = {}
        assert isinstance(tags, dict)
        tags.update(kwargs)
        if tags:
            msg.append("tags={}".format(format_dict(tags)))
        return " ".join(msg)


class WriterLineProtocol(WriterBase):
    """Write InfluxDB line protocol format log lines.

    Note: the tags and fields' keys and values must not contain spaces.
    If values have a space then the values need quoting.  This function does
    not do that.

    '{collection},{tags} {fields} {timestamp}'

    Note that 'collection' here, is a 'measurement' in InfluxDB terms.
    """

    def __init__(self, handle):
        """Create a InfluxDB Writer."""
        super().__init__("InfluxDB", handle)

    def write(self, newline=True, **kwargs):
        """Write a InfluxDB log line.

        The measure is the test_run_id.
        The fields are unit, item, event, comment and uuid
        The tags are in tags and any left over kwargs.

        :param newline: If true, default, ensure the log has a newline.
        :type newline: bool
        :param kwargs: the key=value pairs to format into line protocol.
        :type kwargs: Dict[str, Any]
        """
        fields = kwargs.pop('fields', {})
        for field in ('unit', 'item', 'event', 'comment', 'uuid'):
            try:
                fields[field] = kwargs[field]
                kwargs.pop(field)
            except KeyError:
                pass
        kwargs['fields'] = fields
        # convert Python timestamp to microseconds for InfluxDB if it exists
        try:
            timestamp = kwargs['timestamp']
            if isinstance(timestamp, datetime.datetime):
                kwargs['timestamp'] = (
                    "{}us" .format(int(timestamp.timestamp() * 1e6)))
        except KeyError:
            pass
        super().write(newline=newline, **kwargs)

    def format(self, **kwargs):
        """Format the Line Protocol string.

        '{collection},{tags} {fields} {timestamp}'

        :param kwargs: the keyword arguments arranged as collection, tags,
            fields and timestamp
        :type kwargs: Dict[str, Any]
        :returns: formatting log line.
        :rtype: str
        """
        collection = kwargs.pop('collection', 'collection?')
        tags = kwargs.pop('tags', {})
        fields = kwargs.pop('fields', {})
        timestamp = kwargs.pop('timestamp', None)
        tags.update(kwargs)
        return (
            "{collection}{tags}{fields}{timestamp}"
            .format(
                collection=collection,
                tags=("" if not tags else ",{}"
                      .format(format_dict(tags, tag=True))),
                fields=("" if not fields else " {}"
                        .format(format_dict(fields))),
                timestamp=(" {}".format(timestamp) if timestamp else "")))


def format_value(value, tag=False):
    """Quote a value if it isn't quoted yet.

    :param value: the string to quote
    :type value: Any
    :param tag: if this is a tag, then don't quote it, but make sure it has no
        spaces.
    :type tag: bool
    :returns: quoted value
    :rtype: str
    """
    if tag:
        if isinstance(value, str):
            return value.replace(' ', '-')
        return value
    if isinstance(value, str):
        if value.startswith('"') and value.endswith('"'):
            return value
    return '"{}"'.format(value)


def format_dict(d, tag=False):
    """Fromat a dictionary with quoted values.

    :param d: the dictionary of values to quote.
    :type d: Dict[str, str]
    :param tag: if the values are tags, they need have no spaces and are not
        quoted.
    :type tag: bool
    :returns: single string of comma-seperated k="v" quoted items.
    :rtype: str
    """
    assert isinstance(d, dict)
    return ",".join(
        '{}={}'.format(k, format_value(v, tag=tag))
        for k, v in d.items())


class HandleToLogging:
    """HandleToLogging logs events to Python logging."""

    def __init__(self, name=None, level=logging.DEBUG, python_logger=None):
        """Initialise a HandleToLogging object.

        This acts as a proxy handle to enable Writers to write to Python's
        standard loggers.

        :param name: the name of this handle
        :type name: Optional[str]
        :param level: the level to log at (python logging)
        :type level: int
        :param python_logger: The python logger to use for logging.
        :type python_logger: Optional[logging.RootLogger]
        """
        self.name = name
        self.level = level
        self.logger = python_logger

    def write(self, msg):
        """Write a message to the python logger.

        Note that it ignores newlines.

        :param msg: the message to write to the logger.
        :type msg: str
        """
        msg = msg.rstrip()
        if msg:
            _logger = self.logger or logger
            _logger.log(self.level, "(events): '%s'", msg)

    def flush(self):
        """Flush the handle.

        This is a no-op for the HandleToLogging object.
        """
        pass
