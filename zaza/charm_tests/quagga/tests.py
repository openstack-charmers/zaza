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

"""Encapsulating `quagga` testing."""

import logging
import re
import unittest

import zaza


class QuaggaTest(unittest.TestCase):
    """Class for `quagga` tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for `quagga` tests."""
        super(QuaggaTest, cls).setUpClass()

    def test_bgp_peer_datapath(self):
        """Get peers from BGP neighbour list and ping them."""
        status = zaza.model.get_status()
        applications = (app for app in ['spine0', 'spine1', 'tor0', 'tor1',
                                        'tor2', 'peer0', 'peer1']
                        if app in status.applications.keys())
        for application in applications:
                for unit in zaza.model.get_units(application):
                    bgp_sum = zaza.model.run_on_unit(
                        unit.entity_id,
                        'echo "sh bgp ipv4 unicast summary" | vtysh')['Stdout']
                    r = re.compile('^(\d+\.\d+\.\d+\.\d+)')
                    ip_list = []
                    for line in bgp_sum.splitlines():
                        m = r.match(line)
                        if m:
                            ip_list.append(m.group(1))
                    logging.info('unit {} neighbours {}'
                                 .format(unit.entity_id, ip_list))

                    if not ip_list:
                        raise Exception('FAILED: Unit {} has no BGP peers.'
                                        .format(unit.entity_id))
                    for ip in ip_list:
                        result = zaza.model.run_on_unit(
                            unit.entity_id,
                            'ping -c 3 {}'.format(ip))
                        logging.info(result['Stdout'])
                        if result['Code'] == '1':
                            raise Exception('FAILED')
