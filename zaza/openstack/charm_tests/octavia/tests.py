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

"""Encapsulate octavia testing."""

import logging
import tenacity

import zaza.openstack.charm_tests.test_utils as test_utils
import zaza.openstack.utilities.openstack as openstack_utils


class CharmOperationTest(test_utils.OpenStackBaseTest):
    """Charm operation tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running Octavia charm operation tests."""
        super(CharmOperationTest, cls).setUpClass()

    def test_pause_resume(self):
        """Run pause and resume tests.

        Pause service and check services are stopped, then resume and check
        they are started.
        """
        self.pause_resume(['apache2'])


class LBAASv2Test(test_utils.OpenStackBaseTest):
    """LBaaSv2 service tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running LBaaSv2 service tests."""
        super(LBAASv2Test, cls).setUpClass()

    def test_create_loadbalancer(self):
        """Create load balancer."""
        keystone_session = openstack_utils.get_overcloud_keystone_session()
        neutron_client = openstack_utils.get_neutron_session_client(
            keystone_session)
        resp = neutron_client.list_networks(name='private')
        subnet_id = resp['networks'][0]['subnets'][0]
        octavia_client = openstack_utils.get_octavia_session_client(
            keystone_session)
        result = octavia_client.load_balancer_create(
            json={
                'loadbalancer': {
                    'description': 'Created by Zaza',
                    'admin_state_up': True,
                    'vip_subnet_id': subnet_id,
                    'name': 'zaza-lb-0',
                }})
        lb_id = result['loadbalancer']['id']

        @tenacity.retry(wait=tenacity.wait_fixed(1),
                        reraise=True, stop=tenacity.stop_after_delay(900))
        def wait_for_loadbalancer(octavia_client, load_balancer_id):
            resp = octavia_client.load_balancer_show(load_balancer_id)
            if resp['provisioning_status'] != 'ACTIVE':
                raise Exception('load balancer has not reached expected '
                                'status: {}'.format(resp))
            return resp
        logging.info('Awaiting loadbalancer to reach provisioning_status '
                     '"ACTIVE"')
        resp = wait_for_loadbalancer(octavia_client, lb_id)
        logging.info(resp)
