import functools
import mock
import zaza.model as model
import unit_tests.utils as ut_utils
from juju import loop


class TestModel(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestModel, self).setUp()

        async def _scp_to(source, destination, user, proxy, scp_opts):
            return
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

        async def _test_func(arg):
            return arg * 2
        self.Model.return_value = self.Model_mock
        func = functools.partial(_test_func, 'hello')
        out = loop.run(
            model.run_in_model(
                'mymodel',
                func,
                awaitable=True))
        self.assertEqual(out, 'hellohello')

    def test_run_in_model_not_awaitable(self):
        self.patch_object(model, 'Model')

        def _test_func(arg):
            return arg * 3
        self.Model.return_value = self.Model_mock
        func = functools.partial(_test_func, 'hello')
        out = loop.run(
            model.run_in_model(
                'mymodel',
                func,
                awaitable=False))
        self.assertEqual(out, 'hellohellohello')

    def test_run_in_model_add_model_arg(self):
        self.patch_object(model, 'Model')

        def _test_func(arg, model):
            return model
        self.Model.return_value = self.Model_mock
        func = functools.partial(_test_func, 'hello')
        out = loop.run(
            model.run_in_model(
                'mymodel',
                func,
                add_model_arg=True,
                awaitable=False))
        self.assertEqual(out, self.Model_mock)

    def test_scp_to_unit(self):
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        unit_mock = mock.MagicMock()
        self.get_unit_from_name.return_value = unit_mock
        self.Model.return_value = self.Model_mock
        model.scp_to_unit('app/1', 'modelname', '/tmp/src', '/tmp/dest')
        unit_mock.scp_to.assert_called_once_with(
            '/tmp/src', '/tmp/dest', proxy=False, scp_opts='', user='ubuntu')

    def test_scp_to_all_units(self):
        self.patch_object(model, 'Model')
        self.Model.return_value = self.Model_mock
        model.scp_to_all_units('app', 'modelname', '/tmp/src', '/tmp/dest')
        self.unit1.scp_to.assert_called_once_with(
            '/tmp/src', '/tmp/dest', proxy=False, scp_opts='', user='ubuntu')
        self.unit2.scp_to.assert_called_once_with(
            '/tmp/src', '/tmp/dest', proxy=False, scp_opts='', user='ubuntu')

    def test_scp_from_unit(self):
        self.patch_object(model, 'Model')
        self.patch_object(model, 'get_unit_from_name')
        unit_mock = mock.MagicMock()
        self.get_unit_from_name.return_value = unit_mock
        self.Model.return_value = self.Model_mock
        model.scp_from_unit('app/1', 'modelname', '/tmp/src', '/tmp/dest')
        unit_mock.scp_from.assert_called_once_with(
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
