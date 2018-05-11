import copy
import mock
import unit_tests.utils as ut_utils
from zaza.utilities import openstack as openstack_utils


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

    def test_get_overcloud_keystone_session(self):
        self.patch_object(openstack_utils, "get_keystone_session")
        self.patch_object(openstack_utils, "get_keystone_scope")
        self.patch_object(openstack_utils, "get_overcloud_auth")
        _auth = "FAKE_AUTH"
        _scope = "PROJECT"
        self.get_keystone_scope.return_value = _scope
        self.get_overcloud_auth.return_value = _auth

        openstack_utils.get_overcloud_keystone_session()
        self.get_keystone_session.assert_called_once_with(_auth, scope=_scope)

    def test_get_undercloud_keystone_session(self):
        self.patch_object(openstack_utils, "get_keystone_session")
        self.patch_object(openstack_utils, "get_keystone_scope")
        self.patch_object(openstack_utils, "get_undercloud_auth")
        _auth = "FAKE_AUTH"
        _scope = "PROJECT"
        self.get_keystone_scope.return_value = _scope
        self.get_undercloud_auth.return_value = _auth

        openstack_utils.get_undercloud_keystone_session()
        self.get_keystone_session.assert_called_once_with(_auth, scope=_scope)
