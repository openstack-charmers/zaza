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

See zaza.events.notifications for more details.
"""

import logging

from zaza.global_options import get_option
from zaza.events.notifications import EventsPlugin


logger = logging.getLogger(__name__)


def configure(env_deployments):
    """Configure the event plugin for events.

    If the 'zaza-events' config option is available, this configures the
    EventsPlugin that then glues zaza.notifications published events into
    zaza.events time-series notifications.

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
