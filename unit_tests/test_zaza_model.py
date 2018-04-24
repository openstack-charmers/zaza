import mock
import zaza.model as model
import unit_tests.utils as ut_utils
from juju import loop


class TestModel(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestModel, self).setUp()

        async def _scp_to(source, destination, user, proxy, scp_opts):
            return

        async def _scp_from(source, destination, user, proxy, scp_opts):
            return

        async def _run(command, timeout=None):
            return self.action

        async def _run_action(command, **params):
            return self.run_action

        async def _wait():
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
        self.unit1.run.side_effect = _run
        self.unit1.scp_to.side_effect = _scp_to
        self.unit2.scp_to.side_effect = _scp_to
        self.unit1.scp_from.side_effect = _scp_from
        self.unit2.scp_from.side_effect = _scp_from
        self.unit1.run_action.side_effect = _run_action
        self.unit2.run_action.side_effect = _run_action
        self.unit1.is_leader_from_status.side_effect = _is_leader(False)
        self.unit2.is_leader_from_status.side_effect = _is_leader(True)
        self.units = [self.unit1, self.unit2]
        _units = mock.MagicMock()
        _units.units = self.units
        self.mymodel = mock.MagicMock()
        self.mymodel.applications = {
            'app': _units
        }
        self.Model_mock = mock.MagicMock()

        async def _connect_model(model_name):
            return model_name

        async def _disconnect():
            return

        self.Model_mock.connect_model.side_effect = _connect_model
        self.Model_mock.disconnect.side_effect = _disconnect
        self.Model_mock.applications = self.mymodel.applications

    def test_run_in_model(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock

        async def _wrapper():
            async with model.run_in_model('modelname') as mymodel:
                return mymodel
        self.assertEqual(loop.run(_wrapper()), self.Model_mock)
        self.Model_mock.connect_model.assert_called_once_with('modelname')
        self.Model_mock.disconnect.assert_called_once_with()

    def test_scp_to_unit(self):
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.Model.return_value = self.Model_mock
        model.scp_to_unit('modelname', 'app/1', '/tmp/src', '/tmp/dest')
        self.unit1.scp_to.assert_called_once_with(
            '/tmp/src', '/tmp/dest', proxy=False, scp_opts='', user='ubuntu')

    def test_scp_to_all_units(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        model.scp_to_all_units('modelname', 'app', '/tmp/src', '/tmp/dest')
        self.unit1.scp_to.assert_called_once_with(
            '/tmp/src', '/tmp/dest', proxy=False, scp_opts='', user='ubuntu')
        self.unit2.scp_to.assert_called_once_with(
            '/tmp/src', '/tmp/dest', proxy=False, scp_opts='', user='ubuntu')

    def test_scp_from_unit(self):
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.Model.return_value = self.Model_mock
        model.scp_from_unit('modelname', 'app/1', '/tmp/src', '/tmp/dest')
        self.unit1.scp_from.assert_called_once_with(
            '/tmp/src', '/tmp/dest', proxy=False, scp_opts='', user='ubuntu')

    def test_get_units(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(
            model.get_units('modelname', 'app'),
            self.units)

    def test_get_machines(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(
            model.get_machines('modelname', 'app'),
            ['machine3', 'machine7'])

    def test_get_first_unit_name(self):
        self.patch_object(model, 'get_units')
        self.get_units.return_value = self.units
        self.assertEqual(
            model.get_first_unit_name('model', 'app'),
            'app/2')

    def test_get_unit_from_name(self):
        self.assertEqual(
            model.get_unit_from_name('app/4', self.mymodel),
            self.unit2)

    def test_get_app_ips(self):
        self.patch_object(model, 'get_units')
        self.get_units.return_value = self.units
        self.assertEqual(model.get_app_ips('model', 'app'), ['ip1', 'ip2'])

    def test_run_on_unit(self):
        expected = {'Code': '0', 'Stderr': '', 'Stdout': 'RESULT'}
        self.cmd = cmd = 'somecommand someargument'
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.Model.return_value = self.Model_mock
        self.assertEqual(model.run_on_unit('app/2', 'modelname', cmd),
                         expected)
        self.unit1.run.assert_called_once_with(cmd, timeout=None)

    def test_run_action(self):
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        self.get_unit_from_name.return_value = self.unit1
        self.Model.return_value = self.Model_mock
        model.run_action('app/2', 'modelname', 'backup',
                         {'backup_dir': '/dev/null'})
        self.unit1.run_action.assert_called_once_with(
            'backup',
            backup_dir='/dev/null')

    def test_get_actions(self):
        self.patch_object(model.subprocess, 'check_output')
        self.check_output.return_value = 'action: "action desc"'
        self.assertEqual(
            model.get_actions('mname', 'myapp'),
            {'action': "action desc"})
        self.check_output.assert_called_once_with(
            ['juju', 'actions', '-m', 'mname', 'myapp', '--format', 'yaml'])

    def test_run_action_on_leader(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        model.run_action_on_leader('modelname', 'app', 'backup',
                                   {'backup_dir': '/dev/null'})
        self.assertFalse(self.unit1.called)
        self.unit2.run_action.assert_called_once_with(
            'backup',
            backup_dir='/dev/null')

    def _application_states_setup(self, setup):
        self.system_ready = True

        async def _block_until(f, timeout=None):
            result = f()
            if not result:
                self.system_ready = False
            return
        self.Model_mock.block_until.side_effect = _block_until
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.Model_mock.all_units_idle.return_value = True
        p_mock_ws = mock.PropertyMock(
            return_value=setup['workload-status'])
        p_mock_wsmsg = mock.PropertyMock(
            return_value=setup['workload-status-message'])
        type(self.unit1).workload_status = p_mock_ws
        type(self.unit1).workload_status_message = p_mock_wsmsg
        type(self.unit2).workload_status = p_mock_ws
        type(self.unit2).workload_status_message = p_mock_wsmsg

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

    def test_wait_for_application_states_bespoke_msg_bloked_ok(self):
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
