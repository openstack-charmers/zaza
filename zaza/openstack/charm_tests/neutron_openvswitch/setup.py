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

"""Code for setting up neutron-openvswitch."""

import logging
import pprint

import zaza

import zaza.openstack.utilities.openstack as openstack_utils


def overlay_network():
    """Create network with subnets, add OVS port per unit.

    Useful for testing that the `neutron-openvswitch` charm configures the
    system, LXD profiles etc in such a way that the Neutron OpenvSwitch
    agent is able to perform the required OVS configuration.
    """
    keystone_session = openstack_utils.get_overcloud_keystone_session()
    neutron_client = openstack_utils.get_neutron_session_client(
        keystone_session)

    resp = neutron_client.create_network(
        {'network': {'name': 'zaza-neutron-openvswitch-network'}})
    network = resp['network']
    logging.info('created network {}'.format(pprint.pformat(network)))

    # make rfc4193 Unique Local IPv6 Unicast Addresses from network UUID
    rfc4193_addr = 'fc00'
    for n in [0, 4, 8]:
        rfc4193_addr += ':' + network['id'].split('-')[4][n:n + 4]
    rfc4193_addr += '::/64'

    resp = neutron_client.create_subnet(
        {
            'subnets': [
                {
                    'name': 'zaza-neutron-openvswitch-subnet',
                    'ip_version': 4,
                    'cidr': '10.42.42.0/24',
                    'network_id': network['id'],
                },
                {
                    'name': 'zaza-neutron-openvswitch-subnetv6',
                    'ip_version': 6,
                    'ipv6_address_mode': 'slaac',
                    'ipv6_ra_mode': 'slaac',
                    'cidr': rfc4193_addr,
                    'network_id': network['id'],
                },
            ],
        })
    logging.info('created subnets {}'
                 .format(pprint.pformat(resp['subnets'])))

    for unit in zaza.model.get_units('neutron-openvswitch'):
        result = zaza.model.run_on_unit(unit.entity_id, 'hostname')
        hostname = result['Stdout'].rstrip()
        logging.info('hostname: "{}"'.format(hostname))
        resp = neutron_client.create_port(
            {
                'port': {
                    'binding:host_id': hostname,
                    'device_owner': 'Zaza:neutron-openvswitch-test',
                    'name': hostname,
                    'network_id': network['id'],
                },
            })
        port = resp['port']
        logging.info('created port {}'
                     .format(pprint.pformat(port)))
        result = zaza.model.run_on_unit(
            unit.entity_id,
            'ovs-vsctl -- --may-exist add-port br-int zaza0 '
            '-- set Interface zaza0 type=internal '
            '-- set Interface zaza0 external-ids:iface-status=active '
            '-- set Interface zaza0 external-ids:attached-mac={} '
            '-- set Interface zaza0 external-ids:iface-id={} '
            '-- set Interface zaza0 external-ids:skip_cleanup=true '
            .format(port['mac_address'], port['id']))
        logging.info('do ovs configuration {}'
                     .format(pprint.pformat(result)))
        result = zaza.model.run_on_unit(
            unit.entity_id,
            'ip link set dev zaza0 address {} up'
            .format(port['mac_address']))
        logging.info('ip link {}'
                     .format(pprint.pformat(result)))
        for ip_info in port['fixed_ips']:
            # NOTE(fnordahl) overly simplified but is sufficient for test
            if ':' in ip_info['ip_address']:
                bits = '64'
            else:
                bits = '24'
            result = zaza.model.run_on_unit(
                unit.entity_id,
                'ip addr add {}/{} dev zaza0'
                .format(ip_info['ip_address'], bits))
            logging.info('ip addr add {}'
                         .format(pprint.pformat(result)))
