# Copyright 2019 Canonical Ltd.
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

"""Module for logging events for a summary report.

This module contains a number of functions for logging events so that they
can be summarised, with timings, at the end of the run.
"""

import enum
import copy
import logging
import time
import math
import yaml

_run_data = None


def get_run_data():
    """Return the dict of events data.

    :returns: Dictionary of events data.
    :rtype: dict
    """
    global _run_data
    if _run_data is None:
        _run_data = init_run_data()
    return _run_data


def clear_run_data():
    """Clear the existing event data."""
    global _run_data
    _run_data = None


def init_run_data():
    """Initialise the report data structure.

    :returns: Dictionary of events data.
    :rtype: dict
    """
    return {
        ReportKeys.EVENTS: {},
        ReportKeys.METADATA: {}}


def get_copy_of_events():
    """Return a copy of the dictionary of events for this run.

    :returns: Dictionary of events.
    :rtype: dict
    """
    return copy.deepcopy(get_run_data())[ReportKeys.EVENTS]


def get_copy_of_metadata():
    """Return a copy of the metadata recorded for this run.

    :returns: Dictionary of metadata.
    :rtype: dict
    """
    return copy.deepcopy(get_run_data())[ReportKeys.METADATA]


class EnumToStrDumper(yaml.SafeDumper):
    """Convert Enums to str when dumping."""

    def represent_data(self, data):
        """If the value is an Enum dump the value."""
        if isinstance(data, enum.Enum):
            return self.represent_data(data.value)
        return super().represent_data(data)


class ReportKeys(enum.Enum):
    """Keys in the Run report."""

    METADATA = 'Metadata'
    EVENTS = 'Events'
    PCT_OF_RUNTIME = 'PCT Of Run Time'
    ELAPSED_TIME = 'Elapsed Time'


class EventStates(enum.Enum):
    """States that can be registered against an event."""

    START = 'Start'
    FINISH = 'Finish'


def register_event(event_name, event_state, timestamp=None):
    """Register that event_name is at event_state.

    :param event_name: Name of event
    :type event_name: str
    :param event_state: Name of event state (should be one of EventStates).
    :type event_state: enum.Enum
    :param timestamp: Seconds since epoch when event_state of event_name was
                      reached.
    :type timestamp: float
    """
    run_data = get_run_data()
    timestamp = timestamp or time.time()
    events = run_data[ReportKeys.EVENTS]
    if event_name in events:
        events[event_name][event_state] = timestamp
    else:
        events[event_name] = {event_state: timestamp}


def register_metadata(cloud_name=None, model_name=None, target_bundle=None):
    """Add metadata about this run.

    :param cloud_name: Name of cloud eg canonistack1
    :type cloud_name: str
    :param model_name: Name of model
    :type model_name: str
    :param target_bundle: Name of bundle
    :type target_bundle: str
    """
    run_data = get_run_data()
    if cloud_name:
        run_data[ReportKeys.METADATA]['cloud_name'] = cloud_name
    if model_name:
        run_data[ReportKeys.METADATA]['model_name'] = model_name
    if target_bundle:
        run_data[ReportKeys.METADATA]['target_bundle'] = target_bundle


def get_events_start_stop_time(events):
    """Return the time of the first event and the last.

    :param events: Dict of events.
    :type events: dict
    :returns: Tuple of start time and endtime in seconds since epoch.
    :rtype: (float, float)
    """
    timestamps = events.values()
    start_times = [x.get(EventStates.START) for x in timestamps]
    finish_times = [x.get(EventStates.FINISH) for x in timestamps]
    if start_times and finish_times:
        return min(start_times), max(finish_times)
    else:
        return None, None


def get_event_report():
    """Produce report based on current run.

    :returns: Dictionary of run data with summary info.
    :rtype: Dict[str, Dict[str, float]]
    """
    run_data = get_run_data()
    report = copy.deepcopy(run_data)
    start_time, finish_time = get_events_start_stop_time(get_copy_of_events())
    if start_time and finish_time:
        full_run_time = finish_time - start_time
        for name, info in report[ReportKeys.EVENTS].items():
            try:
                event_time = (info[EventStates.FINISH] -
                              info[EventStates.START])
                info[ReportKeys.ELAPSED_TIME] = event_time
                info[ReportKeys.PCT_OF_RUNTIME] = math.ceil(
                    (event_time / full_run_time) * 100)
            except KeyError:
                pass
    return report


def get_yaml_event_report():
    """Get the report and convert it to yaml.

    :returns: The ereport in yaml format
    :rtype: str
    """
    return yaml.dump(
        get_event_report(),
        Dumper=EnumToStrDumper,
        default_flow_style=False)


def output_event_report(output_file=None):
    """Log the event report and optionally write to a file.

    :param outputfile: File name to write summary to.
    :type events: str
    """
    report_yaml = get_yaml_event_report()
    if output_file:
        write_event_report(report_yaml, output_file)
    log_event_report(report_yaml)


def write_event_report(report, output_file):
    """Write the given event report to a file.

    :param report: Report to write out.
    :type report: str
    :param output_file: File to write report to.
    :type output_file: str
    """
    with open(output_file, 'w') as out:
        out.write(report)


def log_event_report(report):
    """Log the given event report.

    :param report: Report to log
    :type report: str
    """
    logging.info(report)
