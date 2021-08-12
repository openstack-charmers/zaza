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

"""Integrate zaza.events into in the tests system using global_options.

This sub-module provides the module level functions that test functions can use
to access the events system.

They are split out, as they rely on global_options.
"""


from zaza.global_options import get_option

from .plugins.logging import get_plugin_manager


def get_global_events_logging_manager():
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
    name = get_option("zaza-events.modules.logging.logger-name", None)
    if name is None:
        name = get_option("zaza-events.collection-name", "DEFAULT")
    return get_plugin_manager(name)


def get_global_event_logger_instance():
    """Get an event logger with prefilled fields for the collection.

    This returns an options configured event logger (proxy) with prefilled
    fields.  This is almost CERTAINLY the event logger that you want to use in
    zaza test functions.

    :returns: a configured LoggerInstance with prefilled collection and unit
        fields.
    :rtype: LoggerInstance
    """
    return get_global_events_logging_manager().get_event_logger()
