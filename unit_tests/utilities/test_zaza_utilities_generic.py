import mock
import unit_tests.utils as ut_utils
from zaza.utilities import generic as generic_utils


class TestGenericUtils(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestGenericUtils, self).setUp()

    def test_dict_to_yaml(self):
        _dict_data = {"key": "value"}
        _str_data = "key: value\n"
        self.assertEqual(generic_utils.dict_to_yaml(_dict_data),
                         _str_data)

    def test_get_network_config(self):
        self.patch_object(generic_utils.os.path, "exists")
        self.patch_object(generic_utils, "get_yaml_config")
        self.patch_object(generic_utils, "get_undercloud_env_vars")
        net_topology = "topo"
        _data = {net_topology: {"network": "DATA"}}
        self.get_yaml_config.return_value = _data

        # YAML file does not exist
        self.exists.return_value = False
        with self.assertRaises(Exception):
            generic_utils.get_network_config(net_topology)

        # No environmental variables
        self.exists.return_value = True
        self.assertEqual(
            generic_utils.get_network_config(net_topology,
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
            generic_utils.get_network_config(net_topology),
            _data[net_topology])
        self.get_undercloud_env_vars.assert_called_once_with()

    def test_get_pkg_version(self):
        self.patch_object(generic_utils.model, "get_units")
        self.patch_object(generic_utils.lifecycle_utils, "get_juju_model")
        self.patch_object(generic_utils.juju_utils, "remote_run")
        _pkg = "os-thingy"
        _version = "2:27.0.0-0ubuntu1~cloud0"
        _dpkg_output = ("ii {} {} all OpenStack thingy\n"
                        .format(_pkg, _version))
        self.remote_run.return_value = _dpkg_output
        _model_name = "model-name"
        self.get_juju_model.return_value = _model_name
        _unit1 = mock.MagicMock()
        _unit1.entity_id = "os-thingy/7"
        _unit2 = mock.MagicMock()
        _unit2.entity_id = "os-thingy/12"
        _units = [_unit1, _unit2]
        self.get_units.return_value = _units

        # Matching
        self.assertEqual(generic_utils.get_pkg_version(_pkg, _pkg),
                         _version)

        # Mismatched
        _different_dpkg_output = ("ii {} {} all OpenStack thingy\n"
                                  .format(_pkg, "DIFFERENT"))
        self.remote_run.side_effect = [_dpkg_output, _different_dpkg_output]
        with self.assertRaises(Exception):
            generic_utils.get_pkg_version(_pkg, _pkg)

    def test_get_undercloud_env_vars(self):
        self.patch_object(generic_utils.os.environ, "get")

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
        self.assertEqual(generic_utils.get_undercloud_env_vars(),
                         _expected_result)

        # Overriding configure.network named variables
        _override = {"start_floating_ip": "10.100.50.0",
                     "end_floating_ip": "10.100.50.254",
                     "default_gateway": "10.100.0.1",
                     "external_net_cidr": "10.100.0.0/16"}
        _env.update(_override)
        _expected_result.update(_override)
        self.assertEqual(generic_utils.get_undercloud_env_vars(),
                         _expected_result)

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

        self.assertEqual(generic_utils.get_yaml_config(_filename),
                         _yaml_dict)
        self._open.assert_called_once_with(_filename, "r")
