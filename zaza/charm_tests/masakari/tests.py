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

from datetime import datetime
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

    @classmethod
    def tearDown(cls):
        """Bring hypervisors and services back up."""
        logging.info('Running teardown')
        for unit in zaza.model.get_units('nova-compute',
                                         model_name=cls.model_name):
            zaza.configure.masakari.simulate_compute_host_recovery(
                unit.entity_id,
                model_name=cls.model_name)
        zaza.utilities.openstack.enable_all_nova_services(cls.nova_client)
        zaza.configure.masakari.enable_hosts()

    def ensure_guest(self, vm_name):
        """Return the existing guest or boot a new one.

        :param vm_name: Name of guest to lookup
        :type vm_name: str
        :returns: Guest matching name.
        :rtype: novaclient.v2.servers.Server
        """
        try:
            guest = self.nova_client.servers.find(name=vm_name)
            logging.info('Found existing guest')
        except novaclient.exceptions.NotFound:
            logging.info('Launching new guest')
            guest = zaza.configure.guest.launch_instance(
                'bionic',
                use_boot_volume=True,
                vm_name=vm_name)
        return guest

    def get_guests_compute_info(self, vm_name):
        """Return the hostname & juju unit of compute host hosting vm.

        :param vm_name: Name of guest to lookup
        :type vm_name: str
        :returns: Hypervisor name and juju unit name
        :rtype: (str, str)
        """
        current_hypervisor = zaza.utilities.openstack.get_hypervisor_for_guest(
            self.nova_client,
            vm_name)
        unit_name = juju_utils.get_unit_name_from_host_name(
            current_hypervisor,
            'nova-compute')
        return current_hypervisor, unit_name

    def get_guest_qemu_pid(self, compute_unit_name, vm_uuid, model_name=None):
        """Return the qemu pid of process running guest.

        :param compute_unit_name: Juju unit name of hypervisor running guest
        :type compute_unit_name: str
        :param vm_uuid: Guests UUID
        :type vm_uuid: str
        :param model_name: Name of model running cloud.
        :type model_name: str
        :returns: PID of qemu process
        :rtype: int
        """
        pid_find_cmd = 'pgrep -u libvirt-qemu -f {}'.format(vm_uuid)
        out = zaza.model.run_on_unit(
            compute_unit_name,
            pid_find_cmd,
            model_name=self.model_name)
        return int(out['Stdout'].strip())

    def test_instance_failover(self):
        """Test masakari managed guest migration."""
        # Launch guest
        vm_name = 'zaza-test-instance-failover'
        self.ensure_guest(vm_name)

        # Locate hypervisor hosting guest and shut it down
        current_hypervisor, unit_name = self.get_guests_compute_info(vm_name)
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

    def test_instance_restart_on_fail(self):
        """Test singlee guest crash and recovery."""
        vm_name = 'zaza-test-instance-failover'
        vm = self.ensure_guest(vm_name)
        _, unit_name = self.get_guests_compute_info(vm_name)
        logging.info('{} is running on {}'.format(vm_name, unit_name))
        guest_pid = self.get_guest_qemu_pid(
            unit_name,
            vm.id,
            model_name=self.model_name)
        logging.info('{} pid is {}'.format(vm_name, guest_pid))
        inital_update_time = datetime.strptime(
            vm.updated,
            "%Y-%m-%dT%H:%M:%SZ")
        logging.info('Simulating vm crash of {}'.format(vm_name))
        zaza.configure.masakari.simulate_vm_crash(
            guest_pid,
            unit_name,
            model_name=self.model_name)
        logging.info('Waiting for {} to be updated and become active'.format(
            vm_name))
        zaza.utilities.openstack.wait_for_server_update_and_active(
            self.nova_client,
            vm_name,
            inital_update_time)
        new_guest_pid = self.get_guest_qemu_pid(
            unit_name,
            vm.id,
            model_name=self.model_name)
        logging.info('{} pid is now {}'.format(vm_name, guest_pid))
        assert new_guest_pid and new_guest_pid != guest_pid, (
            "Restart failed or never happened")
