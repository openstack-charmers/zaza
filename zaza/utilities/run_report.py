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

run_data = None


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


def _init_run_data(reset=False):
    global run_data
    if not run_data or reset:
        run_data = {
            ReportKeys.EVENTS.value: {},
            ReportKeys.METADATA.value: {}}


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
    global run_data
    _init_run_data()
    timestamp = timestamp or time.time()
    events = run_data[ReportKeys.EVENTS.value]
    if event_name in events:
        events[event_name][event_state.value] = timestamp
    else:
        events[event_name] = {event_state.value: timestamp}


def register_metadata(cloud_name=None, model_name=None, target_bundle=None):
    """Add metadata about this run.

    :param cloud_name: Name of cloud eg canonistack1
    :type cloud_name: str
    :param model_name: Name of model
    :type model_name: str
    :param target_bundle: Name of bundle
    :type target_bundle: str
    """
    global run_data
    _init_run_data()
    if cloud_name:
        run_data[ReportKeys.METADATA.value]['cloud_name'] = cloud_name
    if model_name:
        run_data[ReportKeys.METADATA.value]['model_name'] = model_name
    if target_bundle:
        run_data[ReportKeys.METADATA.value]['target_bundle'] = target_bundle


def get_events_start_stop_time(events):
    """Return the time of the first event and the last.

    :param events: Dict of events.
    :type events: dict
    :returns: Tuple of start time and endtime in seconds since epoch.
    :rtype: (float, float)
    """
    start_time = -1
    finish_time = -1
    for event_name, event_info in events.items():
        for event_state, timestamp in event_info.items():
            if start_time == -1 or start_time > timestamp:
                start_time = timestamp
            if finish_time == -1 or finish_time < timestamp:
                finish_time = timestamp
    return start_time, finish_time


def get_event_report():
    """Produce report based on current run.

    :returns: Dictionary of run data with summary info.
    :rtype: dict
    """
    global run_data
    _init_run_data()
    report = copy.deepcopy(run_data)
    start_time, finish_time = get_events_start_stop_time(get_events())
    full_run_time = finish_time - start_time
    for name, info in report[ReportKeys.EVENTS.value].items():
        try:
            event_time = (info[EventStates.FINISH.value] -
                          info[EventStates.START.value])
            info[ReportKeys.ELAPSED_TIME.value] = event_time
            info[ReportKeys.PCT_OF_RUNTIME.value] = math.ceil(
                (event_time / full_run_time) * 100)
        except KeyError:
            pass
    return report


def write_event_report(output_file=None):
    """Log the event report and optionally write to a file.

    :param outputfile: File name to write summary to.
    :type events: str
    """
    report = get_event_report()
    report_txt = yaml.dump(report, default_flow_style=False)
    if output_file:
        with open(output_file, 'w') as out:
            out.write(report_txt)
    logging.info(report_txt)


def get_run_data():
    """Return the raw dictionary of events.

    :returns: Dictionary of run data without summary info.
    :rtype: dict
    """
    global run_data
    _init_run_data()
    return run_data


def reset_run_data():
    """Reset the run data, removing all entries."""
    _init_run_data(reset=True)


def get_events():
    """Return the dictionary of events recorded for this run.

    :returns: Dictionary of events.
    :rtype: dict
    """
    return get_run_data()[ReportKeys.EVENTS.value]


def get_metadata():
    """Return the dictionary of metadata recorded for this run.

    :returns: Dictionary of metadata.
    :rtype: dict
    """
    return get_run_data()[ReportKeys.METADATA.value]
