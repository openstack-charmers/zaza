#!/usr/bin/env python3

# Copyright 2018 Canonical Ltd.
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

"""Define class for Series Upgrade."""

import logging
import os
import unittest

from zaza import model
from zaza.utilities import (
    cli as cli_utils,
    generic as generic_utils,
)
from zaza.charm_tests.nova.tests import LTSGuestCreateTest


class SeriesUpgradeTest(unittest.TestCase):
    """Class to encapsulate Sereis Upgrade Tests."""

    @classmethod
    def setUpClass(cls):
        """Run setup for Series Upgrades."""
        cli_utils.setup_logging()
        cls.lts = LTSGuestCreateTest()

    def test_100_validate_pre_series_upgrade_cloud(self):
        """Validate pre series upgrade."""
        logging.info("Validate pre-series-upgrade: Spin up LTS instance")
        self.lts.test_launch_small_cirros_instance()

    def test_200_run_series_upgrade(self):
        """Run series upgrade."""
        # Set Feature Flag
        os.environ["JUJU_DEV_FEATURE_FLAGS"] = "upgrade-series"

        applications = model.get_status().applications
        from_series = "trusty"
        to_series = "xenial"
        for application in applications:
            # Defaults
            origin = "openstack-origin"
            pause_non_leader_subordinate = True
            pause_non_leader_primary = False
            # Skip subordinates
            if applications[application]["subordinate-to"]:
                continue
            if "percona-cluster" in applications[application]["charm"]:
                origin = "source"
                pause_non_leader_primary = True
                pause_non_leader_subordinate = True
            if "rabbitmq-server" in applications[application]["charm"]:
                origin = "source"
                pause_non_leader_primary = True
                pause_non_leader_subordinate = False
            if "nova-compute" in applications[application]["charm"]:
                pause_non_leader_primary = False
                pause_non_leader_subordinate = False
            # Place holder for Ceph applications
            # The rest are likley APIs and use defaults

            generic_utils.series_upgrade_application(
                application,
                pause_non_leader_primary=pause_non_leader_primary,
                pause_non_leader_subordinate=pause_non_leader_subordinate,
                from_series=from_series,
                to_series=to_series,
                origin=origin)

    def test_300_validate_series_upgraded_cloud(self):
        """Validate post series upgrade."""
        logging.info("Validate post-series-upgrade: Spin up LTS instance")
        self.lts.test_launch_small_cirros_instance()


if __name__ == "__main__":
    unittest.main()
