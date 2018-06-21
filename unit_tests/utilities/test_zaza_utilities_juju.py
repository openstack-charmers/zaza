"""Module containing unit tests for zaza.utilities.juju."""
import mock
import unit_tests.utils as ut_utils
from zaza.utilities import juju as juju_utils


class TestJujuUtils(ut_utils.BaseTestCase):
    """Unit tests for zaza.utilities.juju."""

    def setUp(self):
        """Run setup for zaza.utilities.juju tests."""
        super(TestJujuUtils, self).setUp()

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
        self.patch_object(juju_utils, "model")
        self.model_name = "model-name"
        self.model.get_status.return_value = self.juju_status
        self.run_output = {"Code": "0", "Stderr": "", "Stdout": "RESULT"}
        self.error_run_output = {"Code": "1", "Stderr": "ERROR", "Stdout": ""}
        self.model.run_on_unit.return_value = self.run_output

        # Clouds
        self.cloud_name = "FakeCloudName"
        self.cloud_type = "FakeCloudType"
        self.clouds = {
            "clouds":
                {self.cloud_name:
                    {"type": self.cloud_type}}}

        # Controller
        self.patch_object(juju_utils, "controller")
        self.controller.get_cloud.return_value = self.cloud_name

    def test_get_application_status(self):
        """Test get_application_status."""
        self.patch_object(juju_utils, "get_full_juju_status")
        self.get_full_juju_status.return_value = self.juju_status

        # Full status juju object return
        self.assertEqual(
            juju_utils.get_application_status(), self.juju_status)
        self.get_full_juju_status.assert_called_once()

        # Application only dictionary return
        self.assertEqual(
            juju_utils.get_application_status(application=self.application),
            self.application_data)

        # Unit no application dictionary return
        self.assertEqual(
            juju_utils.get_application_status(unit=self.unit),
            self.unit_data)

    def test_get_cloud_configs(self):
        """Test get_cloud_configs."""
        self.patch_object(juju_utils.Path, "home")
        self.patch_object(juju_utils.generic_utils, "get_yaml_config")
        self.get_yaml_config.return_value = self.clouds

        # All the cloud configs
        self.assertEqual(juju_utils.get_cloud_configs(), self.clouds)

        # With cloud specified
        self.assertEqual(juju_utils.get_cloud_configs(self.cloud_name),
                         self.clouds["clouds"][self.cloud_name])

    def test_get_full_juju_status(self):
        """Test get_full_juju_status."""
        self.assertEqual(juju_utils.get_full_juju_status(), self.juju_status)
        self.model.get_status.assert_called_once_with()

    def test_get_machines_for_application(self):
        """Test get_machines_for_application."""
        self.patch_object(juju_utils, "get_application_status")
        self.get_application_status.return_value = self.application_data

        # Machine data
        self.assertEqual(
            juju_utils.get_machines_for_application(self.application),
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
            juju_utils.get_machines_for_application(
                self.subordinate_application),
            [self.machine])

    def test_get_machine_status(self):
        """Test get_machine_status for all data and a specific key."""
        self.patch_object(juju_utils, "get_full_juju_status")
        self.get_full_juju_status.return_value = self.juju_status

        # All machine data
        self.assertEqual(
            juju_utils.get_machine_status(self.machine),
            self.machine_data)
        self.get_full_juju_status.assert_called_once()

        # Request a specific key
        self.assertEqual(
            juju_utils.get_machine_status(self.machine, self.key),
            self.key_data)

    def test_get_machine_uuids_for_application(self):
        """Test get_machine_uuids_for_application."""
        self.patch_object(juju_utils, "get_machines_for_application")
        self.get_machines_for_application.return_value = [self.machine]

        self.assertEqual(
            juju_utils.get_machine_uuids_for_application(self.application),
            [self.machine_data.get("instance-id")])
        self.get_machines_for_application.assert_called_once_with(
            self.application)

    def test_get_provider_type(self):
        """Test get_provider_type."""
        self.patch_object(juju_utils, "get_cloud_configs")
        self.get_cloud_configs.return_value = {"type": self.cloud_type}
        self.assertEqual(juju_utils.get_provider_type(),
                         self.cloud_type)
        self.get_cloud_configs.assert_called_once_with(self.cloud_name)

    def test_remote_run(self):
        """Test remote_run."""
        _cmd = "do the thing"

        # Success
        self.assertEqual(juju_utils.remote_run(self.unit, _cmd),
                         self.run_output["Stdout"])
        self.model.run_on_unit.assert_called_once_with(
            self.unit, _cmd, timeout=None)

        # Non-fatal failure
        self.model.run_on_unit.return_value = self.error_run_output
        self.assertEqual(juju_utils.remote_run(self.unit, _cmd, fatal=False),
                         self.error_run_output["Stderr"])

        # Fatal failure
        with self.assertRaises(Exception):
            juju_utils.remote_run(self.unit, _cmd, fatal=True)

    def test_get_unit_names(self):
        """Test _get_unit_names."""
        self.patch('zaza.model.get_first_unit_name', new_callable=mock.Mock(),
                   name='_get_first_unit_name')
        juju_utils._get_unit_names(['aunit/0', 'otherunit/0'])
        self.assertFalse(self._get_first_unit_name.called)

    def test_get_unit_names_called_with_application_name(self):
        """Test get_first_unit_name."""
        self.patch_object(juju_utils, 'model')
        juju_utils._get_unit_names(['aunit', 'otherunit/0'])
        self.model.get_first_unit_name.assert_called()

    def test_get_relation_from_unit(self):
        """Test get_relation_from_unit."""
        self.patch_object(juju_utils, '_get_unit_names')
        self.patch_object(juju_utils, 'yaml')
        self.patch_object(juju_utils, 'model')
        self._get_unit_names.return_value = ['aunit/0', 'otherunit/0']
        data = {'foo': 'bar'}
        self.model.get_relation_id.return_value = 42
        self.model.run_on_unit.return_value = {'Code': 0, 'Stdout': str(data)}
        juju_utils.get_relation_from_unit('aunit/0', 'otherunit/0',
                                          'arelation')
        self.model.run_on_unit.assert_called_with(
            'aunit/0',
            'relation-get --format=yaml -r "42" - "otherunit/0"')
        self.yaml.load.assert_called_with(str(data))

    def test_get_relation_from_unit_fails(self):
        """Test get_relation_from_unit raises exception on error."""
        self.patch_object(juju_utils, '_get_unit_names')
        self.patch_object(juju_utils, 'yaml')
        self.patch_object(juju_utils, 'model')
        self._get_unit_names.return_value = ['aunit/0', 'otherunit/0']
        self.model.get_relation_id.return_value = 42
        self.model.run_on_unit.return_value = {'Code': 1, 'Stderr': 'ERROR'}
        with self.assertRaises(Exception):
            juju_utils.get_relation_from_unit('aunit/0', 'otherunit/0',
                                              'arelation')
        self.model.run_on_unit.assert_called_with(
            'aunit/0',
            'relation-get --format=yaml -r "42" - "otherunit/0"')
        self.assertFalse(self.yaml.load.called)
