import mock
import unit_tests.utils as ut_utils
from zaza.utilities import _local_utils


class TestLocalUtils(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestLocalUtils, self).setUp()

        # Juju Status Object and data
        self.key = "instance-id"
        self.key_data = "machine-uuid"
        self.machine = "1"
        self.machine_data = {self.key: self.key_data}
        self.unit = "app/1"
        self.unit_data = {"machine": self.machine}
        self.application = "app"
        self.application_data = {"units": {self.unit: self.unit_data}}
        self.subordinate_application = "subordinate_application"
        self.subordinate_application_data = {
            "subordinate-to": [self.application]}
        self.juju_status = mock.MagicMock()
        self.juju_status.name = "juju_status_object"
        self.juju_status.applications.get.return_value = self.application_data
        self.juju_status.machines.get.return_value = self.machine_data

        # Model
        self.patch_object(_local_utils, "model")
        self.patch_object(_local_utils.lifecycle_utils, "get_juju_model")
        self.model_name = "model-name"
        self.get_juju_model.return_value = self.model_name
        self.model.get_status.return_value = self.juju_status

    def test_get_yaml_config(self):
        self.patch("builtins.open",
                   new_callable=mock.mock_open(),
                   name="_open")
        _yaml = "data: somedata"
        _yaml_dict = {"data": "somedata"}
        _filename = "filename"
        _fileobj = mock.MagicMock()
        _fileobj.read.return_value = _yaml
        self._open.return_value = _fileobj

        self.assertEqual(_local_utils.get_yaml_config(_filename),
                         _yaml_dict)
        self._open.assert_called_once_with(_filename, "r")

    def test_get_undercloud_env_vars(self):
        self.patch_object(_local_utils.os.environ, "get")

        def _get_env(key):
            return _env.get(key)
        self.get.side_effect = _get_env

        # OSCI backward compatible env vars
        _env = {"NET_ID": "netid",
                "NAMESERVER": "10.0.0.10",
                "GATEWAY": "10.0.0.1",
                "CIDR_EXT": "10.0.0.0/24",
                "FIP_RANGE": "10.0.200.0:10.0.200.254"}
        _expected_result = {}
        _expected_result["net_id"] = _env["NET_ID"]
        _expected_result["external_dns"] = _env["NAMESERVER"]
        _expected_result["default_gateway"] = _env["GATEWAY"]
        _expected_result["external_net_cidr"] = _env["CIDR_EXT"]
        _expected_result["start_floating_ip"] = _env["FIP_RANGE"].split(":")[0]
        _expected_result["end_floating_ip"] = _env["FIP_RANGE"].split(":")[1]
        self.assertEqual(_local_utils.get_undercloud_env_vars(),
                         _expected_result)

        # Overriding configure.network named variables
        _override = {"start_floating_ip": "10.100.50.0",
                     "end_floating_ip": "10.100.50.254",
                     "default_gateway": "10.100.0.1",
                     "external_net_cidr": "10.100.0.0/16"}
        _env.update(_override)
        _expected_result.update(_override)
        self.assertEqual(_local_utils.get_undercloud_env_vars(),
                         _expected_result)

    def test_get_network_config(self):
        self.patch_object(_local_utils.os.path, "exists")
        self.patch_object(_local_utils, "get_yaml_config")
        self.patch_object(_local_utils, "get_undercloud_env_vars")
        net_topology = "topo"
        _data = {net_topology: {"network": "DATA"}}
        self.get_yaml_config.return_value = _data

        # YAML file does not exist
        self.exists.return_value = False
        with self.assertRaises(Exception):
            _local_utils.get_network_config(net_topology)

        # No environmental variables
        self.exists.return_value = True
        self.assertEqual(
            _local_utils.get_network_config(net_topology,
                                            ignore_env_vars=True),
            _data[net_topology])
        self.get_yaml_config.assert_called_once_with("network.yaml")
        self.get_undercloud_env_vars.assert_not_called()

        # Update with environmental variables
        _more_data = {"network": "NEW",
                      "other": "DATA"}
        self.get_undercloud_env_vars.return_value = _more_data
        _data[net_topology].update(_more_data)
        self.assertEqual(
            _local_utils.get_network_config(net_topology),
            _data[net_topology])
        self.get_undercloud_env_vars.assert_called_once_with()

    def test_get_full_juju_status(self):
        self.assertEqual(_local_utils.get_full_juju_status(), self.juju_status)
        self.model.get_status.assert_called_once_with(self.model_name)

    def test_get_application_status(self):
        self.patch_object(_local_utils, "get_full_juju_status")
        self.get_full_juju_status.return_value = self.juju_status

        # Full status juju object return
        self.assertEqual(
            _local_utils.get_application_status(), self.juju_status)
        self.get_full_juju_status.assert_called_once()

        # Application only dictionary return
        self.assertEqual(
            _local_utils.get_application_status(application=self.application),
            self.application_data)

        # Unit no application dictionary return
        self.assertEqual(
            _local_utils.get_application_status(unit=self.unit),
            self.unit_data)

    def test_get_machine_status(self):
        self.patch_object(_local_utils, "get_full_juju_status")
        self.get_full_juju_status.return_value = self.juju_status

        # All machine data
        self.assertEqual(
            _local_utils.get_machine_status(self.machine),
            self.machine_data)
        self.get_full_juju_status.assert_called_once()

        # Request a specific key
        self.assertEqual(
            _local_utils.get_machine_status(self.machine, self.key),
            self.key_data)

    def test_get_machines_for_application(self):
        self.patch_object(_local_utils, "get_application_status")
        self.get_application_status.return_value = self.application_data

        # Machine data
        self.assertEqual(
            _local_utils.get_machines_for_application(self.application),
            [self.machine])
        self.get_application_status.assert_called_once()

        # Subordinate application has no units
        def _get_application_status(application):
            _apps = {
                self.application: self.application_data,
                self.subordinate_application:
                    self.subordinate_application_data}
            return _apps[application]
        self.get_application_status.side_effect = _get_application_status

        self.assertEqual(
            _local_utils.get_machines_for_application(
                self.subordinate_application),
            [self.machine])

    def test_get_machine_uuids_for_application(self):
        self.patch_object(_local_utils, "get_machines_for_application")
        self.get_machines_for_application.return_value = [self.machine]

        self.assertEqual(
            _local_utils.get_machine_uuids_for_application(self.application),
            [self.machine_data.get("instance-id")])
        self.get_machines_for_application.assert_called_once_with(
            self.application)
