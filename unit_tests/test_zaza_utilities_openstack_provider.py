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

import mock

import unit_tests.utils as ut_utils
import zaza.utilities.openstack_provider as openstack_provider


class TestOpenStackUtils(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestOpenStackUtils, self).setUp()
        self.port_name = "port_name"
        self.net_uuid = "net_uuid"
        self.project_id = "project_uuid"
        self.ext_net = "ext_net"
        self.private_net = "private_net"
        self.port = {
            "port": {"id": "port_id",
                     "name": self.port_name,
                     "network_id": self.net_uuid}}
        self.ports = {"ports": [self.port["port"]]}
        self.floatingip = {
            "floatingip": {"id": "floatingip_id",
                           "floating_network_id": self.net_uuid,
                           "port_id": "port_id"}}
        self.floatingips = {"floatingips": [self.floatingip["floatingip"]]}
        self.address_scope_name = "address_scope_name"
        self.address_scope = {
            "address_scope": {"id": "address_scope_id",
                              "name": self.address_scope_name,
                              "shared": True,
                              "ip_version": 4,
                              "tenant_id": self.project_id}}
        self.address_scopes = {
            "address_scopes": [self.address_scope["address_scope"]]}

        self.network = {
            "network": {"id": "network_id",
                              "name": self.ext_net,
                              "tenant_id": self.project_id,
                              "router:external": True,
                              "provider:physical_network": "physnet1",
                              "provider:network_type": "flat"}}

        self.networks = {
            "networks": [self.network["network"]]}

        self.agents = {
            "agents": [
                {
                    'id': '7f3afd5b-ff6d-4df3-be0e-3d9651e71873',
                    'binary': 'neutron-bgp-dragent',
                }]}

        self.bgp_speakers = {
            "bgp_speakers": [
                {
                    'id': '07a0798d-c29c-4a92-8fcb-c1ec56934729',
                }]}

        self.neutronclient = mock.MagicMock()
        self.neutronclient.list_ports.return_value = self.ports
        self.neutronclient.create_port.return_value = self.port

        self.neutronclient.list_floatingips.return_value = self.floatingips
        self.neutronclient.create_floatingip.return_value = self.floatingip

        self.neutronclient.list_address_scopes.return_value = (
            self.address_scopes)
        self.neutronclient.create_address_scope.return_value = (
            self.address_scope)

        self.neutronclient.list_networks.return_value = self.networks
        self.neutronclient.create_network.return_value = self.network

        self.neutronclient.list_agents.return_value = self.agents
        self.neutronclient.list_bgp_speaker_on_dragent.return_value = \
            self.bgp_speakers

    def test_get_undercloud_keystone_session(self):
        self.patch_object(openstack_provider, "get_keystone_session")
        self.patch_object(openstack_provider, "get_undercloud_auth")
        _auth = "FAKE_AUTH"
        self.get_undercloud_auth.return_value = _auth

        openstack_provider.get_undercloud_keystone_session()
        self.get_keystone_session.assert_called_once_with(_auth, verify=None)

    def test_get_nova_session_client(self):
        session_mock = mock.MagicMock()
        self.patch_object(openstack_provider.novaclient_client, "Client")
        openstack_provider.get_nova_session_client(session_mock)
        self.Client.assert_called_once_with(2, session=session_mock)
        self.Client.reset_mock()
        openstack_provider.get_nova_session_client(session_mock, version=2.56)
        self.Client.assert_called_once_with(2.56, session=session_mock)

    def test__resource_removed(self):
        resource_mock = mock.MagicMock()
        resource_mock.list.return_value = [mock.MagicMock(id='ba8204b0')]
        openstack_provider._resource_removed(resource_mock, 'e01df65a')

    def test__resource_removed_fail(self):
        resource_mock = mock.MagicMock()
        resource_mock.list.return_value = [mock.MagicMock(id='e01df65a')]
        with self.assertRaises(AssertionError):
            openstack_provider._resource_removed(resource_mock, 'e01df65a')

    def test_resource_removed(self):
        self.patch_object(openstack_provider, "_resource_removed")
        self._resource_removed.return_value = True
        openstack_provider.resource_removed('resource', 'e01df65a')
        self._resource_removed.assert_called_once_with(
            'resource',
            'e01df65a',
            'resource')

    def test_resource_removed_custom_retry(self):
        self.patch_object(openstack_provider, "_resource_removed")

        def _retryer(f, arg1, arg2, arg3):
            f(arg1, arg2, arg3)
        self.patch_object(
            openstack_provider.tenacity,
            "Retrying",
            return_value=_retryer)
        saa_mock = mock.MagicMock()
        self.patch_object(
            openstack_provider.tenacity,
            "stop_after_attempt",
            return_value=saa_mock)
        we_mock = mock.MagicMock()
        self.patch_object(
            openstack_provider.tenacity,
            "wait_exponential",
            return_value=we_mock)
        self._resource_removed.return_value = True
        openstack_provider.resource_removed(
            'resource',
            'e01df65a',
            wait_exponential_multiplier=2,
            wait_iteration_max_time=20,
            stop_after_attempt=2)
        self._resource_removed.assert_called_once_with(
            'resource',
            'e01df65a',
            'resource')
        self.Retrying.assert_called_once_with(
            wait=we_mock,
            reraise=True,
            stop=saa_mock)

    def test_delete_resource(self):
        resource_mock = mock.MagicMock()
        self.patch_object(openstack_provider, "resource_removed")
        openstack_provider.delete_resource(resource_mock, 'e01df65a')
        resource_mock.delete.assert_called_once_with('e01df65a')
        self.resource_removed.assert_called_once_with(
            resource_mock,
            'e01df65a',
            'resource')

    def test_get_keystone_session(self):
        self.patch_object(openstack_provider, "session")
        self.patch_object(openstack_provider, "v2")
        _auth = mock.MagicMock()
        self.v2.Password.return_value = _auth
        _openrc = {
            "OS_AUTH_URL": "https://keystone:5000",
            "OS_USERNAME": "myuser",
            "OS_PASSWORD": "pass",
            "OS_TENANT_NAME": "tenant",
        }
        openstack_provider.get_keystone_session(_openrc)
        self.session.Session.assert_called_once_with(auth=_auth, verify=None)

    def test_get_keystone_session_tls(self):
        self.patch_object(openstack_provider, "session")
        self.patch_object(openstack_provider, "v2")
        _auth = mock.MagicMock()
        self.v2.Password.return_value = _auth
        _cacert = "/tmp/cacert"
        _openrc = {
            "OS_AUTH_URL": "https://keystone:5000",
            "OS_USERNAME": "myuser",
            "OS_PASSWORD": "pass",
            "OS_TENANT_NAME": "tenant",
            "OS_CACERT": _cacert,
        }
        openstack_provider.get_keystone_session(_openrc)
        self.session.Session.assert_called_once_with(
            auth=_auth, verify=_cacert)
