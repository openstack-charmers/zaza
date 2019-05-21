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

import zaza.charm_lifecycle.func_test_runner as lc_func_test_runner
import unit_tests.utils as ut_utils


class TestCharmLifecycleFuncTestRunner(ut_utils.BaseTestCase):

    def test_parser(self):
        # Test defaults
        args = lc_func_test_runner.parse_args([])
        self.assertFalse(args.keep_model)
        self.assertFalse(args.smoke)
        self.assertFalse(args.dev)
        self.assertIsNone(args.bundle)
        # Test flags
        args = lc_func_test_runner.parse_args(['--keep-model'])
        self.assertTrue(args.keep_model)
        args = lc_func_test_runner.parse_args(['--smoke'])
        self.assertTrue(args.smoke)
        args = lc_func_test_runner.parse_args(['--dev'])
        self.assertTrue(args.dev)
        args = lc_func_test_runner.parse_args(['--bundle', 'mybundle'])
        self.assertEqual(args.bundle, 'mybundle')
        args = lc_func_test_runner.parse_args(['--log', 'DEBUG'])
        self.assertEqual(args.loglevel, 'DEBUG')

    def test_func_test_runner(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.generate_model_name.return_value = 'newmodel'
        self.get_charm_config.return_value = {
            'charm_name': 'mycharm',
            'gate_bundles': ['bundle1', 'bundle2'],
            'smoke_bundles': ['bundle2'],
            'dev_bundles': ['bundle3', 'bundle4'],
            'configure': [
                'zaza.charm_tests.mycharm.setup.basic_setup'
                'zaza.charm_tests.othercharm.setup.setup'],
            'tests': [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest']}
        lc_func_test_runner.func_test_runner()
        prepare_calls = [
            mock.call('newmodel'),
            mock.call('newmodel')]
        deploy_calls = [
            mock.call('./tests/bundles/bundle1.yaml', 'newmodel'),
            mock.call('./tests/bundles/bundle2.yaml', 'newmodel')]
        configure_calls = [
            mock.call('newmodel', [
                'zaza.charm_tests.mycharm.setup.basic_setup'
                'zaza.charm_tests.othercharm.setup.setup']),
            mock.call('newmodel', [
                'zaza.charm_tests.mycharm.setup.basic_setup'
                'zaza.charm_tests.othercharm.setup.setup'])]
        test_calls = [
            mock.call('newmodel', [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest']),
            mock.call('newmodel', [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest'])]
        destroy_calls = [
            mock.call('newmodel'),
            mock.call('newmodel')]
        self.prepare.assert_has_calls(prepare_calls)
        self.deploy.assert_has_calls(deploy_calls)
        self.configure.assert_has_calls(configure_calls)
        self.test.assert_has_calls(test_calls)
        self.destroy.assert_has_calls(destroy_calls)

    def test_func_test_runner_smoke(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.generate_model_name.return_value = 'newmodel'
        self.get_charm_config.return_value = {
            'charm_name': 'mycharm',
            'gate_bundles': ['bundle1', 'bundle2'],
            'smoke_bundles': ['bundle2'],
            'dev_bundles': ['bundle3', 'bundle4'],
            'configure': [
                'zaza.charm_tests.mycharm.setup.basic_setup'
                'zaza.charm_tests.othercharm.setup.setup'],
            'tests': [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest']}
        lc_func_test_runner.func_test_runner(smoke=True)
        deploy_calls = [
            mock.call('./tests/bundles/bundle2.yaml', 'newmodel')]
        self.deploy.assert_has_calls(deploy_calls)

    def test_func_test_runner_dev(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.generate_model_name.return_value = 'newmodel'
        self.get_charm_config.return_value = {
            'charm_name': 'mycharm',
            'gate_bundles': ['bundle1', 'bundle2'],
            'smoke_bundles': ['bundle2'],
            'dev_bundles': ['bundle3', 'bundle4'],
            'configure': [
                'zaza.charm_tests.mycharm.setup.basic_setup'
                'zaza.charm_tests.othercharm.setup.setup'],
            'tests': [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest']}
        lc_func_test_runner.func_test_runner(dev=True)
        deploy_calls = [
            mock.call('./tests/bundles/bundle3.yaml', 'newmodel'),
            mock.call('./tests/bundles/bundle4.yaml', 'newmodel')]
        self.deploy.assert_has_calls(deploy_calls)

    def test_func_test_runner_specify_bundle(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.generate_model_name.return_value = 'newmodel'
        self.get_charm_config.return_value = {
            'charm_name': 'mycharm',
            'gate_bundles': ['bundle1', 'bundle2'],
            'smoke_bundles': ['bundle2'],
            'dev_bundles': ['bundle3', 'bundle4'],
            'configure': [
                'zaza.charm_tests.mycharm.setup.basic_setup'
                'zaza.charm_tests.othercharm.setup.setup'],
            'tests': [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest']}
        lc_func_test_runner.func_test_runner(bundle='maveric-filebeat')
        deploy_calls = [
            mock.call('./tests/bundles/maveric-filebeat.yaml', 'newmodel')]
        self.deploy.assert_has_calls(deploy_calls)

    def test_main_smoke_dev_ambiguous(self):
        self.patch_object(lc_func_test_runner, 'parse_args')
        self.patch_object(lc_func_test_runner, 'cli_utils')
        self.patch_object(lc_func_test_runner, 'func_test_runner')
        self.patch_object(lc_func_test_runner, 'asyncio')
        _args = mock.Mock()
        _args.loglevel = 'DEBUG'
        _args.dev = True
        _args.smoke = True
        self.parse_args.return_value = _args
        with self.assertRaises(ValueError) as context:
            lc_func_test_runner.main()
        self.assertEqual(
            'Ambiguous arguments: --smoke and --dev cannot be used together',
            str(context.exception))

    def test_main_bundle_dev_ambiguous(self):
        self.patch_object(lc_func_test_runner, 'parse_args')
        self.patch_object(lc_func_test_runner, 'cli_utils')
        self.patch_object(lc_func_test_runner, 'func_test_runner')
        self.patch_object(lc_func_test_runner, 'asyncio')
        _args = mock.Mock()
        _args.loglevel = 'DEBUG'
        _args.dev = True
        _args.smoke = False
        _args.bundle = 'foo.yaml'
        self.parse_args.return_value = _args
        with self.assertRaises(ValueError) as context:
            lc_func_test_runner.main()
        self.assertEqual(
            ('Ambiguous arguments: --bundle and --dev '
             'cannot be used together'),
            str(context.exception))

    def test_main_bundle_smoke_ambiguous(self):
        self.patch_object(lc_func_test_runner, 'parse_args')
        self.patch_object(lc_func_test_runner, 'cli_utils')
        self.patch_object(lc_func_test_runner, 'func_test_runner')
        self.patch_object(lc_func_test_runner, 'asyncio')
        _args = mock.Mock()
        _args.loglevel = 'DEBUG'
        _args.dev = False
        _args.smoke = True
        _args.bundle = 'foo.yaml'
        self.parse_args.return_value = _args
        with self.assertRaises(ValueError) as context:
            lc_func_test_runner.main()
        self.assertEqual(
            ('Ambiguous arguments: --bundle and --smoke '
             'cannot be used together'),
            str(context.exception))
