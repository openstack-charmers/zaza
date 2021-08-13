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

"""Time-Series Event Framework for zaza.

This module provides a set of functions and classes to enable the creation and
collection of event logs from a variety of places:

 - zaza tests - instrumentation of test code with events.
 - juju unit logs - scraping juju logs for useful events (hooks, actions, etc.)
       and converting them into logs.
 - ConnCheck - data plane connectivity monitoring events.

The module provides a mechanism to define and record all of the log files
associated with events. It is then able to provide a mechanism to iterate
though all the logs and create a single 'event' stream for uploading to a
database (or writing to further file).

Key ideas:

 1. All events belong to a collection. A collection has a name (and this needs
    to appear in the logs).
 2. Logs have 'fields' and 'tags' -- essentially, this is modelled on InfluxDB.
    Key fields are 'unit', 'item', and 'event'.
    'unit' is something like a juju unit, or a ConnCheck instance, or a test
    name. An 'item' is a part of a unit. (e.g. listener, test, etc.)
    Due to the way influxdb handles tags, comments need to be a field so that
    they can contain spaces.
 3. Logs come in different formats, but InfluxDB format is the key one for
    bringing together all the logs.  Events are primarily InfluxDB events.
"""


from .collection import get_collection  # NOQA
# NOQA
from .plugins.logging import ( # NOQA
    get_logger_instance,
    get_logger,
)
from .plugins.conncheck import get_conncheck_manager  # NOQA
from .types import (  # NOQA
    LogFormats,
    Events,
)
from .tests_integration import ( # NOQA
    get_global_events_logging_manager,
    get_global_event_logger_instance,
)
