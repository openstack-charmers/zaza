import copy
import mock

import zaza.charm_lifecycle.prepare as lc_prepare
import unit_tests.utils as ut_utils


class TestCharmLifecyclePrepare(ut_utils.BaseTestCase):

    MODEL_CONFIG_DEFAULTS = lc_prepare.MODEL_DEFAULTS

    def base_get_model_settings(self, env, expect):
        with mock.patch.dict(lc_prepare.os.environ, env):
            self.assertEqual(lc_prepare.get_model_settings(), expect)

    def test_get_model_settings_no_config(self):
        expect_config = copy.deepcopy(self.MODEL_CONFIG_DEFAULTS)
        self.base_get_model_settings({}, expect_config)

    def test_get_model_settings_empty_config(self):
        expect_config = copy.deepcopy(self.MODEL_CONFIG_DEFAULTS)
        self.base_get_model_settings({'MODEL_SETTINGS': ''}, expect_config)

    def test_get_model_settings_single_value(self):
        expect_config = copy.deepcopy(self.MODEL_CONFIG_DEFAULTS)
        expect_config.update({'virt-type': 'kvm'})
        self.base_get_model_settings(
            {'MODEL_SETTINGS': 'virt-type=kvm'},
            expect_config)

    def test_get_model_settings_multiple_values(self):
        expect_config = copy.deepcopy(self.MODEL_CONFIG_DEFAULTS)
        expect_config.update({
            'virt-type': 'kvm',
            'no-proxy': 'jujucharms.com'})
        self.base_get_model_settings(
            {'MODEL_SETTINGS': 'virt-type=kvm;no-proxy=jujucharms.com'},
            expect_config)

    def test_get_model_settings_multiple_values_override(self):
        expect_config = copy.deepcopy(self.MODEL_CONFIG_DEFAULTS)
        expect_config.update({'test-mode': 'false'})
        self.base_get_model_settings(
            {'MODEL_SETTINGS': 'test-mode=false'},
            expect_config)

    def test_get_model_settings_whitespace(self):
        expect_config = copy.deepcopy(self.MODEL_CONFIG_DEFAULTS)
        expect_config.update({
            'test-mode': 'false',
            'virt-type': 'kvm'})
        self.base_get_model_settings(
            {'MODEL_SETTINGS': ' test-mode= false ; virt-type=  kvm'},
            expect_config)

    def test_prepare(self):
        self.patch_object(lc_prepare.zaza.controller, 'add_model')
        self.patch_object(lc_prepare, 'get_model_settings')
        self.get_model_settings.return_value = lc_prepare.MODEL_DEFAULTS
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
