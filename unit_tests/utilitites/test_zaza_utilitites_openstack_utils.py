import mock
import unit_tests.utils as ut_utils
from zaza.utilities import openstack_utils


class TestOpenStackUtils(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestOpenStackUtils, self).setUp()
        self.port_name = 'port_name'
        self.net_uuid = 'uuid'
        self.port = {
            'port': {'id': 'port_id',
                     'name': self.port_name,
                     'network_id': self.net_uuid}}

        self.ports = {'ports': [self.port['port']]}
        self.floatingip = {
            'floatingip': {'id': 'floatingip_id',
                           'floating_network_id': self.net_uuid,
                           'port_id': 'port_id'}}

        self.floatingips = {'floatingips': [self.floatingip['floatingip']]}

        self.neutronclient = mock.MagicMock()
        self.neutronclient.list_ports.return_value = self.ports
        self.neutronclient.create_port.return_value = self.port

        self.neutronclient.list_floatingips.return_value = self.floatingips
        self.neutronclient.create_floatingip.return_value = self.floatingip
        self.ext_net = 'ext_net'
        self.private_net = 'private_net'

    def test_create_port(self):
        self.patch_object(openstack_utils, 'get_net_uuid')
        self.get_net_uuid.return_value = self.net_uuid

        # Already exists
        port = openstack_utils.create_port(
            self.neutronclient, self.port_name, self.private_net)
        self.assertEqual(port, self.port['port'])
        self.neutronclient.create_port.assert_not_called()

        # Does not yet exist
        self.neutronclient.list_ports.return_value = {'ports': []}
        self.port['port'].pop('id')
        port = openstack_utils.create_port(
            self.neutronclient, self.port_name, self.private_net)
        self.assertEqual(port, self.port['port'])
        self.neutronclient.create_port.assert_called_once_with(self.port)

    def test_create_floating_ip(self):
        self.patch_object(openstack_utils, 'get_net_uuid')
        self.get_net_uuid.return_value = self.net_uuid

        # Already exists
        floatingip = openstack_utils.create_floating_ip(
            self.neutronclient, self.ext_net, port=self.port['port'])
        self.assertEqual(floatingip, self.floatingip['floatingip'])
        self.neutronclient.create_floatingip.assert_not_called()

        # Does not yet exist
        self.neutronclient.list_floatingips.return_value = {'floatingips': []}
        self.floatingip['floatingip'].pop('id')
        floatingip = openstack_utils.create_floating_ip(
            self.neutronclient, self.private_net, port=self.port['port'])
        self.assertEqual(floatingip, self.floatingip['floatingip'])
        self.neutronclient.create_floatingip.assert_called_once_with(
            self.floatingip)
