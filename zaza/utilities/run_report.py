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

import copy
import logging
import time
import math
import yaml


start = 'Start'
finish = 'Finish'
metadata = 'Metadata'
events = 'Events'
pct_of_runtime = 'PCT Of Run Time'
elapsed_time = 'Elapsed Time'

run_data = None

event_states = [start, finish]


def _init_run_data(reset=False):
    global run_data
    if not run_data or reset:
        run_data = {
            events: {},
            metadata: {}}


def register_event(event_name, event_state, timestamp=None):
    """Register that event_name is at event_state.

    :param event_name: Name of event
    :type event_name: str
    :param event_state: Name of event state (should be one of event_states).
    :type event_state: str
    :param timestamp: Seconds since epoch when event_state of event_name was
                      reached.
    :type timestamp: float
    """
    global run_data
    _init_run_data()
    timestamp = timestamp or time.time()
    if event_name in run_data[events]:
        run_data[events][event_name][event_state] = timestamp
    else:
        run_data[events][event_name] = {event_state: timestamp}


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
        run_data[metadata]['cloud_name'] = cloud_name
    if model_name:
        run_data[metadata]['model_name'] = model_name
    if target_bundle:
        run_data[metadata]['target_bundle'] = target_bundle


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
    start_time, finish_time = get_events_start_stop_time(report[events])
    full_run_time = finish_time - start_time
    for event_name, event_info in report[events].items():
        try:
            event_time = event_info[finish] - event_info[start]
            event_info[elapsed_time] = event_time
            event_info[pct_of_runtime] = math.ceil(
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
    global run_data
    _init_run_data(reset=True)
