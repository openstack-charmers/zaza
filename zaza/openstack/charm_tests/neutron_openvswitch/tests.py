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

"""Encapsulating `neutron-openvswitch` testing."""

import json
import logging
import unittest

import zaza
import zaza.openstack.utilities.openstack as openstack_utils


class NeutronOpenvSwitchOverlayTest(unittest.TestCase):
    """Class for `neutron-openvswitch` tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for `neutron-openvswitch` tests."""
        super(NeutronOpenvSwitchOverlayTest, cls).setUpClass()

    def test_tunnel_datapath(self):
        """From ports list, connect to unit in one end, ping other end(s)."""
        keystone_session = openstack_utils.get_overcloud_keystone_session()
        neutron_client = openstack_utils.get_neutron_session_client(
            keystone_session)

        resp = neutron_client.list_ports()
        ports = resp['ports']
        host_port = {}
        for port in ports:
            if (port['device_owner'].startswith('network:') or
                    port['device_owner'].startswith('compute:')):
                continue
            host_port[port['binding:host_id']] = port

        for unit in zaza.model.get_units('neutron-openvswitch'):
            result = zaza.model.run_on_unit(unit.entity_id, 'hostname')
            hostname = result['Stdout'].rstrip()
            if hostname not in host_port:
                # no port bound to this host, skip
                continue
            # get interface name from unit OVS data
            ovs_interface = json.loads(zaza.model.run_on_unit(
                unit.entity_id, 'ovs-vsctl -f json find Interface '
                                'external_ids:iface-id={}'
                                .format(host_port[hostname]['id']))['Stdout'])
            for (idx, heading) in enumerate(ovs_interface['headings']):
                if heading == 'name':
                    break
            else:
                raise Exception('Unable to find interface name from OVS')
            interface_name = ovs_interface['data'][0][idx]

            ip_unit = zaza.model.run_on_unit(
                unit.entity_id, 'ip addr show dev {}'
                                .format(interface_name))
            for other_host in (set(host_port) - set([hostname])):
                for ip_info in host_port[other_host]['fixed_ips']:
                    logging.info('Local IP info: "{}"'.format(ip_unit))
                    logging.info('PING "{}" --> "{}"...'
                                 .format(hostname, other_host))
                    result = zaza.model.run_on_unit(
                        unit.entity_id,
                        'ping -c 3 {}'.format(ip_info['ip_address']))
                    logging.info(result['Stdout'])
                    if result['Code'] == '1':
                        raise Exception('FAILED')
