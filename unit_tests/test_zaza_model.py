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

        async def _get_config():
            return {'debug': 'maybe'}

        async def _set_config(config):
            return config

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
        self.unit1.scp_to.side_effect = _scp_to
        self.unit2.scp_to.side_effect = _scp_to
        self.unit1.scp_from.side_effect = _scp_from
        self.unit2.scp_from.side_effect = _scp_from
        self.units = [self.unit1, self.unit2]
        self._app_mock = mock.MagicMock()
        self._app_mock.units = self.units
        self._app_mock.get_config = _get_config
        self._app_mock.set_config = _set_config
        self.mymodel = mock.MagicMock()
        self.mymodel.applications = {
            'app': self._app_mock
        }
        self.Model_mock = mock.MagicMock()

        async def _connect_model(model_name):
            return model_name

        async def _disconnect():
            return

        async def _get_status():
            return {'current-status'}

        self.Model_mock.connect_model.side_effect = _connect_model
        self.Model_mock.disconnect.side_effect = _disconnect
        self.Model_mock.applications = self.mymodel.applications
        self.Model_mock.get_status.side_effect = _get_status

    def test_RunInModel(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock

        async def _wrapper():
            async with model.RunInModel('modelname') as mymodel:
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

    def test_get_application(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(
            model.get_application('modelname', 'app'),
            self._app_mock
        )

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

    def test_get_application_config(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(
            model.get_application_config('modelname', 'app'),
            {'debug': 'maybe'})

    def test_set_application_config(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(model.set_application_config(
            'modelname', 'app', {'debug': 'probably'}),
            {'debug': 'probably'})

    def test_get_status(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        self.assertEqual(
            model.get_status('modelname'),
            {'current-status'})
