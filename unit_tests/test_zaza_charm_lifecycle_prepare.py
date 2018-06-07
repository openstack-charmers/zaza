import zaza.charm_lifecycle.prepare as lc_prepare
import unit_tests.utils as ut_utils


class TestCharmLifecyclePrepare(ut_utils.BaseTestCase):

    def test_prepare(self):
        self.patch_object(lc_prepare.zaza.model, 'add_model')
        lc_prepare.prepare('newmodel')
        self.add_model.assert_called_once_with(
            'newmodel',
            config={
                'agent-stream': 'proposed',
                'default-series': 'xenial',
                'image-stream': 'daily',
                'test-mode': 'true',
                'transmit-vendor-metrics': 'false',
                'enable-os-upgrade': 'false',
                'automatically-retry-hooks': 'false',
                'use-default-secgroup': 'true'})

    def test_parser(self):
        args = lc_prepare.parse_args(['-m', 'newmodel'])
        self.assertEqual(args.model_name, 'newmodel')
