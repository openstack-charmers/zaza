import zaza.charm_lifecycle.prepare as lc_prepare
import unit_tests.utils as ut_utils


class TestCharmLifecyclePrepare(ut_utils.BaseTestCase):

    def test_add_model(self):
        self.patch_object(lc_prepare.subprocess, 'check_call')
        lc_prepare.add_model('newmodel')
        self.check_call.assert_called_once_with(
            [
                'juju', 'add-model', 'newmodel',
                '--config', 'agent-stream=proposed',
                '--config', 'default-series=xenial',
                '--config', 'image-stream=daily',
                '--config', 'test-mode=true',
                '--config', 'transmit-vendor-metrics=false',
                '--config', 'enable-os-upgrade=false',
                '--config', 'automatically-retry-hooks=false',
                '--config', 'use-default-secgroup=true'
            ])

    def test_prepare(self):
        self.patch_object(lc_prepare, 'add_model')
        lc_prepare.add_model('newmodel')
        self.add_model.assert_called_once_with('newmodel')

    def test_parser(self):
        args = lc_prepare.parse_args(['-m', 'newmodel'])
        self.assertEqual(args.model_name, 'newmodel')
