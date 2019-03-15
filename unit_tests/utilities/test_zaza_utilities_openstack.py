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

import copy
import datetime
import io
import mock
import tenacity

import unit_tests.utils as ut_utils
from zaza.utilities import openstack as openstack_utils
from zaza.utilities import exceptions


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

    def test_create_port(self):
        self.patch_object(openstack_utils, "get_net_uuid")
        self.get_net_uuid.return_value = self.net_uuid

        # Already exists
        port = openstack_utils.create_port(
            self.neutronclient, self.port_name, self.private_net)
        self.assertEqual(port, self.port["port"])
        self.neutronclient.create_port.assert_not_called()

        # Does not yet exist
        self.neutronclient.list_ports.return_value = {"ports": []}
        self.port["port"].pop("id")
        port = openstack_utils.create_port(
            self.neutronclient, self.port_name, self.private_net)
        self.assertEqual(port, self.port["port"])
        self.neutronclient.create_port.assert_called_once_with(self.port)

    def test_create_floating_ip(self):
        self.patch_object(openstack_utils, "get_net_uuid")
        self.get_net_uuid.return_value = self.net_uuid

        # Already exists
        floatingip = openstack_utils.create_floating_ip(
            self.neutronclient, self.ext_net, port=self.port["port"])
        self.assertEqual(floatingip, self.floatingip["floatingip"])
        self.neutronclient.create_floatingip.assert_not_called()

        # Does not yet exist
        self.neutronclient.list_floatingips.return_value = {"floatingips": []}
        self.floatingip["floatingip"].pop("id")
        floatingip = openstack_utils.create_floating_ip(
            self.neutronclient, self.private_net, port=self.port["port"])
        self.assertEqual(floatingip, self.floatingip["floatingip"])
        self.neutronclient.create_floatingip.assert_called_once_with(
            self.floatingip)

    def test_create_address_scope(self):
        self.patch_object(openstack_utils, "get_net_uuid")
        self.get_net_uuid.return_value = self.net_uuid

        # Already exists
        address_scope = openstack_utils.create_address_scope(
            self.neutronclient, self.project_id, self.address_scope_name)
        self.assertEqual(address_scope, self.address_scope["address_scope"])
        self.neutronclient.create_address_scope.assert_not_called()

        # Does not yet exist
        self.neutronclient.list_address_scopes.return_value = {
            "address_scopes": []}
        address_scope_msg = copy.deepcopy(self.address_scope)
        address_scope_msg["address_scope"].pop("id")
        address_scope = openstack_utils.create_address_scope(
            self.neutronclient, self.project_id, self.address_scope_name)
        self.assertEqual(address_scope, self.address_scope["address_scope"])
        self.neutronclient.create_address_scope.assert_called_once_with(
            address_scope_msg)

    def test_create_external_network(self):
        self.patch_object(openstack_utils, "get_net_uuid")
        self.get_net_uuid.return_value = self.net_uuid

        # Already exists
        network = openstack_utils.create_external_network(
            self.neutronclient, self.project_id, False)
        self.assertEqual(network, self.network["network"])
        self.neutronclient.create_network.assert_not_called()

        # Does not yet exist
        self.neutronclient.list_networks.return_value = {
            "networks": []}
        network_msg = copy.deepcopy(self.network)
        network_msg["network"].pop("id")
        network = openstack_utils.create_external_network(
            self.neutronclient, self.project_id, False)
        self.assertEqual(network, self.network["network"])
        self.neutronclient.create_network.assert_called_once_with(
            network_msg)

    def test_get_keystone_scope(self):
        self.patch_object(openstack_utils, "get_current_os_versions")

        # <= Liberty
        self.get_current_os_versions.return_value = {"keystone": "liberty"}
        self.assertEqual(openstack_utils.get_keystone_scope(), "DOMAIN")
        # > Liberty
        self.get_current_os_versions.return_value = {"keystone": "mitaka"}
        self.assertEqual(openstack_utils.get_keystone_scope(), "PROJECT")

    def _test_get_overcloud_auth(self, tls_relation=False, ssl_cert=False,
                                 v2_api=False):
        self.patch_object(openstack_utils.model, 'get_relation_id')
        self.patch_object(openstack_utils, 'get_application_config_option')
        self.patch_object(openstack_utils, 'get_keystone_ip')
        self.patch_object(openstack_utils, "get_current_os_versions")
        self.patch_object(openstack_utils.juju_utils, 'leader_get')
        if tls_relation:
            self.patch_object(openstack_utils.model, "scp_from_unit")
            self.patch_object(openstack_utils.model, "get_first_unit_name")
            self.get_first_unit_name.return_value = "keystone/4"
            self.patch_object(openstack_utils.os, "chmod")
            self.patch_object(openstack_utils.os, "path")
            self.path.return_value = True

        self.get_keystone_ip.return_value = '127.0.0.1'
        self.get_relation_id.return_value = None
        self.get_application_config_option.return_value = None
        self.leader_get.return_value = 'openstack'
        if tls_relation or ssl_cert:
            port = 35357
            transport = 'https'
            if tls_relation:
                self.get_relation_id.return_value = 'tls-certificates:1'
            if ssl_cert:
                self.get_application_config_option.side_effect = [
                    'FAKECRTDATA',
                    None,
                ]
        else:
            port = 5000
            transport = 'http'
        if v2_api:
            str_api = 'v2.0'
            self.get_current_os_versions.return_value = {"keystone": "mitaka"}
            expect = {
                'OS_AUTH_URL': '{}://127.0.0.1:{}/{}'
                               .format(transport, port, str_api),
                'OS_TENANT_NAME': 'admin',
                'OS_USERNAME': 'admin',
                'OS_PASSWORD': 'openstack',
                'OS_REGION_NAME': 'RegionOne',
                'API_VERSION': 2,
            }
        else:
            str_api = 'v3'
            self.get_current_os_versions.return_value = {"keystone": "queens"}
            expect = {
                'OS_AUTH_URL': '{}://127.0.0.1:{}/{}'
                               .format(transport, port, str_api),
                'OS_USERNAME': 'admin',
                'OS_PASSWORD': 'openstack',
                'OS_REGION_NAME': 'RegionOne',
                'OS_DOMAIN_NAME': 'admin_domain',
                'OS_USER_DOMAIN_NAME': 'admin_domain',
                'OS_PROJECT_NAME': 'admin',
                'OS_PROJECT_DOMAIN_NAME': 'admin_domain',
                'API_VERSION': 3,
            }
        if tls_relation:
            expect['OS_CACERT'] = openstack_utils.KEYSTONE_LOCAL_CACERT
        self.assertEqual(openstack_utils.get_overcloud_auth(),
                         expect)

    def test_get_overcloud_auth(self):
        self._test_get_overcloud_auth()

    def test_get_overcloud_auth_v2(self):
        self._test_get_overcloud_auth(v2_api=True)

    def test_get_overcloud_auth_tls_relation(self):
        self._test_get_overcloud_auth(tls_relation=True)

    def test_get_overcloud_auth_tls_relation_v2(self):
        self._test_get_overcloud_auth(v2_api=True, tls_relation=True)

    def test_get_overcloud_auth_ssl_cert(self):
        self._test_get_overcloud_auth(ssl_cert=True)

    def test_get_overcloud_auth_ssl_cert_v2(self):
        self._test_get_overcloud_auth(v2_api=True, ssl_cert=True)

    def test_get_overcloud_keystone_session(self):
        self.patch_object(openstack_utils, "get_keystone_session")
        self.patch_object(openstack_utils, "get_keystone_scope")
        self.patch_object(openstack_utils, "get_overcloud_auth")
        _auth = "FAKE_AUTH"
        _scope = "PROJECT"
        self.get_keystone_scope.return_value = _scope
        self.get_overcloud_auth.return_value = _auth

        openstack_utils.get_overcloud_keystone_session()
        self.get_keystone_session.assert_called_once_with(_auth, scope=_scope,
                                                          verify=None)

    def test_get_undercloud_keystone_session(self):
        self.patch_object(openstack_utils, "get_keystone_session")
        self.patch_object(openstack_utils, "get_undercloud_auth")
        _auth = "FAKE_AUTH"
        self.get_undercloud_auth.return_value = _auth

        openstack_utils.get_undercloud_keystone_session()
        self.get_keystone_session.assert_called_once_with(_auth, verify=None)

    def test_get_urllib_opener(self):
        self.patch_object(openstack_utils.urllib.request, "ProxyHandler")
        self.patch_object(openstack_utils.urllib.request, "HTTPHandler")
        self.patch_object(openstack_utils.urllib.request, "build_opener")
        self.patch_object(openstack_utils.os, "getenv")
        self.getenv.return_value = None
        HTTPHandler_mock = mock.MagicMock()
        self.HTTPHandler.return_value = HTTPHandler_mock
        openstack_utils.get_urllib_opener()
        self.build_opener.assert_called_once_with(HTTPHandler_mock)
        self.HTTPHandler.assert_called_once_with()

    def test_get_urllib_opener_proxy(self):
        self.patch_object(openstack_utils.urllib.request, "ProxyHandler")
        self.patch_object(openstack_utils.urllib.request, "HTTPHandler")
        self.patch_object(openstack_utils.urllib.request, "build_opener")
        self.patch_object(openstack_utils.os, "getenv")
        self.getenv.return_value = 'http://squidy'
        ProxyHandler_mock = mock.MagicMock()
        self.ProxyHandler.return_value = ProxyHandler_mock
        openstack_utils.get_urllib_opener()
        self.build_opener.assert_called_once_with(ProxyHandler_mock)
        self.ProxyHandler.assert_called_once_with({'http': 'http://squidy'})

    def test_get_images_by_name(self):
        image_mock1 = mock.MagicMock()
        image_mock1.name = 'bob'
        image_mock2 = mock.MagicMock()
        image_mock2.name = 'bill'
        glance_client = mock.MagicMock()
        glance_client.images.list.return_value = [image_mock1, image_mock2]
        self.assertEqual(
            openstack_utils.get_images_by_name(glance_client, 'bob'),
            [image_mock1])
        self.assertEqual(
            openstack_utils.get_images_by_name(glance_client, 'frank'),
            [])

    def test_find_cirros_image(self):
        urllib_opener_mock = mock.MagicMock()
        self.patch_object(openstack_utils, "get_urllib_opener")
        self.get_urllib_opener.return_value = urllib_opener_mock
        urllib_opener_mock.open().read.return_value = b'12'
        self.assertEqual(
            openstack_utils.find_cirros_image('aarch64'),
            'http://download.cirros-cloud.net/12/cirros-12-aarch64-disk.img')

    def test_find_ubuntu_image(self):
        self.assertEqual(
            openstack_utils.find_ubuntu_image('bionic', 'aarch64'),
            ('http://cloud-images.ubuntu.com/bionic/current/'
             'bionic-server-cloudimg-aarch64.img'))

    def test_download_image(self):
        urllib_opener_mock = mock.MagicMock()
        self.patch_object(openstack_utils, "get_urllib_opener")
        self.get_urllib_opener.return_value = urllib_opener_mock
        self.patch_object(openstack_utils.urllib.request, "install_opener")
        self.patch_object(openstack_utils.urllib.request, "urlretrieve")
        openstack_utils.download_image('http://cirros/c.img', '/tmp/c1.img')
        self.install_opener.assert_called_once_with(urllib_opener_mock)
        self.urlretrieve.assert_called_once_with(
            'http://cirros/c.img', '/tmp/c1.img')

    def test_resource_reaches_status(self):
        resource_mock = mock.MagicMock()
        resource_mock.get.return_value = mock.MagicMock(status='available')
        openstack_utils.resource_reaches_status(resource_mock, 'e01df65a')

    def test_resource_reaches_status_fail(self):
        openstack_utils.resource_reaches_status.retry.wait = \
            tenacity.wait_none()
        resource_mock = mock.MagicMock()
        resource_mock.get.return_value = mock.MagicMock(status='unavailable')
        with self.assertRaises(AssertionError):
            openstack_utils.resource_reaches_status(
                resource_mock,
                'e01df65a')

    def test_resource_reaches_status_bespoke(self):
        resource_mock = mock.MagicMock()
        resource_mock.get.return_value = mock.MagicMock(status='readyish')
        openstack_utils.resource_reaches_status(
            resource_mock,
            'e01df65a',
            'readyish')

    def test_resource_reaches_status_bespoke_fail(self):
        openstack_utils.resource_reaches_status.retry.wait = \
            tenacity.wait_none()
        resource_mock = mock.MagicMock()
        resource_mock.get.return_value = mock.MagicMock(status='available')
        with self.assertRaises(AssertionError):
            openstack_utils.resource_reaches_status(
                resource_mock,
                'e01df65a',
                'readyish')

    def test_resource_removed(self):
        resource_mock = mock.MagicMock()
        resource_mock.list.return_value = [mock.MagicMock(id='ba8204b0')]
        openstack_utils.resource_removed(resource_mock, 'e01df65a')

    def test_resource_removed_fail(self):
        openstack_utils.resource_reaches_status.retry.wait = \
            tenacity.wait_none()
        resource_mock = mock.MagicMock()
        resource_mock.list.return_value = [mock.MagicMock(id='e01df65a')]
        with self.assertRaises(AssertionError):
            openstack_utils.resource_removed(resource_mock, 'e01df65a')

    def test_delete_resource(self):
        resource_mock = mock.MagicMock()
        self.patch_object(openstack_utils, "resource_removed")
        openstack_utils.delete_resource(resource_mock, 'e01df65a')
        resource_mock.delete.assert_called_once_with('e01df65a')
        self.resource_removed.assert_called_once_with(
            resource_mock,
            'e01df65a',
            'resource')

    def test_delete_image(self):
        self.patch_object(openstack_utils, "delete_resource")
        glance_mock = mock.MagicMock()
        openstack_utils.delete_image(glance_mock, 'b46c2d83')
        self.delete_resource.assert_called_once_with(
            glance_mock.images,
            'b46c2d83',
            msg="glance image")

    def test_upload_image_to_glance(self):
        self.patch_object(openstack_utils, "resource_reaches_status")
        glance_mock = mock.MagicMock()
        image_mock = mock.MagicMock(id='9d1125af')
        glance_mock.images.create.return_value = image_mock
        m = mock.mock_open()
        with mock.patch('zaza.utilities.openstack.open', m, create=False) as f:
            openstack_utils.upload_image_to_glance(
                glance_mock,
                '/tmp/im1.img',
                'bob')
            glance_mock.images.create.assert_called_once_with(
                name='bob',
                disk_format='qcow2',
                visibility='public',
                container_format='bare')
            glance_mock.images.upload.assert_called_once_with(
                '9d1125af',
                f(),
            )
            self.resource_reaches_status.assert_called_once_with(
                glance_mock.images,
                '9d1125af',
                expected_status='active',
                msg='Image status wait')

    def test_create_image_use_tempdir(self):
        glance_mock = mock.MagicMock()
        self.patch_object(openstack_utils.os.path, "exists")
        self.patch_object(openstack_utils, "download_image")
        self.patch_object(openstack_utils, "upload_image_to_glance")
        self.patch_object(openstack_utils.tempfile, "gettempdir")
        self.gettempdir.return_value = "wibbly"
        openstack_utils.create_image(
            glance_mock,
            'http://cirros/c.img',
            'bob')
        self.exists.return_value = False
        self.download_image.assert_called_once_with(
            'http://cirros/c.img',
            'wibbly/c.img')
        self.upload_image_to_glance.assert_called_once_with(
            glance_mock,
            'wibbly/c.img',
            'bob')

    def test_create_image_pass_directory(self):
        glance_mock = mock.MagicMock()
        self.patch_object(openstack_utils.os.path, "exists")
        self.patch_object(openstack_utils, "download_image")
        self.patch_object(openstack_utils, "upload_image_to_glance")
        self.patch_object(openstack_utils.tempfile, "gettempdir")
        openstack_utils.create_image(
            glance_mock,
            'http://cirros/c.img',
            'bob',
            'tests')
        self.exists.return_value = False
        self.download_image.assert_called_once_with(
            'http://cirros/c.img',
            'tests/c.img')
        self.upload_image_to_glance.assert_called_once_with(
            glance_mock,
            'tests/c.img',
            'bob')
        self.gettempdir.assert_not_called()

    def test_create_ssh_key(self):
        nova_mock = mock.MagicMock()
        nova_mock.keypairs.findall.return_value = []
        openstack_utils.create_ssh_key(
            nova_mock,
            'mykeys')
        nova_mock.keypairs.create.assert_called_once_with(name='mykeys')

    def test_create_ssh_key_existing(self):
        nova_mock = mock.MagicMock()
        nova_mock.keypairs.findall.return_value = ['akey']
        self.assertEqual(
            openstack_utils.create_ssh_key(
                nova_mock,
                'mykeys'),
            'akey')
        self.assertFalse(nova_mock.keypairs.create.called)

    def test_create_ssh_key_existing_replace(self):
        nova_mock = mock.MagicMock()
        nova_mock.keypairs.findall.return_value = ['key1']
        openstack_utils.create_ssh_key(
            nova_mock,
            'mykeys',
            replace=True),
        nova_mock.keypairs.delete.assert_called_once_with('key1')
        nova_mock.keypairs.create.assert_called_once_with(name='mykeys')

    def test_get_private_key_file(self):
        self.assertEqual(
            openstack_utils.get_private_key_file('mykeys'),
            'tests/id_rsa_mykeys')

    def test_write_private_key(self):
        m = mock.mock_open()
        with mock.patch('zaza.utilities.openstack.open', m, create=False):
            openstack_utils.write_private_key('mykeys', 'keycontents')
        m.assert_called_once_with('tests/id_rsa_mykeys', 'w')
        handle = m()
        handle.write.assert_called_once_with('keycontents')

    def test_get_private_key(self):
        self.patch_object(openstack_utils.os.path, "isfile",
                          return_value=True)
        m = mock.mock_open(read_data='myprivkey')
        with mock.patch('zaza.utilities.openstack.open', m, create=True):
            self.assertEqual(
                openstack_utils.get_private_key('mykeys'),
                'myprivkey')

    def test_get_private_key_file_missing(self):
        self.patch_object(openstack_utils.os.path, "isfile",
                          return_value=False)
        self.assertIsNone(openstack_utils.get_private_key('mykeys'))

    def test_get_public_key(self):
        key_mock = mock.MagicMock(public_key='mypubkey')
        nova_mock = mock.MagicMock()
        nova_mock.keypairs.findall.return_value = [key_mock]
        self.assertEqual(
            openstack_utils.get_public_key(nova_mock, 'mykeys'),
            'mypubkey')

    def test_valid_key_exists(self):
        nova_mock = mock.MagicMock()
        self.patch_object(openstack_utils, 'get_public_key',
                          return_value='pubkey')
        self.patch_object(openstack_utils, 'get_private_key',
                          return_value='privkey')
        self.patch_object(openstack_utils.cert, 'is_keys_valid',
                          return_value=True)
        self.assertTrue(openstack_utils.valid_key_exists(nova_mock, 'mykeys'))
        self.get_public_key.assert_called_once_with(nova_mock, 'mykeys')
        self.get_private_key.assert_called_once_with('mykeys')
        self.is_keys_valid.assert_called_once_with('pubkey', 'privkey')

    def test_valid_key_exists_missing(self):
        nova_mock = mock.MagicMock()
        self.patch_object(openstack_utils, 'get_public_key',
                          return_value='pubkey')
        self.patch_object(openstack_utils, 'get_private_key',
                          return_value=None)
        self.patch_object(openstack_utils.cert, 'is_keys_valid',
                          return_value=True)
        self.assertFalse(openstack_utils.valid_key_exists(nova_mock, 'mykeys'))
        self.get_public_key.assert_called_once_with(nova_mock, 'mykeys')
        self.get_private_key.assert_called_once_with('mykeys')

    def test_get_ports_from_device_id(self):
        port_mock = {'device_id': 'dev1'}
        neutron_mock = mock.MagicMock()
        neutron_mock.list_ports.return_value = {
            'ports': [port_mock]}
        self.assertEqual(
            openstack_utils.get_ports_from_device_id(
                neutron_mock,
                'dev1'),
            [port_mock])

    def test_get_ports_from_device_id_no_match(self):
        port_mock = {'device_id': 'dev2'}
        neutron_mock = mock.MagicMock()
        neutron_mock.list_ports.return_value = {
            'ports': [port_mock]}
        self.assertEqual(
            openstack_utils.get_ports_from_device_id(
                neutron_mock,
                'dev1'),
            [])

    def test_ping_response(self):
        self.patch_object(openstack_utils.subprocess, 'check_call')
        openstack_utils.ping_response('10.0.0.10')
        self.check_call.assert_called_once_with(
            ['ping', '-c', '1', '-W', '1', '10.0.0.10'], stdout=-3)

    def test_ping_response_fail(self):
        openstack_utils.ping_response.retry.wait = \
            tenacity.wait_none()
        self.patch_object(openstack_utils.subprocess, 'check_call')
        self.check_call.side_effect = Exception()
        with self.assertRaises(Exception):
            openstack_utils.ping_response('10.0.0.10')

    def test_ssh_test(self):
        paramiko_mock = mock.MagicMock()
        self.patch_object(openstack_utils.paramiko, 'SSHClient',
                          return_value=paramiko_mock)
        self.patch_object(openstack_utils.paramiko, 'AutoAddPolicy',
                          return_value='some_policy')
        stdout = io.StringIO("myvm")

        paramiko_mock.exec_command.return_value = ('stdin', stdout, 'stderr')
        openstack_utils.ssh_test(
            'bob',
            '10.0.0.10',
            'myvm',
            password='reallyhardpassord')
        paramiko_mock.connect.assert_called_once_with(
            '10.0.0.10',
            password='reallyhardpassord',
            username='bob')

    def test_ssh_test_wrong_server(self):
        paramiko_mock = mock.MagicMock()
        self.patch_object(openstack_utils.paramiko, 'SSHClient',
                          return_value=paramiko_mock)
        self.patch_object(openstack_utils.paramiko, 'AutoAddPolicy',
                          return_value='some_policy')
        stdout = io.StringIO("anothervm")

        paramiko_mock.exec_command.return_value = ('stdin', stdout, 'stderr')
        with self.assertRaises(exceptions.SSHFailed):
            openstack_utils.ssh_test(
                'bob',
                '10.0.0.10',
                'myvm',
                password='reallyhardpassord')
        paramiko_mock.connect.assert_called_once_with(
            '10.0.0.10',
            password='reallyhardpassord',
            username='bob')

    def test_ssh_test_key_auth(self):
        paramiko_mock = mock.MagicMock()
        self.patch_object(openstack_utils.paramiko, 'SSHClient',
                          return_value=paramiko_mock)
        self.patch_object(openstack_utils.paramiko, 'AutoAddPolicy',
                          return_value='some_policy')
        self.patch_object(openstack_utils.paramiko.RSAKey, 'from_private_key',
                          return_value='akey')
        stdout = io.StringIO("myvm")

        paramiko_mock.exec_command.return_value = ('stdin', stdout, 'stderr')
        openstack_utils.ssh_test(
            'bob',
            '10.0.0.10',
            'myvm',
            privkey='myprivkey')
        paramiko_mock.connect.assert_called_once_with(
            '10.0.0.10',
            password='',
            pkey='akey',
            username='bob')

    def test_neutron_agent_appears(self):
        self.assertEqual(
            openstack_utils.neutron_agent_appears(self.neutronclient,
                                                  'neutron-bgp-dragent'),
            self.agents)

    def test_neutron_agent_appears_not(self):
        _neutronclient = copy.deepcopy(self.neutronclient)
        _neutronclient.list_agents.return_value = {'agents': []}
        openstack_utils.neutron_agent_appears.retry.stop = \
            tenacity.stop_after_attempt(1)
        with self.assertRaises(exceptions.NeutronAgentMissing):
            openstack_utils.neutron_agent_appears(_neutronclient,
                                                  'non-existent')

    def test_neutron_bgp_speaker_appears_on_agent(self):
        openstack_utils.neutron_bgp_speaker_appears_on_agent.retry.stop = \
            tenacity.stop_after_attempt(1)
        self.assertEqual(
            openstack_utils.neutron_bgp_speaker_appears_on_agent(
                self.neutronclient, 'FAKE_AGENT_ID'),
            self.bgp_speakers)

    def test_neutron_bgp_speaker_appears_not_on_agent(self):
        _neutronclient = copy.deepcopy(self.neutronclient)
        _neutronclient.list_bgp_speaker_on_dragent.return_value = {
            'bgp_speakers': []}
        openstack_utils.neutron_bgp_speaker_appears_on_agent.retry.stop = \
            tenacity.stop_after_attempt(1)
        with self.assertRaises(exceptions.NeutronBGPSpeakerMissing):
            openstack_utils.neutron_bgp_speaker_appears_on_agent(
                _neutronclient, 'FAKE_AGENT_ID')

    def test_get_current_openstack_release_pair(self):
        self.patch(
            'zaza.utilities.openstack.get_current_os_versions',
            new_callable=mock.MagicMock(),
            name='_get_os_version'
        )
        self.patch(
            'zaza.utilities.juju.get_machines_for_application',
            new_callable=mock.MagicMock(),
            name='_get_machines'
        )
        self.patch(
            'zaza.utilities.juju.get_machine_series',
            new_callable=mock.MagicMock(),
            name='_get_machine_series'
        )

        # No machine returned
        self._get_machines.return_value = []
        with self.assertRaises(exceptions.ApplicationNotFound):
            openstack_utils.get_current_os_release_pair()

        # No series returned
        self._get_machines.return_value = ['6']
        self._get_machine_series.return_value = None
        with self.assertRaises(exceptions.SeriesNotFound):
            openstack_utils.get_current_os_release_pair()

        # No OS Version returned
        self._get_machine_series.return_value = 'xenial'
        self._get_os_version.return_value = {}
        with self.assertRaises(exceptions.OSVersionNotFound):
            openstack_utils.get_current_os_release_pair()

        # Normal scenario, argument passed
        self._get_os_version.return_value = {'keystone': 'mitaka'}
        expected = 'xenial_mitaka'
        result = openstack_utils.get_current_os_release_pair('keystone')
        self.assertEqual(expected, result)

        # Normal scenario, default value used
        self._get_os_version.return_value = {'keystone': 'mitaka'}
        expected = 'xenial_mitaka'
        result = openstack_utils.get_current_os_release_pair()
        self.assertEqual(expected, result)

    def test_get_openstack_release(self):
        self.patch(
            'zaza.utilities.openstack.get_current_os_release_pair',
            new_callable=mock.MagicMock(),
            name='_get_os_rel_pair'
        )

        # Bad release pair
        release_pair = 'bad'
        with self.assertRaises(exceptions.ReleasePairNotFound):
            openstack_utils.get_os_release(release_pair)

        # Normal scenario
        expected = 4
        result = openstack_utils.get_os_release('xenial_mitaka')
        self.assertEqual(expected, result)

        # Normal scenario with current release pair
        self._get_os_rel_pair.return_value = 'xenial_mitaka'
        expected = 4
        result = openstack_utils.get_os_release()
        self.assertEqual(expected, result)

        # We can compare releases xenial_queens > xenial_mitaka
        xenial_queens = openstack_utils.get_os_release('xenial_queens')
        xenial_mitaka = openstack_utils.get_os_release('xenial_mitaka')
        release_comp = xenial_queens > xenial_mitaka
        self.assertTrue(release_comp)

    def test_get_keystone_api_version(self):
        self.patch_object(openstack_utils, "get_current_os_versions")
        self.patch_object(openstack_utils, "get_application_config_option")

        self.get_current_os_versions.return_value = {"keystone": "liberty"}
        self.get_application_config_option.return_value = None
        self.assertEqual(openstack_utils.get_keystone_api_version(), 2)

        self.get_application_config_option.return_value = "3"
        self.assertEqual(openstack_utils.get_keystone_api_version(), 3)

        self.get_current_os_versions.return_value = {"keystone": "queens"}
        self.get_application_config_option.return_value = None
        self.assertEqual(openstack_utils.get_keystone_api_version(), 3)

    def test_get_project_id(self):
        # No domain
        self.patch_object(openstack_utils, "get_keystone_api_version")
        self.get_keystone_api_version.return_value = 2
        ksclient = mock.MagicMock()
        project_id = "project-uuid"
        project_name = "myproject"
        project = mock.MagicMock()
        project._info = {"name": project_name, "id": project_id}
        ksclient.projects.list.return_value = [project]
        self.assertEqual(
            openstack_utils.get_project_id(ksclient, project_name),
            project_id)
        ksclient.projects.list.assert_called_once_with(domain=None)
        ksclient.domains.list.assert_not_called()

        # With domain
        ksclient.reset_mock()
        domain_name = "mydomain"
        domain_id = "domain-uuid"
        domain = mock.MagicMock()
        domain.id = domain_id
        ksclient.domains.list.return_value = [domain]
        self.assertEqual(
            openstack_utils.get_project_id(
                ksclient, project_name, domain_name=domain_name), project_id)
        ksclient.domains.list.assert_called_once_with(name=domain_name)
        ksclient.projects.list.assert_called_once_with(domain=domain_id)

    def test_wait_for_server_migration(self):
        openstack_utils.wait_for_server_migration.retry.stop = \
            tenacity.stop_after_attempt(1)
        novaclient = mock.MagicMock()
        servermock = mock.MagicMock()
        setattr(servermock, 'OS-EXT-SRV-ATTR:host', 'newhypervisor')
        servermock.status = 'ACTIVE'
        novaclient.servers.find.return_value = servermock
        # Implicit assertion that exception is not raised.
        openstack_utils.wait_for_server_migration(
            novaclient,
            'myvm',
            'org-hypervisor')

    def test_wait_for_server_migration_fail_no_host_change(self):
        openstack_utils.wait_for_server_migration.retry.stop = \
            tenacity.stop_after_attempt(1)
        novaclient = mock.MagicMock()
        servermock = mock.MagicMock()
        setattr(servermock, 'OS-EXT-SRV-ATTR:host', 'org-hypervisor')
        servermock.status = 'ACTIVE'
        novaclient.servers.find.return_value = servermock
        with self.assertRaises(exceptions.NovaGuestMigrationFailed):
            openstack_utils.wait_for_server_migration(
                novaclient,
                'myvm',
                'org-hypervisor')

    def test_wait_for_server_migration_fail_not_active(self):
        openstack_utils.wait_for_server_migration.retry.stop = \
            tenacity.stop_after_attempt(1)
        novaclient = mock.MagicMock()
        servermock = mock.MagicMock()
        setattr(servermock, 'OS-EXT-SRV-ATTR:host', 'newhypervisor')
        servermock.status = 'NOTACTIVE'
        novaclient.servers.find.return_value = servermock
        with self.assertRaises(exceptions.NovaGuestMigrationFailed):
            openstack_utils.wait_for_server_migration(
                novaclient,
                'myvm',
                'org-hypervisor')

    def test_wait_for_server_update_and_active(self):
        openstack_utils.wait_for_server_migration.retry.stop = \
            tenacity.stop_after_attempt(1)
        novaclient = mock.MagicMock()
        servermock = mock.MagicMock()
        servermock.updated = '2019-03-07T13:41:58Z'
        servermock.status = 'ACTIVE'
        novaclient.servers.find.return_value = servermock
        # Implicit assertion that exception is not raised.
        openstack_utils.wait_for_server_update_and_active(
            novaclient,
            'myvm',
            datetime.datetime.strptime(
                '2019-03-07T13:40:58Z',
                '%Y-%m-%dT%H:%M:%SZ'))

    def test_wait_for_server_update_and_active_fail_no_meeta_update(self):
        openstack_utils.wait_for_server_update_and_active.retry.stop = \
            tenacity.stop_after_attempt(1)
        novaclient = mock.MagicMock()
        servermock = mock.MagicMock()
        servermock.updated = '2019-03-07T13:41:58Z'
        servermock.status = 'ACTIVE'
        novaclient.servers.find.return_value = servermock
        with self.assertRaises(exceptions.NovaGuestRestartFailed):
            openstack_utils.wait_for_server_update_and_active(
                novaclient,
                'myvm',
                datetime.datetime.strptime(
                    '2019-03-07T13:41:58Z',
                    '%Y-%m-%dT%H:%M:%SZ'))

    def test_wait_for_server_update_and_active_fail_not_active(self):
        openstack_utils.wait_for_server_update_and_active.retry.stop = \
            tenacity.stop_after_attempt(1)
        novaclient = mock.MagicMock()
        servermock = mock.MagicMock()
        servermock.updated = '2019-03-07T13:41:58Z'
        servermock.status = 'NOTACTIVE'
        novaclient.servers.find.return_value = servermock
        with self.assertRaises(exceptions.NovaGuestRestartFailed):
            openstack_utils.wait_for_server_update_and_active(
                novaclient,
                'myvm',
                datetime.datetime.strptime(
                    '2019-03-07T13:40:58Z',
                    '%Y-%m-%dT%H:%M:%SZ'))

    def test_enable_all_nova_services(self):
        novaclient = mock.MagicMock()
        svc_mock1 = mock.MagicMock()
        svc_mock1.status = 'disabled'
        svc_mock1.binary = 'nova-compute'
        svc_mock1.host = 'juju-bb659c-zaza-ad7c662d7f1d-13'
        svc_mock2 = mock.MagicMock()
        svc_mock2.status = 'enabled'
        svc_mock2.binary = 'nova-compute'
        svc_mock2.host = 'juju-bb659c-zaza-ad7c662d7f1d-14'
        svc_mock3 = mock.MagicMock()
        svc_mock3.status = 'disabled'
        svc_mock3.binary = 'nova-compute'
        svc_mock3.host = 'juju-bb659c-zaza-ad7c662d7f1d-15'
        novaclient.services.list.return_value = [
            svc_mock1,
            svc_mock2,
            svc_mock3]
        openstack_utils.enable_all_nova_services(novaclient)
        expected_calls = [
            mock.call('juju-bb659c-zaza-ad7c662d7f1d-13', 'nova-compute'),
            mock.call('juju-bb659c-zaza-ad7c662d7f1d-15', 'nova-compute')]
        novaclient.services.enable.assert_has_calls(expected_calls)

    def test_get_hypervisor_for_guest(self):
        novaclient = mock.MagicMock()
        servermock = mock.MagicMock()
        setattr(servermock, 'OS-EXT-SRV-ATTR:host', 'newhypervisor')
        novaclient.servers.find.return_value = servermock
        self.assertEqual(
            openstack_utils.get_hypervisor_for_guest(novaclient, 'vmname'),
            'newhypervisor')

    def test_get_keystone_session(self):
        self.patch_object(openstack_utils, "session")
        self.patch_object(openstack_utils, "v2")
        _auth = mock.MagicMock()
        self.v2.Password.return_value = _auth
        _openrc = {
            "OS_AUTH_URL": "https://keystone:5000",
            "OS_USERNAME": "myuser",
            "OS_PASSWORD": "pass",
            "OS_TENANT_NAME": "tenant",
        }
        openstack_utils.get_keystone_session(_openrc)
        self.session.Session.assert_called_once_with(auth=_auth, verify=None)

    def test_get_keystone_session_tls(self):
        self.patch_object(openstack_utils, "session")
        self.patch_object(openstack_utils, "v2")
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
        openstack_utils.get_keystone_session(_openrc)
        self.session.Session.assert_called_once_with(
            auth=_auth, verify=_cacert)
