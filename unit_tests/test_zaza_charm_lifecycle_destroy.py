import zaza.charm_lifecycle.destroy as lc_destroy
import unit_tests.utils as ut_utils


class TestCharmLifecycleDestroy(ut_utils.BaseTestCase):

    def test_destroy_model(self):
        self.patch_object(lc_destroy.subprocess, 'check_call')
        lc_destroy.destroy_model('doomed')
        self.check_call.assert_called_once_with(
            ['juju', 'destroy-model', '--yes', 'doomed'])

    def test_destroy(self):
        self.patch_object(lc_destroy, 'destroy_model')
        lc_destroy.destroy('doomed')
        self.destroy_model.assert_called_once_with('doomed')

    def test_parser(self):
        args = lc_destroy.parse_args(['-m', 'doomed'])
        self.assertEqual(args.model_name, 'doomed')
