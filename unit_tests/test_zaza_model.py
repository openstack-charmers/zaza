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

import aiounittest


# Prior to Python 3.8 asyncio would raise a ``asyncio.futures.TimeoutError``
# exception on timeout, from Python 3.8 onwards it raises a exception from a
# new ``asyncio.exceptions`` module.
#
# Neither of these are inherited from a relevant built-in exception so we
# cannot catch them generally with the built-in TimeoutError or similar.
try:
    import asyncio.exceptions
    AsyncTimeoutError = asyncio.exceptions.TimeoutError
except ImportError:
    import asyncio.futures
    AsyncTimeoutError = asyncio.futures.TimeoutError

import copy
import concurrent
import mock

import unit_tests.utils as ut_utils
from juju import loop

import zaza.model as model


FAKE_STATUS = {
    'can-upgrade-to': '',
    'charm': 'local:trusty/app-136',
    'subordinate-to': [],
    'units': {'app/0': {'leader': True,
                        'machine': '0',
                        'agent-status': {
                            'status': 'idle'
                        },
                        'subordinates': {
                            'app-hacluster/0': {
                                'charm': 'local:trusty/hacluster-0',
                                'leader': True,
                                'agent-status': {
                                    'status': 'idle'
                                }}}},
              'app/1': {'machine': '1',
                        'agent-status': {
                            'status': 'idle'
                        },
                        'subordinates': {
                            'app-hacluster/1': {
                                'charm': 'local:trusty/hacluster-0',
                                'agent-status': {
                                    'status': 'idle'
                                }}}},
              'app/2': {'machine': '2',
                        'agent-status': {
                            'status': 'idle'
                        },
                        'subordinates': {
                            'app-hacluster/2': {
                                'charm': 'local:trusty/hacluster-0',
                                'agent-status': {
                                    'status': 'idle'
                                }}}}}}


EXECUTING_STATUS = {
    'can-upgrade-to': '',
    'charm': 'local:trusty/app-136',
    'subordinate-to': [],
    'units': {'app/0': {'leader': True,
                        'machine': '0',
                        'agent-status': {
                            'status': 'executing'
                        },
                        'subordinates': {
                            'app-hacluster/0': {
                                'charm': 'local:trusty/hacluster-0',
                                'leader': True,
                                'agent-status': {
                                    'status': 'executing'
                                }}}}}}


class TestModel(ut_utils.BaseTestCase):

    def tearDown(self):
        super(TestModel, self).tearDown()
        # Clear cached model name
        model.CURRENT_MODEL = None
        model.MODEL_ALIASES = {}

    def setUp(self):
        super(TestModel, self).setUp()

        async def _scp_to(source, destination, user=None, proxy=None,
                          scp_opts=None):
            return

        async def _scp_from(source, destination, user=None, proxy=None,
                            scp_opts=None):
            return

        async def _run(command, timeout=None):
            return self.action

        async def _run_action(command, **params):
            return self.run_action

        async def _wait():
            return

        async def _add_relation(rel1, rel2):
            return

        async def _destroy_relation(rel1, rel2):
            return

        async def _add_unit(count=1, to=None):
            return

        async def _destroy_unit(*unitnames):
            return

        def _is_leader(leader):
            async def _inner_is_leader():
                return leader
            return _inner_is_leader

        self.run_action = mock.MagicMock()
        self.run_action.wait.side_effect = _wait
        self.action = mock.MagicMock()
        self.action.data = {
            'model-uuid': '1a035018-71ff-473e-8aab-d1a8d6b6cda7',
            'id': 'e26ffb69-6626-4e93-8840-07f7e041e99d',
            'receiver': 'glance/0',
            'name': 'juju-run',
            'parameters': {
                'command': 'somecommand someargument', 'timeout': 0},
            'status': 'completed',
            'message': '',
            'results': {'Code': '0', 'Stderr': '', 'Stdout': 'RESULT'},
            'enqueued': '2018-04-11T23:13:42Z',
            'started': '2018-04-11T23:13:42Z',
            'completed': '2018-04-11T23:13:43Z'}

        self.unit1 = mock.MagicMock()
        self.unit1.public_address = 'ip1'
        self.unit1.name = 'app/2'
        self.unit1.entity_id = 'app/2'
        self.unit1.machine = 'machine3'
        self.unit2 = mock.MagicMock()
        self.unit2.public_address = 'ip2'
        self.unit2.name = 'app/4'
        self.unit2.entity_id = 'app/4'
        self.unit2.machine = 'machine7'
        self.unit2.run.side_effect = _run
        self.unit1.run.side_effect = _run
        self.unit1.scp_to.side_effect = _scp_to
        self.unit2.scp_to.side_effect = _scp_to
        self.unit1.scp_from.side_effect = _scp_from
        self.unit2.scp_from.side_effect = _scp_from
        self.unit1.run_action.side_effect = _run_action
        self.unit2.run_action.side_effect = _run_action
        self.unit1.is_leader_from_status.side_effect = _is_leader(False)
        self.unit2.is_leader_from_status.side_effect = _is_leader(True)
        self.unit1.data = {'agent-status': {'current': 'idle'}}
        self.unit2.data = {'agent-status': {'current': 'idle'}}
        self.units = [self.unit1, self.unit2]
        self.relation1 = mock.MagicMock()
        self.relation1.id = 42
        self.relation1.matches.side_effect = \
            lambda x: True if x == 'app' else False
        self.relation2 = mock.MagicMock()
        self.relation2.id = 51
        self.relation2.matches.side_effect = \
            lambda x: True if x == 'app:interface' else False
        self.relations = [self.relation1, self.relation2]
        _units = mock.MagicMock()
        _units.units = self.units
        _units.relations = self.relations
        _units.add_relation.side_effect = _add_relation
        _units.destroy_relation.side_effect = _destroy_relation
        _units.add_unit.side_effect = _add_unit
        _units.destroy_unit.side_effect = _destroy_unit

        self.mymodel = mock.MagicMock()
        self.mymodel.applications = {
            'app': _units
        }
        self.Model_mock = mock.MagicMock()

        # Juju Status Object and data
        self.key = "instance-id"
        self.key_data = "machine-uuid"
        self.machine = "1"
        self.machine_data = {self.key: self.key_data}
        self.unit = "app/1"
        self.application = "app"
        self.subordinate_application = "subordinate_application"
        self.subordinate_application_data = {
            "subordinate-to": [self.application],
            "units": None}
        self.subordinate_unit = "subordinate_application/1"
        self.subordinate_unit_data = {
            "workload-status": {"status": "active"}}
        self.unit_data = {
            "workload-status": {"status": "active"},
            "machine": self.machine,
            "subordinates": {
                self.subordinate_unit: self.subordinate_unit_data}}
        self.application_data = {"units": {
            self.unit1.name: self.subordinate_unit_data,
            self.unit: self.unit_data}}
        self.juju_status = mock.MagicMock()
        self.juju_status.applications = {
            self.application: self.application_data,
            self.subordinate_application: self.subordinate_application_data}
        self.juju_status.machines = self.machine_data

        async def _connect_model(model_name):
            return model_name

        async def _disconnect():
            return

        async def _connect():
            return

        async def _ctrl_connect():
            return

        async def _ctrl_add_model(model_name, config=None):
            return

        async def _ctrl_destroy_models(model_name):
            return

        self.Model_mock.connect.side_effect = _connect
        self.Model_mock.connect_model.side_effect = _connect_model
        self.Model_mock.disconnect.side_effect = _disconnect
        self.Model_mock.applications = self.mymodel.applications
        self.Model_mock.units = {
            'app/2': self.unit1,
            'app/4': self.unit2}
        self.model_name = "testmodel"
        self.Model_mock.info.name = self.model_name

        self.Controller_mock = mock.MagicMock()
        self.Controller_mock.connect.side_effect = _ctrl_connect
        self.Controller_mock.add_model.side_effect = _ctrl_add_model
        self.Controller_mock.destroy_models.side_effect = _ctrl_destroy_models

    def test_get_juju_model(self):
        self.patch_object(model.os, 'environ')
        self.patch_object(model, 'get_current_model')
        self.get_current_model.return_value = 'modelsmodel'

        def _get_env(key):
            return _env[key]
        self.environ.__getitem__.side_effect = _get_env
        _env = {"JUJU_MODEL": 'envmodel'}

        # JUJU_ENV environment variable set
        self.assertEqual(model.get_juju_model(), 'envmodel')
        self.get_current_model.assert_not_called()

    def test_get_juju_model_alt(self):
        self.patch_object(model.os, 'environ')
        self.patch_object(model, 'get_current_model')
        self.get_current_model.return_value = 'modelsmodel'

        def _get_env(key):
            return _env[key]
        self.environ.__getitem__.side_effect = _get_env
        _env = {"MODEL_NAME": 'envmodel'}

        # JUJU_ENV environment variable set
        self.assertEqual(model.get_juju_model(), 'envmodel')
        self.get_current_model.assert_not_called()

    def test_get_juju_model_noenv(self):
        self.patch_object(model.os, 'environ')
        self.patch_object(model, 'async_get_current_model')

        async def _async_get_current_model():
            return 'modelsmodel'
        self.async_get_current_model.side_effect = _async_get_current_model

        # No envirnment variable
        self.environ.__getitem__.side_effect = KeyError
        self.assertEqual(model.get_juju_model(), 'modelsmodel')
        self.async_get_current_model.assert_called_once()

    def test_set_juju_model_aliases(self):
        model.set_juju_model_aliases({'alias1': 'model1', 'alias2': 'model2'})
        self.assertEqual(
            model.MODEL_ALIASES,
            {'alias1': 'model1', 'alias2': 'model2'})

    def test_unset_juju_model_aliases(self):
        model.unset_juju_model_aliases()
        self.assertEqual(
            model.MODEL_ALIASES,
            {})
        model.set_juju_model_aliases({'alias1': 'model1', 'alias2': 'model2'})
        model.unset_juju_model_aliases()
        self.assertEqual(
            model.MODEL_ALIASES,
            {})

    def test_get_juju_model_aliases(self):
        model.set_juju_model_aliases({'alias1': 'model1', 'alias2': 'model2'})
        self.assertEqual(
            model.get_juju_model_aliases(),
            {'alias1': 'model1', 'alias2': 'model2'})

    def test_run_in_model(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock

        async def _wrapper():
            async with model.run_in_model('modelname') as mymodel:
                return mymodel
        self.assertEqual(loop.run(_wrapper()), self.Model_mock)
        self.Model_mock.connect_model.assert_called_once_with('modelname')
        self.Model_mock.disconnect.assert_called_once_with()

    def test_run_in_model_exception(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock

        async def _wrapper():
            async with model.run_in_model('modelname'):
                raise Exception
        with self.assertRaises(Exception):
            loop.run(_wrapper())
        self.Model_mock.connect_model.assert_called_once_with('modelname')
        self.Model_mock.disconnect.assert_called_once_with()

    def test_scp_to_unit(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.Model.return_value = self.Model_mock
        model.scp_to_unit('app/1', '/tmp/src', '/tmp/dest')
        self.unit1.scp_to.assert_called_once_with(
            '/tmp/src', '/tmp/dest', proxy=False, scp_opts='', user='ubuntu')

    def test_scp_to_all_units(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        model.scp_to_all_units('app', '/tmp/src', '/tmp/dest')
        self.unit1.scp_to.assert_called_once_with(
            '/tmp/src', '/tmp/dest', proxy=False, scp_opts='', user='ubuntu')
        self.unit2.scp_to.assert_called_once_with(
            '/tmp/src', '/tmp/dest', proxy=False, scp_opts='', user='ubuntu')

    def test_scp_from_unit(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.Model.return_value = self.Model_mock
        model.scp_from_unit('app/1', '/tmp/src', '/tmp/dest')
        self.unit1.scp_from.assert_called_once_with(
            '/tmp/src', '/tmp/dest', proxy=False, scp_opts='', user='ubuntu')

    def test_get_units(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(
            model.get_units('app'),
            self.units)

    def test_get_machines(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(
            model.get_machines('app'),
            ['machine3', 'machine7'])

    def test_get_first_unit_name(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'get_units')
        self.get_units.return_value = self.units
        self.assertEqual(
            model.get_first_unit_name('model', 'app'),
            'app/2')

    def test_get_lead_unit_name(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'get_units')
        self.get_units.return_value = self.units
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(
            model.get_lead_unit_name('app', 'model'),
            'app/4')

    def test_get_lead_unit_ip(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'get_units')
        self.get_units.return_value = self.units
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(
            model.get_lead_unit_ip('app', 'model'),
            'ip2')

    def test_get_unit_from_name(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        # Normal case
        self.assertEqual(
            model.get_unit_from_name('app/4', model_name='mname'),
            self.unit2)

        # Normal case with Model()
        self.assertEqual(
            model.get_unit_from_name('app/4', self.mymodel),
            self.unit2)

        # Normal case, using default
        self.assertEqual(
            model.get_unit_from_name('app/4'),
            self.unit2)

        # Unit does not exist
        with self.assertRaises(model.UnitNotFound):
            model.get_unit_from_name('app/10', model_name='mname')

        # Application does not exist
        with self.assertRaises(model.UnitNotFound):
            model.get_unit_from_name('bad_name', model_name='mname')

    def test_get_app_ips(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'get_units')
        self.get_units.return_value = self.units
        self.assertEqual(model.get_app_ips('model', 'app'), ['ip1', 'ip2'])

    def test_run_on_unit(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        expected = {'Code': '0', 'Stderr': '', 'Stdout': 'RESULT'}
        self.cmd = cmd = 'somecommand someargument'
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.Model.return_value = self.Model_mock
        self.assertEqual(model.run_on_unit('app/2', cmd),
                         expected)
        self.unit1.run.assert_called_once_with(cmd, timeout=None)

    def test_run_on_unit_missing_stderr(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        expected = {'Code': '0', 'Stderr': '', 'Stdout': 'RESULT'}
        self.action.data['results'] = {'Code': '0', 'Stdout': 'RESULT'}
        self.cmd = cmd = 'somecommand someargument'
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.Model.return_value = self.Model_mock
        self.assertEqual(model.run_on_unit('app/2', cmd),
                         expected)
        self.unit1.run.assert_called_once_with(cmd, timeout=None)

    def test_run_on_leader(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        expected = {'Code': '0', 'Stderr': '', 'Stdout': 'RESULT'}
        self.cmd = cmd = 'somecommand someargument'
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(model.run_on_leader('app', cmd),
                         expected)
        self.unit2.run.assert_called_once_with(cmd, timeout=None)

    def test_get_relation_id(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(model.get_relation_id('app', 'app'), 42)

    def test_add_relation(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        model.add_relation('app', 'shared-db', 'mysql-shared-db')
        self.mymodel.applications['app'].add_relation.assert_called_once_with(
            'shared-db',
            'mysql-shared-db')

    def test_remove_relation(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        model.remove_relation('app', 'shared-db', 'mysql-shared-db')
        self.mymodel.applications[
            'app'].destroy_relation.assert_called_once_with('shared-db',
                                                            'mysql-shared-db')

    def test_add_unit(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        model.add_unit('app', count=2, to='lxd/0')
        self.mymodel.applications['app'].add_unit.assert_called_once_with(
            count=2, to='lxd/0')

    def test_add_unit_wait(self):
        self.patch_object(model, 'async_block_until_unit_count')
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        model.add_unit('app', count=2, to='lxd/0', wait_appear=True)
        self.mymodel.applications['app'].add_unit.assert_called_once_with(
            count=2, to='lxd/0')
        self.async_block_until_unit_count.assert_called_once_with(
            'app', 4, model_name=None)

    def test_destroy_unit(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        model.destroy_unit('app', 'app/2')
        self.mymodel.applications['app'].destroy_unit.assert_called_once_with(
            'app/2')

    def test_destroy_unit_wait(self):
        self.patch_object(model, 'async_block_until_unit_count')
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        model.destroy_unit('app', 'app/2', wait_disappear=True)
        self.mymodel.applications['app'].destroy_unit.assert_called_once_with(
            'app/2')
        self.async_block_until_unit_count.assert_called_once_with(
            'app', 1, model_name=None)

    def test_get_relation_id_interface(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(
            model.get_relation_id('app', 'app',
                                  remote_interface_name='interface'),
            51)

    def test_run_action(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.Model.return_value = self.Model_mock
        model.run_action(
            'app/2',
            'backup',
            action_params={'backup_dir': '/dev/null'})
        self.unit1.run_action.assert_called_once_with(
            'backup',
            backup_dir='/dev/null')
        self.run_action.status = 'failed'
        self.run_action.message = 'aMessage'
        self.run_action.id = 'aId'
        self.run_action.enqueued = 'aEnqueued'
        self.run_action.started = 'aStarted'
        self.run_action.completed = 'aCompleted'
        self.run_action.name = 'backup2'
        self.run_action.parameters = {'backup_dir': '/non-existent'}
        self.run_action.receiver = 'app/2'
        with self.assertRaises(model.ActionFailed) as e:
            model.run_action(
                self.run_action.receiver,
                self.run_action.name,
                action_params=self.run_action.parameters,
                raise_on_failure=True)
        self.assertEqual(
            str(e.exception),
            'Run of action "backup2" with parameters '
            '"{\'backup_dir\': \'/non-existent\'}" on '
            '"app/2" failed with "aMessage" '
            '(id=aId status=failed enqueued=aEnqueued '
            'started=aStarted completed=aCompleted)')

    def test_get_actions(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model.subprocess, 'check_output')
        self.check_output.return_value = 'action: "action desc"'
        self.assertEqual(
            model.get_actions('myapp'),
            {'action': "action desc"})
        self.check_output.assert_called_once_with(
            ['juju', 'actions', '-m', 'mname', 'myapp', '--format', 'yaml'])

    def test_run_action_on_leader(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        model.run_action_on_leader(
            'app',
            'backup',
            action_params={'backup_dir': '/dev/null'})
        self.assertFalse(self.unit1.called)
        self.unit2.run_action.assert_called_once_with(
            'backup',
            backup_dir='/dev/null')
        self.run_action.status = 'failed'
        self.run_action.message = 'aMessage'
        self.run_action.id = 'aId'
        self.run_action.enqueued = 'aEnqueued'
        self.run_action.started = 'aStarted'
        self.run_action.completed = 'aCompleted'
        self.run_action.name = 'backup2'
        self.run_action.parameters = {'backup_dir': '/non-existent'}
        self.run_action.receiver = 'app/2'
        with self.assertRaises(model.ActionFailed) as e:
            model.run_action(
                self.run_action.receiver,
                self.run_action.name,
                action_params=self.run_action.parameters,
                raise_on_failure=True)
        self.assertEqual(
            str(e.exception),
            'Run of action "backup2" with parameters '
            '"{\'backup_dir\': \'/non-existent\'}" on '
            '"app/2" failed with "aMessage" '
            '(id=aId status=failed enqueued=aEnqueued '
            'started=aStarted completed=aCompleted)')

    def test_run_action_on_units(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_unit_from_name')
        units = {
            'app/1': self.unit1,
            'app/2': self.unit2}
        self.get_unit_from_name.side_effect = lambda x, y: units[x]
        self.run_action.status = 'completed'
        model.run_action_on_units(
            ['app/1', 'app/2'],
            'backup',
            action_params={'backup_dir': '/dev/null'})
        self.unit1.run_action.assert_called_once_with(
            'backup',
            backup_dir='/dev/null')
        self.unit2.run_action.assert_called_once_with(
            'backup',
            backup_dir='/dev/null')

    def test_run_action_on_units_timeout(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.run_action.status = 'running'
        with self.assertRaises(AsyncTimeoutError):
            model.run_action_on_units(
                ['app/1'],
                'backup',
                action_params={'backup_dir': '/dev/null'},
                timeout=0.1)

    def test_run_action_on_units_fail(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.run_action.status = 'failed'
        with self.assertRaises(model.ActionFailed):
            model.run_action_on_units(
                ['app/1'],
                'backup',
                raise_on_failure=True,
                action_params={'backup_dir': '/dev/null'})

    def _application_states_setup(self, setup, units_idle=True):
        self.system_ready = True
        self._block_until_calls = 0

        async def _block_until(f, timeout=0):
            # Mimic timeouts
            timeout = timeout + self._block_until_calls
            self._block_until_calls += 1
            if timeout == -1:
                raise concurrent.futures._base.TimeoutError("Timeout", 1)
            result = f()
            if not result:
                self.system_ready = False
            return

        async def _all_units_idle():
            return units_idle
        self.Model_mock.block_until.side_effect = _block_until
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.Model_mock.all_units_idle.return_value = _all_units_idle
        p_mock_ws = mock.PropertyMock(
            return_value=setup['workload-status'])
        p_mock_wsmsg = mock.PropertyMock(
            return_value=setup['workload-status-message'])
        type(self.unit1).workload_status = p_mock_ws
        type(self.unit1).workload_status_message = p_mock_wsmsg
        type(self.unit2).workload_status = p_mock_ws
        type(self.unit2).workload_status_message = p_mock_wsmsg

    def test_units_with_wl_status_state(self):
        self._application_states_setup({
            'workload-status': 'active',
            'workload-status-message': 'Unit is ready'})
        units = model.units_with_wl_status_state(self.Model_mock, 'active')
        self.assertTrue(len(units) == 2)
        self.assertIn(self.unit1, units)
        self.assertIn(self.unit2, units)

    def test_units_with_wl_status_state_no_match(self):
        self._application_states_setup({
            'workload-status': 'blocked',
            'workload-status-message': 'Unit is ready'})
        units = model.units_with_wl_status_state(self.Model_mock, 'active')
        self.assertTrue(len(units) == 0)

    def test_check_model_for_hard_errors(self):
        self.patch_object(model, 'units_with_wl_status_state')
        self.units_with_wl_status_state.return_value = []
        # Test will fail if an Exception is raised
        model.check_model_for_hard_errors(self.Model_mock)

    def test_check_model_for_hard_errors_found(self):
        self.patch_object(model, 'units_with_wl_status_state')
        self.units_with_wl_status_state.return_value = [self.unit1]
        with self.assertRaises(model.UnitError):
            model.check_model_for_hard_errors(self.Model_mock)

    def test_check_unit_workload_status(self):
        self.patch_object(model, 'check_model_for_hard_errors')
        self._application_states_setup({
            'workload-status': 'active',
            'workload-status-message': 'Unit is ready'})
        self.assertTrue(
            model.check_unit_workload_status(self.Model_mock,
                                             self.unit1, ['active']))

    def test_check_unit_workload_status_no_match(self):
        self.patch_object(model, 'check_model_for_hard_errors')
        self._application_states_setup({
            'workload-status': 'blocked',
            'workload-status-message': 'Unit is ready'})
        self.assertFalse(
            model.check_unit_workload_status(self.Model_mock,
                                             self.unit1, ['active']))

    def test_check_unit_workload_status_multi(self):
        self.patch_object(model, 'check_model_for_hard_errors')
        self._application_states_setup({
            'workload-status': 'blocked',
            'workload-status-message': 'Unit is ready'})
        self.assertTrue(
            model.check_unit_workload_status(
                self.Model_mock,
                self.unit1, ['active', 'blocked']))

    def test_check_unit_workload_status_message_message(self):
        self.patch_object(model, 'check_model_for_hard_errors')
        self._application_states_setup({
            'workload-status': 'blocked',
            'workload-status-message': 'Unit is ready'})
        self.assertTrue(
            model.check_unit_workload_status_message(self.Model_mock,
                                                     self.unit1,
                                                     message='Unit is ready'))

    def test_check_unit_workload_status_message_message_not_found(self):
        self.patch_object(model, 'check_model_for_hard_errors')
        self._application_states_setup({
            'workload-status': 'blocked',
            'workload-status-message': 'Something else'})
        self.assertFalse(
            model.check_unit_workload_status_message(self.Model_mock,
                                                     self.unit1,
                                                     message='Unit is ready'))

    def test_check_unit_workload_status_message_prefix(self):
        self.patch_object(model, 'check_model_for_hard_errors')
        self._application_states_setup({
            'workload-status': 'blocked',
            'workload-status-message': 'Unit is ready (OSD Count 23)'})
        self.assertTrue(
            model.check_unit_workload_status_message(
                self.Model_mock,
                self.unit1,
                prefixes=['Readyish', 'Unit is ready']))

    def test_check_unit_workload_status_message_prefix_no_match(self):
        self.patch_object(model, 'check_model_for_hard_errors')
        self._application_states_setup({
            'workload-status': 'blocked',
            'workload-status-message': 'On my holidays'})
        self.assertFalse(
            model.check_unit_workload_status_message(
                self.Model_mock,
                self.unit1,
                prefixes=['Readyish', 'Unit is ready']))

    def test_wait_for_application_states(self):
        self._application_states_setup({
            'workload-status': 'active',
            'workload-status-message': 'Unit is ready'})
        model.wait_for_application_states('modelname', timeout=1)
        self.assertTrue(self.system_ready)

    def test_wait_for_application_states_not_ready_ws(self):
        self._application_states_setup({
            'workload-status': 'blocked',
            'workload-status-message': 'Unit is ready'})
        model.wait_for_application_states('modelname', timeout=1)
        self.assertFalse(self.system_ready)

    def test_wait_for_application_states_errored_unit(self):
        self._application_states_setup({
            'workload-status': 'error',
            'workload-status-message': 'Unit is ready'})
        with self.assertRaises(model.UnitError):
            model.wait_for_application_states('modelname', timeout=1)
            self.assertFalse(self.system_ready)

    def test_wait_for_application_states_not_ready_wsmsg(self):
        self._application_states_setup({
            'workload-status': 'active',
            'workload-status-message': 'Unit is not ready'})
        model.wait_for_application_states('modelname', timeout=1)
        self.assertFalse(self.system_ready)

    def test_wait_for_application_states_blocked_ok(self):
        self._application_states_setup({
            'workload-status': 'blocked',
            'workload-status-message': 'Unit is ready'})
        model.wait_for_application_states(
            'modelname',
            states={'app': {
                'workload-status': 'blocked'}},
            timeout=1)
        self.assertTrue(self.system_ready)

    def test_wait_for_application_states_bespoke_msg(self):
        self._application_states_setup({
            'workload-status': 'active',
            'workload-status-message': 'Sure, I could do something'})
        model.wait_for_application_states(
            'modelname',
            states={'app': {
                'workload-status-message': 'Sure, I could do something'}},
            timeout=1)
        self.assertTrue(self.system_ready)

    def test_wait_for_application_states_bespoke_msg_blocked_ok(self):
        self._application_states_setup({
            'workload-status': 'blocked',
            'workload-status-message': 'Sure, I could do something'})
        model.wait_for_application_states(
            'modelname',
            states={'app': {
                'workload-status': 'blocked',
                'workload-status-message': 'Sure, I could do something'}},
            timeout=1)
        self.assertTrue(self.system_ready)

    def test_wait_for_application_states_idle_timeout(self):
        self._application_states_setup({
            'agent-status': 'executing',
            'workload-status': 'blocked',
            'workload-status-message': 'Sure, I could do something'})
        with self.assertRaises(model.ModelTimeout) as timeout:
            model.wait_for_application_states('modelname', timeout=-2)
        self.assertEqual(
            timeout.exception.args[0],
            "Zaza has timed out waiting on the model to reach idle state.")

    def test_wait_for_application_states_timeout(self):
        self._application_states_setup({
            'agent-status': 'executing',
            'workload-status': 'blocked',
            'workload-status-message': 'Sure, I could do something'})
        with self.assertRaises(model.ModelTimeout) as timeout:
            model.wait_for_application_states('modelname', timeout=-3)
        self.assertEqual(
            timeout.exception.args[0],
            ("Timed out waiting for 'app/2'. The workload status is 'blocked' "
             "which is not one of '['active']'"))

    def test_get_current_model(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(model.get_current_model(), self.model_name)

    def test_block_until_file_has_contents(self):
        self.action.data = {
            'results': {'Code': '0', 'Stderr': '', 'Stdout': 'somestring'}
        }

        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch("builtins.open",
                   new_callable=mock.mock_open(),
                   name="_open")
        _fileobj = mock.MagicMock()
        _fileobj.__enter__().read.return_value = "somestring"
        self._open.return_value = _fileobj
        model.block_until_file_has_contents(
            'app',
            '/tmp/src/myfile.txt',
            'somestring',
            timeout=0.1)
        self.unit1.run.assert_called_once_with(
            'cat /tmp/src/myfile.txt')
        self.unit2.run.assert_called_once_with(
            'cat /tmp/src/myfile.txt')

    def test_block_until_file_has_no_contents(self):
        self.action.data = {
            'results': {'Code': '0', 'Stderr': ''}
        }

        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch("builtins.open",
                   new_callable=mock.mock_open(),
                   name="_open")
        _fileobj = mock.MagicMock()
        _fileobj.__enter__().read.return_value = ""
        self._open.return_value = _fileobj
        model.block_until_file_has_contents(
            'app',
            '/tmp/src/myfile.txt',
            '',
            timeout=0.1)
        self.unit1.run.assert_called_once_with(
            'cat /tmp/src/myfile.txt')
        self.unit2.run.assert_called_once_with(
            'cat /tmp/src/myfile.txt')

    def test_block_until_file_has_contents_missing(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch("builtins.open",
                   new_callable=mock.mock_open(),
                   name="_open")
        _fileobj = mock.MagicMock()
        _fileobj.__enter__().read.return_value = "anything else"
        self._open.return_value = _fileobj
        with self.assertRaises(AsyncTimeoutError):
            model.block_until_file_has_contents(
                'app',
                '/tmp/src/myfile.txt',
                'somestring',
                timeout=0.1)
        self.unit1.run.assert_called_once_with('cat /tmp/src/myfile.txt')

    def test_block_until_file_missing(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.action.data['results']['Stdout'] = "1"
        model.block_until_file_missing(
            'app',
            '/tmp/src/myfile.txt',
            timeout=0.1)
        self.unit1.run.assert_called_once_with(
            'test -e "/tmp/src/myfile.txt"; echo $?')

    def test_block_until_file_missing_isnt_missing(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.action.data['results']['Stdout'] = "0"
        with self.assertRaises(AsyncTimeoutError):
            model.block_until_file_missing(
                'app',
                '/tmp/src/myfile.txt',
                timeout=0.1)

    def test_async_block_until_all_units_idle(self):

        async def _block_until(f, timeout=None):
            if not f():
                raise AsyncTimeoutError

        def _all_units_idle():
            return True
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.Model_mock.all_units_idle.side_effect = _all_units_idle
        self.Model_mock.block_until.side_effect = _block_until
        # Check exception is not raised:
        model.block_until_all_units_idle('modelname')

    def test_async_block_until_all_units_idle_false(self):

        async def _block_until(f, timeout=None):
            if not f():
                raise AsyncTimeoutError

        def _all_units_idle():
            return False
        self.Model_mock.all_units_idle.side_effect = _all_units_idle
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.Model_mock.block_until.side_effect = _block_until
        # Confirm exception is raised:
        with self.assertRaises(AsyncTimeoutError):
            model.block_until_all_units_idle('modelname')

    def test_async_block_until_all_units_idle_errored_unit(self):

        async def _block_until(f, timeout=None):
            if not f():
                raise AsyncTimeoutError

        def _all_units_idle():
            return True
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.Model_mock.all_units_idle.side_effect = _all_units_idle
        self.patch_object(model, 'units_with_wl_status_state')
        unit = mock.MagicMock()
        unit.entity_id = 'aerroredunit/0'
        self.units_with_wl_status_state.return_value = [unit]
        self.Model_mock.block_until.side_effect = _block_until
        with self.assertRaises(model.UnitError):
            model.block_until_all_units_idle('modelname')

    def test_block_until_unit_count(self):

        async def _block_until(f, timeout=None):
            rc = await f()
            if not rc:
                raise AsyncTimeoutError

        async def _get_status():
            return self.juju_status
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'async_block_until')
        self.async_block_until.side_effect = _block_until
        self.patch_object(model, 'async_get_status')
        self.async_get_status.side_effect = _get_status
        self.juju_status.applications[self.application]["units"] = [
            'app/1', 'app/2']
        model.block_until_unit_count('app', 2)
        with self.assertRaises(AsyncTimeoutError):
            model.block_until_unit_count('app', 3, timeout=0.1)
        with self.assertRaises(AssertionError):
            model.block_until_unit_count('app', 2.3)

    def test_block_until_charm_url(self):

        async def _block_until(f, timeout=None):
            rc = await f()
            if not rc:
                raise AsyncTimeoutError

        async def _get_status():
            return self.juju_status
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'async_block_until')
        self.async_block_until.side_effect = _block_until
        self.patch_object(model, 'async_get_status')
        self.async_get_status.side_effect = _get_status
        target_url = 'cs:openstack-charmers-next/app'
        self.juju_status.applications[self.application]['charm'] = target_url
        model.block_until_charm_url('app', target_url)
        with self.assertRaises(AsyncTimeoutError):
            model.block_until_charm_url('app', 'something wrong', timeout=0.1)

    def block_until_service_status_base(self, rou_return):

        async def _block_until(f, timeout=None):
            rc = await f()
            if not rc:
                raise AsyncTimeoutError

        async def _run_on_unit(unit_name, cmd, model_name=None, timeout=None):
            return rou_return
        self.patch_object(model, 'async_run_on_unit')
        self.async_run_on_unit.side_effect = _run_on_unit
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'async_block_until')
        self.async_block_until.side_effect = _block_until

    def test_block_until_service_status_check_running(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.block_until_service_status_base({'Stdout': '152 409 54'})
        model.block_until_service_status(
            'app/2',
            ['test_svc'],
            'running')

    def test_block_until_service_status_check_running_with_pgrep(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.block_until_service_status_base({'Stdout': '152 409 54'})
        model.block_until_service_status(
            'app/2',
            ['test_svc'],
            'running',
            pgrep_full=True)
        self.async_run_on_unit.assert_called_once_with(
            'app/2',
            "pgrep -f 'test_svc'",
            model_name=None,
            timeout=2700
        )

    def test_block_until_service_status_check_running_fail(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.block_until_service_status_base({'Stdout': ''})
        with self.assertRaises(AsyncTimeoutError):
            model.block_until_service_status(
                'app/2',
                ['test_svc'],
                'running')

    def test_block_until_service_status_check_stopped(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.block_until_service_status_base({'Stdout': ''})
        model.block_until_service_status(
            'app/2',
            ['test_svc'],
            'stopped')

    def test_block_until_service_status_check_stopped_fail(self):
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.block_until_service_status_base({'Stdout': '152 409 54'})
        with self.assertRaises(AsyncTimeoutError):
            model.block_until_service_status(
                'app/2',
                ['test_svc'],
                'stopped')

    def test_get_unit_time(self):
        async def _run_on_unit(
            unit_name,
            command,
            model_name=None,
            timeout=None
        ):
            return {'Stdout': '1524409654'}
        self.patch_object(model, 'async_run_on_unit')
        self.async_run_on_unit.side_effect = _run_on_unit
        self.assertEqual(
            model.get_unit_time('app/2'),
            1524409654)
        self.async_run_on_unit.assert_called_once_with(
            unit_name='app/2',
            command="date +'%s'",
            model_name=None,
            timeout=None
        )

    def test_get_unit_service_start_time(self):
        async def _run_on_unit(
            unit_name,
            command,
            model_name=None,
            timeout=None
        ):
            return {'Stdout': '1524409654'}
        self.patch_object(model, 'async_run_on_unit')
        self.async_run_on_unit.side_effect = _run_on_unit
        self.assertEqual(
            model.get_unit_service_start_time('app/2', 'mysvc1'), 1524409654)
        cmd = (r"pidof -x 'mysvc1'| tr -d '\n' | "
               "xargs -d' ' -I {} stat -c %Y /proc/{}  | sort -n | head -1")
        self.async_run_on_unit.assert_called_once_with(
            unit_name='app/2',
            command=cmd,
            model_name=None,
            timeout=None
        )

    def test_get_unit_service_start_time_with_pgrep(self):
        async def _run_on_unit(
            unit_name,
            command,
            model_name=None,
            timeout=None
        ):
            return {'Stdout': '1524409654'}
        self.patch_object(model, 'async_run_on_unit')
        self.async_run_on_unit.side_effect = _run_on_unit
        self.assertEqual(
            model.get_unit_service_start_time('app/2',
                                              'mysvc1',
                                              pgrep_full=True),
            1524409654)
        cmd = "stat -c %Y /proc/$(pgrep -o -f 'mysvc1')"

        self.async_run_on_unit.assert_called_once_with(
            unit_name='app/2',
            command=cmd,
            model_name=None,
            timeout=None
        )

    def test_get_unit_service_start_time_not_running(self):
        async def _run_on_unit(
            unit_name,
            command,
            model_name=None,
            timeout=None
        ):
            return {'Stdout': ''}
        self.patch_object(model, 'async_run_on_unit')
        self.async_run_on_unit.side_effect = _run_on_unit
        with self.assertRaises(model.ServiceNotRunning):
            model.get_unit_service_start_time('app/2', 'mysvc1')

    def block_until_oslo_config_entries_match_base(self, file_contents,
                                                   expected_contents):
        self.action.data = {
            'results': {'Code': '0', 'Stderr': '', 'Stdout': file_contents}
        }
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.Model.return_value = self.Model_mock
        model.block_until_oslo_config_entries_match(
            'app',
            '/tmp/src/myfile.txt',
            expected_contents,
            timeout=0.1)

    def test_block_until_oslo_config_entries_match(self):
        file_contents = """
[DEFAULT]
verbose = False
use_syslog = False
debug = False
workers = 4
bind_host = 0.0.0.0

[glance_store]
filesystem_store_datadir = /var/lib/glance/images/
stores = glance.store.filesystem.Store,glance.store.http.Store
default_store = file

[image_format]
disk_formats = ami,ari,aki,vhd,vmdk,raw,qcow2,vdi,iso,root-tar
"""
        expected_contents = {
            'DEFAULT': {
                'debug': ['False']},
            'glance_store': {
                'filesystem_store_datadir': ['/var/lib/glance/images/'],
                'default_store': ['file']}}
        self.block_until_oslo_config_entries_match_base(
            file_contents,
            expected_contents)
        self.unit1.run.assert_called_once_with(
            'cat /tmp/src/myfile.txt')
        self.unit2.run.assert_called_once_with(
            'cat /tmp/src/myfile.txt')

    def test_block_until_oslo_config_entries_match_fail(self):
        file_contents = """
[DEFAULT]
verbose = False
use_syslog = False
debug = True
workers = 4
bind_host = 0.0.0.0

[glance_store]
filesystem_store_datadir = /var/lib/glance/images/
stores = glance.store.filesystem.Store,glance.store.http.Store
default_store = file

[image_format]
disk_formats = ami,ari,aki,vhd,vmdk,raw,qcow2,vdi,iso,root-tar
"""
        expected_contents = {
            'DEFAULT': {
                'debug': ['False']},
            'glance_store': {
                'filesystem_store_datadir': ['/var/lib/glance/images/'],
                'default_store': ['file']}}
        with self.assertRaises(AsyncTimeoutError):
            self.block_until_oslo_config_entries_match_base(
                file_contents,
                expected_contents)
        self.unit1.run.assert_called_once_with(
            'cat /tmp/src/myfile.txt')

    def test_block_until_oslo_config_entries_match_missing_entry(self):
        file_contents = """
[DEFAULT]
verbose = False
use_syslog = False
workers = 4
bind_host = 0.0.0.0

[glance_store]
filesystem_store_datadir = /var/lib/glance/images/
stores = glance.store.filesystem.Store,glance.store.http.Store
default_store = file

[image_format]
disk_formats = ami,ari,aki,vhd,vmdk,raw,qcow2,vdi,iso,root-tar
"""
        expected_contents = {
            'DEFAULT': {
                'debug': ['False']},
            'glance_store': {
                'filesystem_store_datadir': ['/var/lib/glance/images/'],
                'default_store': ['file']}}
        with self.assertRaises(AsyncTimeoutError):
            self.block_until_oslo_config_entries_match_base(
                file_contents,
                expected_contents)
        self.unit1.run.assert_called_once_with(
            'cat /tmp/src/myfile.txt')

    def test_block_until_oslo_config_entries_match_missing_section(self):
        file_contents = """
[DEFAULT]
verbose = False
use_syslog = False
workers = 4
bind_host = 0.0.0.0

[image_format]
disk_formats = ami,ari,aki,vhd,vmdk,raw,qcow2,vdi,iso,root-tar
"""
        expected_contents = {
            'DEFAULT': {
                'debug': ['False']},
            'glance_store': {
                'filesystem_store_datadir': ['/var/lib/glance/images/'],
                'default_store': ['file']}}
        with self.assertRaises(AsyncTimeoutError):
            self.block_until_oslo_config_entries_match_base(
                file_contents,
                expected_contents)
        self.unit1.run.assert_called_once_with(
            'cat /tmp/src/myfile.txt')

    def block_until_services_restarted_base(self, gu_return=None,
                                            gu_raise_exception=False):
        async def _block_until(f, timeout=None):
            rc = await f()
            if not rc:
                raise AsyncTimeoutError
        self.patch_object(model, 'async_block_until')
        self.async_block_until.side_effect = _block_until

        async def _async_get_unit_service_start_time(unit, svc, timeout=None,
                                                     model_name=None,
                                                     pgrep_full=False):
            if gu_raise_exception:
                raise model.ServiceNotRunning('sv1')
            else:
                return gu_return
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'async_get_unit_service_start_time')
        self.async_get_unit_service_start_time.side_effect = \
            _async_get_unit_service_start_time
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock

    def test_block_until_services_restarted(self):
        self.block_until_services_restarted_base(gu_return=10)
        model.block_until_services_restarted(
            'app',
            8,
            ['svc1', 'svc2'])

    def test_block_until_services_restarted_with_pgrep(self):
        self.block_until_services_restarted_base(gu_return=10)
        model.block_until_services_restarted(
            'app',
            8,
            ['svc1', 'svc2'],
            pgrep_full=True)
        self.async_get_unit_service_start_time.assert_has_calls([
            mock.call('app/2',
                      'svc1',
                      model_name=None,
                      pgrep_full=True,
                      timeout=2700),
            mock.call('app/2',
                      'svc2',
                      model_name=None,
                      pgrep_full=True,
                      timeout=2700),
            mock.call('app/4',
                      'svc1',
                      model_name=None,
                      pgrep_full=True,
                      timeout=2700),
            mock.call('app/4',
                      'svc2',
                      model_name=None,
                      pgrep_full=True,
                      timeout=2700),
        ])

    def test_block_until_services_restarted_fail(self):
        self.block_until_services_restarted_base(gu_return=10)
        with self.assertRaises(AsyncTimeoutError):
            model.block_until_services_restarted(
                'app',
                12,
                ['svc1', 'svc2'])

    def test_block_until_services_restarted_not_running(self):
        self.block_until_services_restarted_base(gu_raise_exception=True)
        with self.assertRaises(AsyncTimeoutError):
            model.block_until_services_restarted(
                'app',
                12,
                ['svc1', 'svc2'])

    def test_block_until_unit_wl_status(self):
        async def _block_until(f, timeout=None):
            rc = await f()
            if not rc:
                raise AsyncTimeoutError

        async def _get_status():
            return self.juju_status

        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'get_unit_from_name')
        self.patch_object(model, 'async_get_status')
        self.async_get_status.side_effect = _get_status
        self.patch_object(model, 'async_block_until')
        self.async_block_until.side_effect = _block_until
        model.block_until_unit_wl_status(
            'app/1',
            'active',
            timeout=0.1)
        model.block_until_unit_wl_status(
            'subordinate_application/1',
            'active',
            timeout=0.1)

    def test_block_until_unit_wl_status_fail(self):
        async def _block_until(f, timeout=None):
            rc = await f()
            if not rc:
                raise AsyncTimeoutError

        async def _get_status():
            return self.juju_status

        (self.juju_status.applications[self.application]
            ["units"][self.unit]["workload-status"]["status"]) = "blocked"
        (self.juju_status.applications[self.application]
            ["units"][self.unit]['subordinates'][self.subordinate_unit]
            ["workload-status"]["status"]) = "blocked"

        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'get_unit_from_name')
        self.patch_object(model, 'async_get_status')
        self.async_get_status.side_effect = _get_status
        self.patch_object(model, 'async_block_until')
        self.async_block_until.side_effect = _block_until
        with self.assertRaises(AsyncTimeoutError):
            model.block_until_unit_wl_status(
                'app/1',
                'active',
                timeout=0.1)
        with self.assertRaises(AsyncTimeoutError):
            model.block_until_unit_wl_status(
                'subordinate_application/1',
                'active',
                timeout=0.1)

    def test_block_until_unit_wl_status_inverse(self):
        async def _block_until(f, timeout=None):
            rc = await f()
            if not rc:
                raise AsyncTimeoutError

        async def _get_status():
            return self.juju_status

        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'get_unit_from_name')
        self.patch_object(model, 'async_get_status')
        self.async_get_status.side_effect = _get_status
        self.patch_object(model, 'async_block_until')
        self.async_block_until.side_effect = _block_until
        model.block_until_unit_wl_status(
            'app/1',
            'unknown',
            negate_match=True,
            timeout=0.1)
        model.block_until_unit_wl_status(
            'subordinate_application/1',
            'unknown',
            negate_match=True,
            timeout=0.1)

    def test_block_until_wl_status_info_starts_with(self):
        async def _block_until(f, timeout=None):
            rc = await f()
            if not rc:
                raise AsyncTimeoutError

        async def _get_status():
            return self.juju_status

        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'get_unit_from_name')
        self.patch_object(model, 'async_get_status')
        self.juju_status.applications['app']['units']['app/1'][
            'workload-status']['info'] = "match-me if you want"
        self.juju_status.applications['app']['units']['app/2'][
            'workload-status']['info'] = "match-me if you want"
        self.async_get_status.side_effect = _get_status
        self.patch_object(model, 'async_block_until')
        self.async_block_until.side_effect = _block_until
        model.block_until_wl_status_info_starts_with(
            'app',
            'match-me')

    def test_block_until_wl_status_info_starts_with_negative(self):
        async def _block_until(f, timeout=None):
            rc = await f()
            if not rc:
                raise AsyncTimeoutError

        async def _get_status():
            return self.juju_status

        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'get_unit_from_name')
        self.patch_object(model, 'async_get_status')
        self.juju_status.applications['app']['units']['app/1'][
            'workload-status']['info'] = "match-me if you want"
        self.juju_status.applications['app']['units']['app/2'][
            'workload-status']['info'] = "match-me if you want"
        self.async_get_status.side_effect = _get_status
        self.patch_object(model, 'async_block_until')
        self.async_block_until.side_effect = _block_until
        model.block_until_wl_status_info_starts_with(
            'app',
            'dont-match-me',
            negate_match=True)

    def resolve_units_mocks(self):
        async def _block_until(f, timeout=None):
            if not f():
                raise AsyncTimeoutError
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.patch_object(model, 'units_with_wl_status_state')
        self.unit1.workload_status_message = 'hook failed: "update-status"'
        self.units_with_wl_status_state.return_value = [self.unit1]
        self.patch_object(model, 'subprocess')
        self.Model_mock.block_until.side_effect = _block_until

    def test_resolve_units(self):
        self.resolve_units_mocks()
        model.resolve_units(wait=False)
        self.subprocess.check_output.assert_called_once_with(
            ['juju', 'resolved', '-m', 'testmodel', 'app/2'])

    def test_resolve_units_no_match(self):
        self.resolve_units_mocks()
        model.resolve_units(application_name='foo', wait=False)
        self.assertFalse(self.subprocess.check_output.called)

    def test_resolve_units_wait_timeout(self):
        self.resolve_units_mocks()
        self.unit1.workload_status = 'error'
        with self.assertRaises(AsyncTimeoutError):
            model.resolve_units(wait=True, timeout=0.1)
        self.subprocess.check_output.assert_called_once_with(
            ['juju', 'resolved', '-m', 'testmodel', 'app/2'])

    def test_resolve_units_erred_hook(self):
        self.resolve_units_mocks()
        model.resolve_units(wait=False, erred_hook='update-status')
        self.subprocess.check_output.assert_called_once_with(
            ['juju', 'resolved', '-m', 'testmodel', 'app/2'])

    def test_resolve_units_erred_hook_no_match(self):
        self.resolve_units_mocks()
        model.resolve_units(erred_hook='foo', wait=False)
        self.assertFalse(self.subprocess.check_output.called)

    def test_wait_for_agent_status(self):
        async def _block_until(f, timeout=None):
            if not f():
                raise AsyncTimeoutError
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.unit1.data = {'agent-status': {'current': 'idle'}}
        self.unit2.data = {'agent-status': {'current': 'executing'}}
        self.Model.return_value = self.Model_mock
        self.Model_mock.block_until.side_effect = _block_until
        model.wait_for_agent_status(timeout=0.1)

    def test_wait_for_agent_status_timeout(self):
        async def _block_until(f, timeout=None):
            if not f():
                raise AsyncTimeoutError
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.Model_mock.block_until.side_effect = _block_until
        with self.assertRaises(AsyncTimeoutError):
            model.wait_for_agent_status(timeout=0.1)

    def test_upgrade_charm(self):
        async def _upgrade_charm(channel=None, force_series=False,
                                 force_units=False, path=None,
                                 resources=None, revision=None,
                                 switch=None, model_name=None):
            return
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.Model.return_value = self.Model_mock
        app_mock = mock.MagicMock()
        app_mock.upgrade_charm.side_effect = _upgrade_charm
        self.mymodel.applications['myapp'] = app_mock
        model.upgrade_charm(
            'myapp',
            switch='cs:~me/new-charm-45')
        app_mock.upgrade_charm.assert_called_once_with(
            channel=None,
            force_series=False,
            force_units=False,
            path=None,
            resources=None,
            revision=None,
            switch='cs:~me/new-charm-45')

    def test_get_latest_charm_url(self):
        async def _entity(charm_url, channel=None):
            return {'Id': 'cs:something-23'}
        self.patch_object(model, 'get_juju_model', return_value='mname')
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.Model_mock.charmstore.entity.side_effect = _entity
        self.assertEqual(
            model.get_latest_charm_url('cs:something'),
            'cs:something-23')

    def test_prepare_series_upgrade(self):
        self.patch_object(model, 'subprocess')
        self.patch_object(model, 'get_juju_model',
                          return_value=self.model_name)
        _machine_num = "1"
        _to_series = "bionic"
        model.prepare_series_upgrade(_machine_num, to_series=_to_series)
        self.subprocess.check_call.assert_called_once_with(
            ["juju", "upgrade-series", "-m", self.model_name,
             _machine_num, "prepare", _to_series, "--yes"])

    def test_complete_series_upgrade(self):
        self.patch_object(model, 'get_juju_model',
                          return_value=self.model_name)
        self.patch_object(model, 'subprocess')
        _machine_num = "1"
        model.complete_series_upgrade(_machine_num)
        self.subprocess.check_call.assert_called_once_with(
            ["juju", "upgrade-series", "-m", self.model_name,
             _machine_num, "complete"])

    def test_set_series(self):
        self.patch_object(model, 'get_juju_model',
                          return_value=self.model_name)
        self.patch_object(model, 'subprocess')
        _application = "application"
        _to_series = "bionic"
        model.set_series(_application, _to_series)
        self.subprocess.check_call.assert_called_once_with(
            ["juju", "set-series", "-m", self.model_name,
             _application, _to_series])

    def test_attach_resource(self):
        self.patch_object(model, 'get_juju_model',
                          return_value=self.model_name)
        self.patch_object(model, 'subprocess')
        _application = "application"
        _resource_name = "myresource"
        _resource_path = "/path/to/{}.tar.gz".format(_resource_name)
        model.attach_resource(_application, _resource_name, _resource_path)
        self.subprocess.check_call.assert_called_once_with(
            ["juju", "attach-resource", "-m", self.model_name,
             _application, "{}={}".format(_resource_name, _resource_path)])


class AsyncModelTests(aiounittest.AsyncTestCase):

    async def test_async_block_until_timeout(self):

        async def _f():
            return False

        async def _g():
            return True

        with self.assertRaises(AsyncTimeoutError):
            await model.async_block_until(_f, _g, timeout=0.1)

    async def test_async_block_until_pass(self):

        async def _f():
            return True

        async def _g():
            return True

        await model.async_block_until(_f, _g, timeout=0.1)

    async def test_run_on_machine(self):
        with mock.patch.object(
            model.generic_utils,
            'check_call'
        ) as check_call:
            await model.async_run_on_machine('1', 'test')
        check_call.assert_called_once_with(
            ['juju', 'run', '--machine=1', 'test'])

    async def test_run_on_machine_with_timeout(self):
        # self.patch_object(model.generic_utils, 'check_call')
        with mock.patch.object(
            model.generic_utils,
            'check_call'
        ) as check_call:
            await model.async_run_on_machine('1', 'test', timeout='20m')
        check_call.assert_called_once_with(
            ['juju', 'run', '--machine=1', '--timeout=20m', 'test'])

    async def test_run_on_machine_with_model(self):
        # self.patch_object(model.generic_utils, 'check_call')
        with mock.patch.object(
            model.generic_utils,
            'check_call'
        ) as check_call:
            await model.async_run_on_machine('1', 'test', model_name='test')
        check_call.assert_called_once_with(
            ['juju', 'run', '--machine=1', '--model=test', 'test'])

    async def test_async_get_agent_status(self):
        model_mock = mock.MagicMock()
        model_mock.applications.__getitem__.return_value = FAKE_STATUS
        with mock.patch.object(
            model,
            'async_get_status',
            return_value=model_mock
        ):
            idle = await model.async_get_agent_status('app', 'app/0')
        self.assertEqual('idle', idle)

    async def test_async_check_if_subordinates_idle(self):
        model_mock = mock.MagicMock()
        model_mock.applications.__getitem__.return_value = FAKE_STATUS
        with mock.patch.object(
            model,
            'async_get_status',
            return_value=model_mock
        ):
            idle = await model.async_check_if_subordinates_idle('app', 'app/0')
        assert(idle)

    async def test_async_get_agent_status_busy(self):
        model_mock = mock.MagicMock()
        model_mock.applications.__getitem__.return_value = EXECUTING_STATUS
        with mock.patch.object(
            model,
            'async_get_status',
            return_value=model_mock
        ):
            idle = await model.async_get_agent_status('app', 'app/0')
        self.assertEqual('executing', idle)

    async def test_async_check_if_subordinates_idle_busy(self):
        model_mock = mock.MagicMock()
        model_mock.applications.__getitem__.return_value = EXECUTING_STATUS
        with mock.patch.object(
            model,
            'async_get_status',
            return_value=model_mock
        ):
            idle = await model.async_check_if_subordinates_idle('app', 'app/0')
        self.assertFalse(idle)

    async def test_async_check_if_subordinates_idle_missing(self):
        model_mock = mock.MagicMock()
        status = copy.deepcopy(EXECUTING_STATUS)
        del(status['units']['app/0']['subordinates'])
        model_mock.applications.__getitem__.return_value = status
        with mock.patch.object(
            model,
            'async_get_status',
            return_value=model_mock
        ):
            idle = await model.async_check_if_subordinates_idle('app', 'app/0')
        assert(idle)
