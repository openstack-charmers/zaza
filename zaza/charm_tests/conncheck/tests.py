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

"""Tests for conncheck/zaza integration tests."""


import logging
import time
import unittest
import time

import zaza.events
import zaza.model
import zaza.global_options
import zaza.utilities.generic


logger = logging.getLogger(__name__)


class TestConncheckIntegration(unittest.TestCase):
    """Code for validating ConnCheck integation."""

    @classmethod
    def setUpClass(cls):
        """Run class setup."""
        super().setUpClass()

    def test_instances(self):
        """Setup the ConnCheck instances on the Ubuntu units."""
        logger.info('Setup the logging environment and install ConnCheck.')

        conncheck_manager = zaza.events.get_conncheck_manager()
        events = zaza.events.get_event_logger()

        # Configure the conncheck manager
        span = events.span()
        events.log(zaza.events.BEGIN,
                   span=span,
                   comment="start ConnCheck configuration")

        # add an instance to each of the units
        model = zaza.model.get_juju_model()
        logger.info("model is type(%s) '%s'", type(model), model)
        apps = zaza.model.sync_deployed(model)
        logger.info("apps are: %s", apps)
        assert 'ubuntu' in apps
        app = 'ubuntu'
        instances = [
            conncheck_manager.add_instance("juju:{}".format(unit.name))
            for unit in sorted(
                zaza.model.get_units(app), key=lambda m: m.name)]

        # One listener, one http sender
        instances[0].add_listener('udp', 8080)
        instances[1].add_speaker('udp', 8080, instances[0])

        # start them speaking.
        events.log(zaza.events.COMMENT,
                   span=span,
                   comment="ConnCheck instances configuring")
        for instance in instances:
            instance.start()
        events.log(zaza.events.END,
                   span=span,
                   comment="ConnCheck configured")

        for n in range(5):
            events.log(zaza.events.COMMENT,
                       comment="Sleeping for 5 seconds: {} of 5"
                       .format(n + 1))
            time.sleep(5)

        # Now reboot the first instance.
        logger.error("instances[0] is: %s", instances[0])
        logger.error("instances[0].machine_or_unit_spec: %s",
                     instances[0].machine_or_unit_spec)
        unit_name = instances[0].name
        with events.span("Rebooting {}".format(unit_name)):
            zaza.utilities.generic.reboot(unit_name)
            time.sleep(10)
            # zaza.model.block_until_unit_wl_status(unit_name, "unknown")
            zaza.model.block_until_all_units_idle()

        # Now wait a while to allow more events to be collected.
        for n in range(5):
            events.log(zaza.events.COMMENT,
                       comment="Sleeping for 5 seconds: {} of 5"
                       .format(n + 1))
            time.sleep(5)

        with events.span("Finalising ConnCheck instances."):
            for instance in instances:
                instance.finalise()

        events.log(zaza.events.COMMENT, comment="Test ended")

        # Note that the zaza framework will now finalise and upload the events
        # to wherever they are configured.
