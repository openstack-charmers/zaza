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

"""Collection of code for setting up and testing keystone."""
import zaza
import zaza.openstack.charm_tests.test_utils as test_utils
import zaza.openstack.utilities.openstack as openstack_utils

DEMO_TENANT = 'demoTenant'
DEMO_DOMAIN = 'demoDomain'
DEMO_PROJECT = 'demoProject'
DEMO_ADMIN_USER = 'demo_admin'
DEMO_ADMIN_USER_PASSWORD = 'password'
DEMO_USER = 'demo'
DEMO_PASSWORD = 'password'


class BaseKeystoneTest(test_utils.OpenStackBaseTest):
    """Base for Keystone charm tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running Keystone charm operation tests."""
        super(BaseKeystoneTest, cls).setUpClass()
        # Check if we are related to Vault TLS certificates
        cls.tls_rid = zaza.model.get_relation_id(
            'keystone', 'vault', remote_interface_name='certificates')
        # Check for VIP
        cls.vip = (zaza.model.get_application_config('keystone')
                   .get('vip').get('value'))
        cls.keystone_ips = zaza.model.get_app_ips('keystone')
        # If we have a VIP set and we are using TLS only check the VIP
        # If you check the individual IP haproxy may send to a different
        # back end which leads to mismatched certificates.
        if cls.vip:
            if cls.tls_rid:
                cls.keystone_ips = [cls.vip]
            else:
                cls.keystone_ips.append(cls.vip)
        if (openstack_utils.get_os_release() <
                openstack_utils.get_os_release('xenial_queens')):
            cls.default_api_version = '2'
        else:
            cls.default_api_version = '3'
        cls.admin_keystone_session = (
            openstack_utils.get_overcloud_keystone_session())
        cls.admin_keystone_client = (
            openstack_utils.get_keystone_session_client(
                cls.admin_keystone_session,
                client_api_version=cls.default_api_version))
