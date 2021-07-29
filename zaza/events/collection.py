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

"""Collection of Events for a test run.

Zaza is capable of running multiple bundles / test_runs in a single instance.
The Collection classes are to deal with:

 * Events from the test functions that indicates stages of the test.
 * Events from the Juju units (specifically scanning the logs) for hook events
     and errors.
 * Events from other compatible logging entities that need to be combined into
   a coherent log for the collection.

There are several common fields used in the logging framework:

 * collection - the name of the test (but could be anything)
 * event - the thing that occurred.

 Any other fields can be used as needed.  Additionally, tags can be used which
 result in a field of the form name=thing,name1=thing2.

 At the highest level of abstraction, the objects in the collection need to be
 able to 'give-up' their log files, so that they can be combined and stored as
 a collection along with a manifest.
"""

import collections
from datetime import datetime
import logging
import tempfile

from zaza.utilities import ConfigurableMixin

from .formats import LogFormats


# Hold collections; probably there will only be one.
_collections = {}


def get_collection(name="DEFAULT"):
    """Return a collection by name.

    Collections are available globally, and typically only one will be needed
    per test.  However, a collection per bundle may be a good approach too.

    This returns a named collection (a.k.a logging) for use in a module.

    :returns: the colection named, or creates a new one of that name.
    :rtype: Collection
    """
    global _collections
    try:
        return _collections[name]
    except KeyError:
        pass
    _collections[name] = Collection(name=name)
    return _collections[name]


class Collection(ConfigurableMixin):
    """Collection of Log Events.

       The collection manages a set of event loggers and associated log files.
       The final set of files is provided in a Manifest object.

       And event logger object needs the following methods:

           configure(**kwargs) -> None
           finalise(self) -> None
           get_manifest(self) -> ManifestBase
           clean_up(self) -> None

       These are used to control the logging on the units, in the following
       manner.

       configure(logs_dir=...) -- indicate where to put the logs.
       finalise()              -- ensure that the logs are complete and
                                  pullable.
       get_manifest()          -- fetch a manifest of all the log files.
       clean_up()              -- do any clean-up as we've finished.

       If the logs_dir is not configured then a temporary log directory will be
       created with tempfile.mkdtemp() -- this will stick around after the
       program is completed.
    """

    def __init__(self, **kwargs):
        """Initialise a collection of related log files."""
        self.name = None
        self.collection = None
        self.description = None
        self.logs_dir = None
        self.log_format = None
        self._event_managers = []
        self.configure(**kwargs)
        if self.log_format is None:
            self.log_format = LogFormats.InfluxDB

    def _ensure_logs_dir(self):
        """Ensure that the logs_dir is set.

        Also ensure the directory exists.
        """
        if self.logs_dir is not None:
            return
        self.logs_dir = tempfile.mkdtemp()

    def add_logging_manager(self, manager):
        """Add a logging manager to the collection.

        The manager implements the PluginManagerBase class which allows the
        collection to configure the logs dir, collection name, log format, and
        other items.

        :param manager: the plugin manager that manages the thing recording
            events.
        :type manager: PluginManagerBase
        """
        if manager in self._event_managers:
            logging.debug(
                "Collection: adding manager %s more than once, ignoring.",
                manager)
            return
        self._event_managers.append(manager)
        manager.configure(collection_object=self)
        self._ensure_logs_dir()
        manager.configure_plugin()

    def finalise(self):
        """Finalise the logging collection.

        This finalises ALL of the event managers that are connected to this
        collection.  Depending on the plugin this may terminate / gather logs
        from multiple sources; i.e. it may take a while.
        """
        for manager in self._event_managers:
            manager.finalise()

    def log_files(self):
        """This function returns an iterator of (name, type, filename).

        This is from all of the managers.

        :returns: A list/iterator of tuples of (name, type, filename)
        :rtype: Iterator[Tuple[str, str, str]]
        """
        for manager in self._event_managers:
            yield from manager.log_files()

    def events(self, sort=True, precision="us", strip_precision=True):
        """Provide a context manager that returns an iterator of events.

        Designed to be used as:

            with collection.events() as events:
                for event in events:
                    # do something with the (filename, event)

        If sort is True, then the events are sorted, otherwise they are just
        returned in the order of files from :method:`log_files`.

        Note that all the log files should be the same format.  If, not, the
        collection is broken and an error will probably occur.

        This uses the log_file() iterator on this class to produce a complete
        list of log files; they all must provide the same log format.

        The precision is used to normalise the precision across all of the
        events to the same precision and then strip the precision indicator
        ready for upload to InfluxDB.

        :param sort: if True, then a sorted stream is returned.
        :type sort: bool
        :param precision: the precision to use; (default ms)
        :type precision: str
        :param strip_precision: If True, do no re-add the precision at the end.
        :type strip_precision: bool
        :returns: context manager
        :rtype: Iterator[(str, str)]
        :raises AssertionError: if the logs are all the same type.
        """
        specs = list(self.log_files())
        if not specs:
            return
        type_ = specs[0][1]
        if not all(t[1] == type_ for t in specs[1:]):
            raise AssertionError("Not all specs match {}".format(type_))
        files = [s[2] for s in specs]
        return Streamer(files, self.log_format, sort=sort,
                        precision=precision, strip_precision=strip_precision)

    def clean_up(self):
        """Tell all the managed plugins to clean-up."""
        for manager in self._event_managers:
            manager.clean_up()


class Streamer:
    """An context manager for with that streams from multiple log files."""

    def __init__(self, files, log_format, sort=True, precision="us",
                 strip_precision=True):
        """Initialise the object.

        precision must be of of ("s", "ms", "us", "ns")

        :param files: a list of files
        :type files: List[str]
        :param log_format: one of CSV, LOG, InfluxDB
        :type log_format: str
        :param sort: whether to sort the logs by date order.
        :type sort: bool
        :param precision: the precision to use; (default ms)
        :type precision: str
        :param strip_precision: If True, do no re-add the precision at the end.
        :type strip_precision: bool
        :returns: Iterator[(str, str)]
        :raises: AssertionError if precision is not valid.
        """
        self.files = files
        self.log_format = log_format
        self.sort = sort
        self.handles = None
        self.precision = precision
        self.strip_precision = strip_precision
        assert precision in ("s", "ms", "us", "ns")

    def __enter__(self):
        """Set it up."""
        # open the files to handles
        handles = collections.OrderedDict()
        for f in self.files:
            try:
                handles[f] = open(f)
            except (FileNotFoundError, OSError) as e:
                logging.warning("Couldn't open log file: %s: %s", f, str(e))
        self.handles = handles
        return self._iterator()

    def __exit__(self, _, __, ___):
        """Exit, just ensure that all the handles are closed."""
        for f, h in self.handles.items():
            try:
                h.close()
            except Exception as e:
                logging.warning("Exception on closing %s: %s", f, str(e))
        return False

    def _iterator(self):
        # Whilst we still have open files.
        currents = []
        # Get the first set of currents [(timestamp, filename, event)]
        for f, h in self.handles.copy().items():
            try:
                line = h.readline()
                if line:
                    event = line.rstrip()
                    currents.append(
                        (_parse_date(self.log_format, event), f, event))
                else:
                    self.handles[f].close()
                    del self.handles[f]
            except OSError as e:
                logging.warning("Couldn't read log file: %s: %s", f, str(e))
                self.handles[f].close()
                del self.handles[f]
        if self.sort:
            currents.sort(key=lambda i: i[0])

        # Now whilst we still have handles, find the youngest, and yield it and
        # get another.
        while currents:
            # take the first one, youngest, and yield it.
            _, filename, event = currents.pop(0)
            if self.log_format == LogFormats.InfluxDB:
                event = _re_precision_timestamp_influxdb(
                    event,
                    self.precision,
                    strip_precision=self.strip_precision)
            yield (filename, event)
            # get a new one from the handle for the filename.
            try:
                try:
                    line = self.handles[filename].readline()
                except KeyError:
                    # i.e. no more from this filename
                    continue
                if line:
                    event = line.rstrip()
                    ts = _parse_date(self.log_format, event)
                    # now insert the ts stamp at the correct place.
                    if self.sort:
                        for i, (ts_, _, _) in enumerate(currents):
                            if ts < ts_:
                                currents.insert(i, (ts, filename, event))
                                break
                        else:
                            currents.append((ts, filename, event))
                    else:
                        currents.insert(0, (ts, filename, event))
                else:
                    self.handles[filename].close()
                    del self.handles[filename]
            except OSError as e:
                logging.warning("Couldn't read log file: %s: %s", filename,
                                str(e))
                self.handles[filename].close()
                del self.handles[filename]


_precision_multipliers = {
    "s": 1.0,
    "ms": 1e3,
    "us": 1e6,
    "ns": 1e9,
}


def _re_precision_timestamp_influxdb(event,
                                     precision,
                                     no_suffix_precision="ns",
                                     strip_precision=True):
    """For an influxdb event, this re-writes the precision to the new version.

    If :param:`strip_precision` is True, the default, then the precision
    indicator is stripped off, and the timestamp put back after being
    converted.  If no precision is on the timestamp then it is assumed to be
    the :param:`no_suffix_precision` (default of ns = nanoseconds).

    Note: this function LOSES precision if going from smaller to larger.
    That's because influxdb timestamps are ints with a precision.

    :param precision: the precision to use; (default ms)
    :type precision: str
    :param no_suffix_precision: the precision when there is no suffix.
    :type no_suffix_precision: str
    :param strip_precision: If True, do no re-add the precision at the end.
    :type strip_precision: bool
    :returns: the timestamp from the event.
    :rtype: datetime.datetime
    """
    assert precision in ("s", "ms", "us", "ns")
    precision_m = _precision_multipliers[precision]

    event_list = event.split(" ")
    ts = event_list[-1]
    suffix = ts[-2:]
    try:
        event_m = _precision_multipliers[suffix]
        ts = ts[:-2]
    except KeyError:
        event_m = _precision_multipliers[no_suffix_precision]
        suffix = no_suffix_precision

    # now adjust the precision.
    if suffix != precision:
        ts = str(int(float(ts) * precision_m / event_m))
    elif not strip_precision:
        # if the suffix matches the desired precision and we don't strip the
        # precision then just return the event unchanged.
        return event
    if not strip_precision:
        ts = "{}{}".format(ts, precision)

    # reassemble the event
    event_list = event_list[:-1]
    event_list.append(ts)
    return " ".join(event_list)


def _parse_date(log_format, event):
    """Parse a date to a timestamp for comparisons.

    The function can work with Log formats know to collections:
    CSV, LOG, INFLUXDB

    :param log_format: the format of the event.
    :type log_format: str
    :param event: the event to parse a date from
    :type event: str
    :returns: the timestamp from the event.
    :rtype: datetime.datetime
    """
    assert log_format in (LogFormats.CSV, LogFormats.LOG, LogFormats.InfluxDB)
    if log_format == LogFormats.InfluxDB:
        ts = event.split(" ")[-1]
        if ts.endswith("ms"):
            return datetime.fromtimestamp(float(ts[:-2]) / 1e3)
        elif ts.endswith("us"):
            return datetime.fromtimestamp(float(ts[:-2]) / 1e6)
        elif ts.endswith("ns"):
            return datetime.fromtimestamp(float(ts[:-2]) / 1e9)
        else:
            if ts.endswith("s"):
                ts = ts[:-1]
            return datetime.fromtimestamp(float(ts))
    elif log_format == LogFormats.CSV:
        ts = event.split(",")[0]
        if ts.startswith('"'):
            ts = ts[1:]
        if ts.endswith('"'):
            ts = ts[:-1]
        return datetime.fromisoformat(ts)
    else:
        ts = event.split(" ")[0]
        return datetime.fromisoformat(ts)
