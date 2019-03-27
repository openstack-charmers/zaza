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

import zaza.utilities.openstack as openstack_utils
import zaza.charm_tests.nova.utils as nova_utils

boot_tests = {
    'cirros': {
        'image_name': 'cirros',
        'flavor_name': 'm1.tiny',
        'username': 'cirros',
        'bootstring': 'gocubsgo',
        'password': 'gocubsgo'},
    'bionic': {
        'image_name': 'bionic',
        'flavor_name': 'm1.small',
        'username': 'ubuntu',
        'bootstring': 'finished at'}}


def launch_instance(instance_key, use_boot_volume=False, vm_name=None,
                    private_network_name=None, image_name=None,
                    flavor_name=None, external_network_name=None, meta=None):
    """Launch an instance.

    :param instance_key: Key to collect associated config data with.
    :type instance_key: str
    :param use_boot_volume: Whether to boot guest from a shared volume.
    :type use_boot_volume: boolean
    :param vm_name: Name to give guest.
    :type vm_name: str
    :param private_network_name: Name of private network to attach guest to.
    :type private_network_name: str
    :param image_name: Image name to use with guest.
    :type image_name: str
    :param flavor_name: Flavor name to use with guest.
    :type flavor_name: str
    :param external_network_name: External network to create floating ip from
                                  for guest.
    :type external_network_name: str
    :param meta: A dict of arbitrary key/value metadata to store for this
                 server. Both keys and values must be <=255 characters.
    :type meta: dict
    """
    keystone_session = openstack_utils.get_overcloud_keystone_session()
    nova_client = openstack_utils.get_nova_session_client(keystone_session)
    neutron_client = openstack_utils.get_neutron_session_client(
        keystone_session)

    # Collect resource information.
    vm_name = vm_name or time.strftime("%Y%m%d%H%M%S")

    image_name = image_name or boot_tests[instance_key]['image_name']
    image = nova_client.glance.find_image(image_name)

    flavor_name = flavor_name or boot_tests[instance_key]['flavor_name']
    flavor = nova_client.flavors.find(name=flavor_name)

    private_network_name = private_network_name or "private"
    net = neutron_client.find_resource("network", private_network_name)
    nics = [{'net-id': net.get('id')}]

    meta = meta or {}
    external_network_name = external_network_name or "ext_net"

    if use_boot_volume:
        bdmv2 = [{
            'boot_index': '0',
            'uuid': image.id,
            'source_type': 'image',
            'volume_size': flavor.disk,
            'destination_type': 'volume',
            'delete_on_termination': True}]
        image = None
    else:
        bdmv2 = None

    # Launch instance.
    logging.info('Launching instance {}'.format(vm_name))
    instance = nova_client.servers.create(
        name=vm_name,
        image=image,
        block_device_mapping_v2=bdmv2,
        flavor=flavor,
        key_name=nova_utils.KEYPAIR_NAME,
        meta=meta,
        nics=nics)

    # Test Instance is ready.
    logging.info('Checking instance is active')
    openstack_utils.resource_reaches_status(
        nova_client.servers,
        instance.id,
        expected_status='ACTIVE',
        stop_after_attempt=16)

    logging.info('Checking cloud init is complete')
    openstack_utils.cloud_init_complete(
        nova_client,
        instance.id,
        boot_tests[instance_key]['bootstring'])
    port = openstack_utils.get_ports_from_device_id(
        neutron_client,
        instance.id)[0]
    logging.info('Assigning floating ip.')
    ip = openstack_utils.create_floating_ip(
        neutron_client,
        external_network_name,
        port=port)['floating_ip_address']
    logging.info('Assigned floating IP {} to {}'.format(ip, vm_name))
    openstack_utils.ping_response(ip)

    # Check ssh'ing to instance.
    logging.info('Testing ssh access.')
    openstack_utils.ssh_test(
        username=boot_tests[instance_key]['username'],
        ip=ip,
        vm_name=vm_name,
        password=boot_tests[instance_key].get('password'),
        privkey=openstack_utils.get_private_key(nova_utils.KEYPAIR_NAME))
