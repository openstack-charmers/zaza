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
        cls.from_series = None
        cls.to_series = None
        cls.workaround_script = None
        cls.files = []

    def test_200_run_series_upgrade(self):
        """Run series upgrade."""
        # Set Feature Flag
        os.environ["JUJU_DEV_FEATURE_FLAGS"] = "upgrade-series"

        applications = model.get_status().applications
        completed_machines = []
        for application in applications:
            # Defaults
            origin = "openstack-origin"
            pause_non_leader_subordinate = True
            pause_non_leader_primary = True
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
            if "ceph" in applications[application]["charm"]:
                origin = "source"
                pause_non_leader_primary = False
                pause_non_leader_subordinate = False
            if "memcached" in applications[application]["charm"]:
                origin = None
                pause_non_leader_primary = False
                pause_non_leader_subordinate = False
            if ("mongodb" in applications[application]["charm"] or
                    "vault" in applications[application]["charm"]):
                # Mongodb and vault need to run series upgrade
                # on its secondaries first.
                generic_utils.series_upgrade_non_leaders_first(
                    application,
                    from_series=self.from_series,
                    to_series=self.to_series,
                    completed_machines=completed_machines)
                continue

            # The rest are likley APIs use defaults

            generic_utils.series_upgrade_application(
                application,
                pause_non_leader_primary=pause_non_leader_primary,
                pause_non_leader_subordinate=pause_non_leader_subordinate,
                from_series=self.from_series,
                to_series=self.to_series,
                origin=origin,
                completed_machines=completed_machines,
                workaround_script=self.workaround_script,
                files=self.files)


class OpenStackSeriesUpgrade(SeriesUpgradeTest):
    """OpenStack Series Upgrade.

    Full OpenStack series upgrade with VM launch before and after the series
    upgrade.

    This test requires a full OpenStack including at least: keystone, glance,
    nova-cloud-controller, nova-compute, neutron-gateway, neutron-api and
    neutron-openvswitch.
    """

    @classmethod
    def setUpClass(cls):
        """Run setup for Series Upgrades."""
        super(OpenStackSeriesUpgrade, cls).setUpClass()
        cls.lts = LTSGuestCreateTest()
        cls.lts.setUpClass()

    def test_100_validate_pre_series_upgrade_cloud(self):
        """Validate pre series upgrade."""
        logging.info("Validate pre-series-upgrade: Spin up LTS instance")
        self.lts.test_launch_small_instance()

    def test_500_validate_series_upgraded_cloud(self):
        """Validate post series upgrade."""
        logging.info("Validate post-series-upgrade: Spin up LTS instance")
        self.lts.test_launch_small_instance()


class OpenStackTrustyXenialSeriesUpgrade(OpenStackSeriesUpgrade):
    """OpenStack Trusty to Xenial Series Upgrade."""

    @classmethod
    def setUpClass(cls):
        """Run setup for Trusty to Xenial Series Upgrades."""
        super(OpenStackTrustyXenialSeriesUpgrade, cls).setUpClass()
        cls.from_series = "trusty"
        cls.to_series = "xenial"


class OpenStackXenialBionicSeriesUpgrade(OpenStackSeriesUpgrade):
    """OpenStack Xenial to Bionic Series Upgrade."""

    @classmethod
    def setUpClass(cls):
        """Run setup for Xenial to Bionic Series Upgrades."""
        super(OpenStackXenialBionicSeriesUpgrade, cls).setUpClass()
        cls.from_series = "xenial"
        cls.to_series = "bionic"


class TrustyXenialSeriesUpgrade(SeriesUpgradeTest):
    """Trusty to Xenial Series Upgrade.

    Makes no assumptions about what is in the deployment.
    """

    @classmethod
    def setUpClass(cls):
        """Run setup for Trusty to Xenial Series Upgrades."""
        super(TrustyXenialSeriesUpgrade, cls).setUpClass()
        cls.from_series = "trusty"
        cls.to_series = "xenial"


class XenialBionicSeriesUpgrade(SeriesUpgradeTest):
    """Xenial to Bionic Series Upgrade.

    Makes no assumptions about what is in the deployment.
    """

    @classmethod
    def setUpClass(cls):
        """Run setup for Xenial to Bionic Series Upgrades."""
        super(XenialBionicSeriesUpgrade, cls).setUpClass()
        cls.from_series = "xenial"
        cls.to_series = "bionic"


if __name__ == "__main__":
    unittest.main()
