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

"""Encapsulate nova testing."""

import logging
import time
import unittest

import zaza.model as model
import zaza.utilities.openstack as openstack_utils
import zaza.charm_tests.nova.utils as nova_utils


class BaseGuestCreateTest(unittest.TestCase):
    """Base for tests to launch a guest."""

    boot_tests = {
        'cirros': {
            'image_name': 'cirrosimage',
            'flavor_name': 'm1.tiny',
            'username': 'cirros',
            'bootstring': 'gocubsgo',
            'password': 'gocubsgo'},
        'bionic': {
            'image_name': 'bionic',
            'flavor_name': 'm1.small',
            'username': 'ubuntu',
            'bootstring': 'finished at'}}

    @classmethod
    def setUpClass(cls):
        """Run class setup for running glance tests."""
        cls.keystone_session = openstack_utils.get_overcloud_keystone_session()
        cls.model_name = model.get_juju_model()
        cls.nova_client = openstack_utils.get_nova_session_client(
            cls.keystone_session)
        cls.neutron_client = openstack_utils.get_neutron_session_client(
            cls.keystone_session)

    def launch_instance(self, instance_key):
        """Launch an instance.

        :param instance_key: Key to collect associated config data with.
        :type instance_key: str
        """
        # Collect resource information.
        vm_name = time.strftime("%Y%m%d%H%M%S")
        image = self.nova_client.glance.find_image(
            self.boot_tests[instance_key]['image_name'])
        flavor = self.nova_client.flavors.find(
            name=self.boot_tests[instance_key]['flavor_name'])
        net = self.neutron_client.find_resource("network", "private")
        nics = [{'net-id': net.get('id')}]

        # Launch instance.
        logging.info('Launching instance {}'.format(vm_name))
        instance = self.nova_client.servers.create(
            name=vm_name,
            image=image,
            flavor=flavor,
            key_name=nova_utils.KEYPAIR_NAME,
            nics=nics)

        # Test Instance is ready.
        logging.info('Checking instance is active')
        openstack_utils.resource_reaches_status(
            self.nova_client.servers,
            instance.id,
            expected_status='ACTIVE')

        logging.info('Checking cloud init is complete')
        openstack_utils.cloud_init_complete(
            self.nova_client,
            instance.id,
            self.boot_tests[instance_key]['bootstring'])
        port = openstack_utils.get_ports_from_device_id(
            self.neutron_client,
            instance.id)[0]
        logging.info('Assigning floating ip.')
        ip = openstack_utils.create_floating_ip(
            self.neutron_client,
            "ext_net",
            port=port)['floating_ip_address']
        logging.info('Assigned floating IP {} to {}'.format(ip, vm_name))
        openstack_utils.ping_response(ip)

        # Check ssh'ing to instance.
        logging.info('Testing ssh access.')
        openstack_utils.ssh_test(
            username=self.boot_tests[instance_key]['username'],
            ip=ip,
            vm_name=vm_name,
            password=self.boot_tests[instance_key].get('password'),
            privkey=openstack_utils.get_private_key(nova_utils.KEYPAIR_NAME))


class CirrosGuestCreateTest(BaseGuestCreateTest):
    """Tests to launch a cirros image."""

    def test_launch_small_cirros_instance(self):
        """Launch a cirros instance and test connectivity."""
        self.launch_instance('cirros')


class LTSGuestCreateTest(BaseGuestCreateTest):
    """Tests to launch a LTS image."""

    def test_launch_small_cirros_instance(self):
        """Launch a cirros instance and test connectivity."""
        self.launch_instance('bionic')
