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

        class MachineMock(dict):

            def __init__(self, display_name=''):
                self.display_name = display_name

        # Juju Status Object and data
        self.key = "instance-id"
        self.key_data = "machine-uuid"

        self.machine1 = "1"
        self.machine1_mock = MachineMock()
        self.machine1_mock[self.key] = self.key_data

        self.machine2 = "2"
        self.machine2_mock = MachineMock()
        self.machine2_mock[self.key] = self.key_data

        self.unit1 = "app/1"
        self.unit1_data = {"machine": self.machine1}
        self.unit1_mock = mock.MagicMock()
        self.unit1_mock.entity_id = self.unit1
        self.unit1_mock.data = {'machine-id': self.machine1}
        self.unit1_mock.public_address = '10.0.0.1'

        self.unit2 = "app/2"
        self.unit2_data = {"machine": self.machine2}
        self.unit2_mock = mock.MagicMock()
        self.unit2_mock.entity_id = self.unit2
        self.unit2_mock.data = {'machine-id': self.machine2}

        self.application = "app"
        self.subordinate_application = "subordinate_application"
        self.subordinate_application_unit = "subordinate_application/0"
        self.subordinate_application_data = {
            "subordinate-to": [self.application]}
        self.application_data = {
            "units": {self.unit1: self.unit1_data},
            "subordinates": {self.subordinate_application_unit: {}}}
        self.juju_status = mock.MagicMock()
        self.juju_status.name = "juju_status_object"
        self.juju_status.applications = {
            self.application: self.application_data,
            self.subordinate_application: self.subordinate_application_data}
        self.juju_status.machines = {
            self.machine1: self.machine1_mock,
            self.machine2: self.machine2_mock}

        # Model
        self.patch_object(juju_utils, "model")
        self.model_name = "model-name"
        self.model.get_juju_model.return_value = self.model_name
        self.model.get_status.return_value = self.juju_status
        self.run_output = {"Code": "0", "Stderr": "", "Stdout": "RESULT"}
        self.error_run_output = {"Code": "1", "Stderr": "ERROR", "Stdout": ""}
        self.model.run_on_unit.return_value = self.run_output
        self.model.get_units.return_value = [self.unit1_mock, self.unit2_mock]

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

    def _get_application_status(self, application=None, unit=None,
                                model_name=None):
        if unit and not application:
            application = unit.split("/")[0]
        return self.juju_status.applications[application]

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
            juju_utils.get_application_status(unit=self.unit1),
            self.unit1_data)

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
        self.model.get_status.assert_called_once_with(model_name=None)

    def test_get_machines_for_application(self):
        self.patch_object(juju_utils, "get_full_juju_status")
        self.get_full_juju_status.return_value = self.juju_status

        # Machine data
        self.assertEqual(
            list(juju_utils.get_machines_for_application(self.application)),
            [self.machine1])

        self.assertEqual(
            list(juju_utils.get_machines_for_application(
                self.subordinate_application)),
            [self.machine1])

    def test_get_unit_name_from_host_name_maas(self):
        self.assertEqual(
            juju_utils.get_unit_name_from_host_name('juju-model-1', 'app'),
            'app/1')
        self.machine2_mock.display_name = 'node-jaeger.maas'
        self.assertEqual(
            juju_utils.get_unit_name_from_host_name('node-jaeger.maas', 'app'),
            'app/2')

    def test_get_unit_name_from_host_name(self):
        self.patch_object(juju_utils, "get_application_status")
        self.get_application_status.side_effect = self._get_application_status
        self.assertEqual(
            juju_utils.get_unit_name_from_host_name(
                'juju-model-1',
                self.application),
            'app/1')
        self.assertEqual(
            juju_utils.get_unit_name_from_host_name(
                'juju-model-1.project.serverstack',
                self.application),
            'app/1')

    def test_get_unit_name_from_host_name_bad_app(self):
        self.assertIsNone(
            juju_utils.get_unit_name_from_host_name('juju-model-12',
                                                    'madeup-app'))

    def test_get_unit_name_from_host_name_subordinate(self):
        self.patch_object(juju_utils, "get_application_status")
        self.get_application_status.side_effect = self._get_application_status
        self.assertEqual(
            juju_utils.get_unit_name_from_host_name(
                'juju-model-1',
                self.subordinate_application),
            self.subordinate_application_unit)

    def test_get_unit_name_from_ip_address(self):
        unit_mock3 = mock.MagicMock()
        unit_mock3.data = {'public-address': '10.0.0.12', 'private-address':
                           '10.0.0.13', 'name': 'myapp/2'}
        unit_mock3.entity_id = 'myapp/2'
        unit_mock4 = mock.MagicMock()
        unit_mock4.data = {'public-address': '10.0.0.240', 'private-address':
                           '10.0.0.241', 'name': 'myapp/5'}
        unit_mock4.entity_id = 'myapp/5'
        self.model.get_units.return_value = [unit_mock3, unit_mock4]
        self.assertEqual(
            juju_utils.get_unit_name_from_ip_address('10.0.0.12', 'myapp'),
            'myapp/2')
        self.assertEqual(
            juju_utils.get_unit_name_from_ip_address('10.0.0.241', 'myapp'),
            'myapp/5')

    def test_get_machine_status(self):
        self.patch_object(juju_utils, "get_full_juju_status")
        self.get_full_juju_status.return_value = self.juju_status

        # All machine data
        self.assertEqual(
            juju_utils.get_machine_status(self.machine1),
            {self.key: self.key_data})
        self.get_full_juju_status.assert_called_once()

        # Request a specific key
        self.assertEqual(
            juju_utils.get_machine_status(self.machine1, self.key),
            self.key_data)

    def test_get_machine_uuids_for_application(self):
        self.patch_object(juju_utils, "get_machines_for_application")
        self.get_machines_for_application.return_value = [self.machine1]

        self.assertEqual(
            list(juju_utils.get_machine_uuids_for_application(
                self.application)),
            [self.key_data])
        self.get_machines_for_application.assert_called_once_with(
            self.application,
            model_name=None)

    def test_get_provider_type(self):
        self.patch_object(juju_utils, "get_cloud_configs")
        self.get_cloud_configs.return_value = {"type": self.cloud_type}
        self.assertEqual(juju_utils.get_provider_type(),
                         self.cloud_type)
        self.get_cloud_configs.assert_called_once_with(self.cloud_name)

    def test_remote_run(self):
        _cmd = "do the thing"

        # Success
        self.assertEqual(juju_utils.remote_run(self.unit1, _cmd),
                         self.run_output["Stdout"])
        self.model.run_on_unit.assert_called_once_with(
            self.unit1, _cmd, model_name=None, timeout=None)

        # Non-fatal failure
        self.model.run_on_unit.return_value = self.error_run_output
        self.assertEqual(juju_utils.remote_run(self.unit1, _cmd, fatal=False),
                         self.error_run_output["Stderr"])

        # Fatal failure
        with self.assertRaises(Exception):
            juju_utils.remote_run(self.unit1, _cmd, fatal=True)

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
            'relation-get --format=yaml -r "42" - "otherunit/0"',
            model_name=None)
        self.yaml.safe_load.assert_called_with(str(data))

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
            'relation-get --format=yaml -r "42" - "otherunit/0"',
            model_name=None)
        self.assertFalse(self.yaml.safe_load.called)

    def test_leader_get(self):
        self.patch_object(juju_utils, 'yaml')
        self.patch_object(juju_utils, 'model')
        data = {'foo': 'bar'}
        self.model.run_on_leader.return_value = {
            'Code': 0, 'Stdout': str(data)}
        juju_utils.leader_get('application')
        self.model.run_on_leader.assert_called_with(
            'application', 'leader-get --format=yaml ',
            model_name=None)
        self.yaml.safe_load.assert_called_with(str(data))

    def test_leader_get_key(self):
        self.patch_object(juju_utils, 'yaml')
        self.patch_object(juju_utils, 'model')
        data = {'foo': 'bar'}
        self.model.run_on_leader.return_value = {
            'Code': 0, 'Stdout': data['foo']}
        juju_utils.leader_get('application', 'foo')
        self.model.run_on_leader.assert_called_with(
            'application', 'leader-get --format=yaml foo',
            model_name=None)
        self.yaml.safe_load.assert_called_with(data['foo'])

    def test_leader_get_fails(self):
        self.patch_object(juju_utils, 'yaml')
        self.patch_object(juju_utils, 'model')
        self.model.run_on_leader.return_value = {
            'Code': 1, 'Stderr': 'ERROR'}
        with self.assertRaises(Exception):
            juju_utils.leader_get('application')
        self.model.run_on_leader.assert_called_with(
            'application', 'leader-get --format=yaml ',
            model_name=None)
        self.assertFalse(self.yaml.safe_load.called)

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
            key='series',
            model_name=None
        )
        self.assertEqual(expected, actual)

    def test_get_subordinate_units(self):
        juju_status = mock.MagicMock()
        juju_status.applications = {
            'nova-compute': {
                'units': {
                    'nova-compute/0': {
                        'subordinates': {
                            'neutron-openvswitch/2': {
                                'charm': 'cs:neutron-openvswitch-22'}}}}},
            'cinder': {
                'units': {
                    'cinder/1': {
                        'subordinates': {
                            'cinder-hacluster/0': {
                                'charm': 'cs:hacluster-42'},
                            'cinder-ceph/3': {
                                'charm': 'cs:cinder-ceph-2'}}}}},
        }
        self.model.get_status.return_Value = juju_status
        self.assertEqual(
            sorted(juju_utils.get_subordinate_units(
                ['nova-compute/0', 'cinder/1'],
                status=juju_status)),
            sorted(['neutron-openvswitch/2', 'cinder-hacluster/0',
                    'cinder-ceph/3']))
        self.assertEqual(
            juju_utils.get_subordinate_units(
                ['nova-compute/0', 'cinder/1'],
                charm_name='ceph',
                status=juju_status),
            ['cinder-ceph/3'])

    def test_get_application_ip(self):
        self.model.get_application_config.return_value = {
            'vip': {'value': '10.0.0.10'}}
        self.model.get_units.return_value = [self.unit1_mock]
        self.assertEqual(
            juju_utils.get_application_ip('app'),
            '10.0.0.10')
        self.model.get_application_config.return_value = {}
        self.assertEqual(
            juju_utils.get_application_ip('app'),
            '10.0.0.1')
