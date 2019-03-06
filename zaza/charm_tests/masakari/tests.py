#!/usr/bin/env python3

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

"""Encapsulate masakari testing."""

import logging

import novaclient

import zaza.model
import zaza.charm_tests.test_utils as test_utils
import zaza.utilities.openstack as openstack_utils
import zaza.utilities.juju as juju_utils
import zaza.configure.guest
import zaza.configure.masakari


class MasakariTest(test_utils.OpenStackBaseTest):
    """Encapsulate Masakari tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running tests."""
        super(MasakariTest, cls).setUpClass()
        cls.keystone_session = openstack_utils.get_overcloud_keystone_session()
        cls.model_name = zaza.model.get_juju_model()
        cls.nova_client = openstack_utils.get_nova_session_client(
            cls.keystone_session)

    def test_instance_failover(self):
        """Test masakari managed guest migration."""
        # Launch guest
        vm_name = 'zaza-test-instance-failover'
        try:
            self.nova_client.servers.find(name=vm_name)
            logging.info('Found existing guest')
        except novaclient.exceptions.NotFound:
            logging.info('Launching new guest')
            zaza.configure.guest.launch_instance(
                'bionic',
                use_boot_volume=True,
                vm_name=vm_name)

        # Locate hypervisor hosting guest and shut it down
        current_hypervisor = zaza.utilities.openstack.get_hypervisor_for_guest(
            self.nova_client,
            vm_name)
        unit_name = juju_utils.get_unit_name_from_host_name(
            current_hypervisor,
            'nova-compute')
        zaza.configure.masakari.simulate_compute_host_failure(
            unit_name,
            model_name=self.model_name)

        # Wait for instance move
        logging.info('Waiting for guest to move away from {}'.format(
            current_hypervisor))
        # wait_for_server_migration will throw an exception if migration fails
        zaza.utilities.openstack.wait_for_server_migration(
            self.nova_client,
            vm_name,
            current_hypervisor)

        # Bring things back
        zaza.configure.masakari.simulate_compute_host_recovery(
            unit_name,
            model_name=self.model_name)
        zaza.utilities.openstack.enable_all_nova_services(self.nova_client)
        zaza.configure.masakari.enable_hosts()
