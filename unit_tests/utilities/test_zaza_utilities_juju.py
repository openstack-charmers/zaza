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
from zaza.utilities import juju as juju_utils


class TestJujuUtils(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestJujuUtils, self).setUp()

        # Patch all subprocess calls
        self.patch(
            'zaza.utilities.juju.subprocess',
            new_callable=mock.MagicMock(),
            name='subprocess'
        )

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
        self.model.get_juju_model.return_value = self.model_name
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
        self.patch_object(juju_utils.Path, "home")
        self.patch_object(juju_utils.generic_utils, "get_yaml_config")
        self.get_yaml_config.return_value = self.clouds

        # All the cloud configs
        self.assertEqual(juju_utils.get_cloud_configs(), self.clouds)

        # With cloud specified
        self.assertEqual(juju_utils.get_cloud_configs(self.cloud_name),
                         self.clouds["clouds"][self.cloud_name])

    def test_get_full_juju_status(self):
        self.assertEqual(juju_utils.get_full_juju_status(), self.juju_status)
        self.model.get_status.assert_called_once_with()

    def test_get_machines_for_application(self):
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
        self.patch_object(juju_utils, "get_machines_for_application")
        self.get_machines_for_application.return_value = [self.machine]

        self.assertEqual(
            juju_utils.get_machine_uuids_for_application(self.application),
            [self.machine_data.get("instance-id")])
        self.get_machines_for_application.assert_called_once_with(
            self.application)

    def test_get_provider_type(self):
        self.patch_object(juju_utils, "get_cloud_configs")
        self.get_cloud_configs.return_value = {"type": self.cloud_type}
        self.assertEqual(juju_utils.get_provider_type(),
                         self.cloud_type)
        self.get_cloud_configs.assert_called_once_with(self.cloud_name)

    def test_remote_run(self):
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
        self.patch('zaza.model.get_first_unit_name', new_callable=mock.Mock(),
                   name='_get_first_unit_name')
        juju_utils._get_unit_names(['aunit/0', 'otherunit/0'])
        self.assertFalse(self._get_first_unit_name.called)

    def test_get_unit_names_called_with_application_name(self):
        self.patch_object(juju_utils, 'model')
        juju_utils._get_unit_names(['aunit', 'otherunit/0'])
        self.model.get_first_unit_name.assert_called()

    def test_get_relation_from_unit(self):
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

    def test_leader_get(self):
        self.patch_object(juju_utils, 'yaml')
        self.patch_object(juju_utils, 'model')
        data = {'foo': 'bar'}
        self.model.run_on_leader.return_value = {
            'Code': 0, 'Stdout': str(data)}
        juju_utils.leader_get('application')
        self.model.run_on_leader.assert_called_with(
            'application', 'leader-get --format=yaml ')
        self.yaml.load.assert_called_with(str(data))

    def test_leader_get_key(self):
        self.patch_object(juju_utils, 'yaml')
        self.patch_object(juju_utils, 'model')
        data = {'foo': 'bar'}
        self.model.run_on_leader.return_value = {
            'Code': 0, 'Stdout': data['foo']}
        juju_utils.leader_get('application', 'foo')
        self.model.run_on_leader.assert_called_with(
            'application', 'leader-get --format=yaml foo')
        self.yaml.load.assert_called_with(data['foo'])

    def test_leader_get_fails(self):
        self.patch_object(juju_utils, 'yaml')
        self.patch_object(juju_utils, 'model')
        self.model.run_on_leader.return_value = {
            'Code': 1, 'Stderr': 'ERROR'}
        with self.assertRaises(Exception):
            juju_utils.leader_get('application')
        self.model.run_on_leader.assert_called_with(
            'application', 'leader-get --format=yaml ')
        self.assertFalse(self.yaml.load.called)

    def test_get_machine_series(self):
        self.patch(
            'zaza.utilities.juju.get_machine_status',
            new_callable=mock.MagicMock(),
            name='_get_machine_status'
        )
        self._get_machine_status.return_value = 'xenial'
        expected = 'xenial'
        actual = juju_utils.get_machine_series('6')
        self._get_machine_status.assert_called_with(
            machine='6',
            key='series'
        )
        self.assertEqual(expected, actual)

    def test_prepare_series_upgrade(self):
        _machine_num = "1"
        _to_series = "bionic"
        juju_utils.prepare_series_upgrade(_machine_num, to_series=_to_series)
        self.subprocess.check_call.assert_called_once_with(
            ["juju", "upgrade-series", "-m", self.model_name,
             "prepare", _machine_num, _to_series, "--agree"])

    def test_complete_series_upgrade(self):
        _machine_num = "1"
        juju_utils.complete_series_upgrade(_machine_num)
        self.subprocess.check_call.assert_called_once_with(
            ["juju", "upgrade-series", "-m", self.model_name,
             "complete", _machine_num])

    def test_set_series(self):
        _application = "application"
        _to_series = "bionic"
        juju_utils.set_series(_application, _to_series)
        self.subprocess.check_call.assert_called_once_with(
            ["juju", "set-series", "-m", self.model_name,
             _application, _to_series])

    def test_update_series(self):
        _machine_num = "1"
        _to_series = "bionic"
        juju_utils.update_series(_machine_num, _to_series)
        self.subprocess.check_call.assert_called_once_with(
            ["juju", "update-series", "-m", self.model_name,
             _machine_num, _to_series])
