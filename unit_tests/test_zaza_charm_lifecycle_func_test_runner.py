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
import os

import zaza.charm_lifecycle.func_test_runner as lc_func_test_runner
import unit_tests.utils as ut_utils


class TestCharmLifecycleFuncTestRunner(ut_utils.BaseTestCase):

    def test_parser(self):
        # Test defaults
        args = lc_func_test_runner.parse_args([])
        self.assertFalse(args.keep_last_model)
        self.assertFalse(args.smoke)
        self.assertFalse(args.dev)
        self.assertFalse(args.force)
        self.assertIsNone(args.bundles)
        # Test flags
        for flag in ['--keep-model', '--keep-last-model']:
            args = lc_func_test_runner.parse_args([flag])
            self.assertTrue(args.keep_last_model)
            args.keep_last_model = False
        args = lc_func_test_runner.parse_args(['--keep-all-models'])
        self.assertTrue(args.keep_all_models)
        args = lc_func_test_runner.parse_args(['--keep-faulty-model'])
        self.assertTrue(args.keep_faulty_model)
        args = lc_func_test_runner.parse_args(['--smoke'])
        self.assertTrue(args.smoke)
        args = lc_func_test_runner.parse_args(['--dev'])
        self.assertTrue(args.dev)
        args = lc_func_test_runner.parse_args(
            ['--bundle', 'mybundle', 'mybundle2'])
        self.assertEqual(args.bundles, ['mybundle', 'mybundle2'])
        args = lc_func_test_runner.parse_args(['--log', 'DEBUG'])
        self.assertEqual(args.loglevel, 'DEBUG')
        args = lc_func_test_runner.parse_args(['-f'])
        self.assertTrue(args.force)
        args = lc_func_test_runner.parse_args(['--force'])
        self.assertTrue(args.force)

    def test_func_test_runner(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.before_deploy, 'before_deploy')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.patch_object(
            lc_func_test_runner.zaza.model,
            'block_until_all_units_idle')
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
        lc_func_test_runner.func_test_runner(
            force=True)
        prepare_calls = [
            mock.call('newmodel', test_directory=None),
            mock.call('newmodel', test_directory=None)]
        cwd = os.getcwd()
        deploy_calls = [
            mock.call(cwd + '/tests/bundles/bundle1.yaml', 'newmodel',
                      model_ctxt={'default_alias': 'newmodel'},
                      force=True, test_directory=None, trust=False,
                      ignore_hard_deploy_errors=False),
            mock.call(cwd + '/tests/bundles/bundle2.yaml', 'newmodel',
                      model_ctxt={'default_alias': 'newmodel'},
                      force=True, test_directory=None, trust=False,
                      ignore_hard_deploy_errors=False)]
        configure_calls = [
            mock.call('newmodel', [
                'zaza.charm_tests.mycharm.setup.basic_setup'
                'zaza.charm_tests.othercharm.setup.setup'],
                test_directory=None),
            mock.call('newmodel', [
                'zaza.charm_tests.mycharm.setup.basic_setup'
                'zaza.charm_tests.othercharm.setup.setup'],
                test_directory=None)]
        test_calls = [
            mock.call('newmodel', [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest'],
                test_directory=None),
            mock.call('newmodel', [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest'],
                test_directory=None)]
        destroy_calls = [
            mock.call('newmodel'),
            mock.call('newmodel')]
        self.prepare.assert_has_calls(prepare_calls)
        self.deploy.assert_has_calls(deploy_calls)
        self.configure.assert_has_calls(configure_calls)
        self.test.assert_has_calls(test_calls)
        self.destroy.assert_has_calls(destroy_calls)

    def test_func_test_runner_cmr(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.before_deploy, 'before_deploy')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.patch_object(
            lc_func_test_runner.zaza.model,
            'block_until_all_units_idle')
        self.generate_model_name.return_value = 'newmodel'
        model_names = ['m6', 'm5', 'm4', 'm3', 'm2', 'm1']
        self.generate_model_name.side_effect = model_names.pop
        self.get_charm_config.return_value = {
            'charm_name': 'mycharm',
            'gate_bundles': [
                'bundle1',
                'bundle2',
                {'model_alias_5': 'bundle5', 'model_alias_6': 'bundle6'}],
            'smoke_bundles': ['bundle2'],
            'dev_bundles': ['bundle3', 'bundle4'],
            'configure': [
                'zaza.charm_tests.mycharm.setup.basic_setup',
                'zaza.charm_tests.othercharm.setup.setup',
                {'model_alias_5': [
                    'zaza.charm_tests.vault.setup.basic_setup1',
                    'zaza.charm_tests.vault.setup.basic_setup2'],
                 'model_alias_6': ['zaza.charm_tests.ks.setup.user_setup']}],
            'tests': [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest',
                {'model_alias_5': ['zaza.charm_tests.vault.test.decrpy'],
                 'model_alias_6': [
                     'zaza.charm_tests.ks.test.project_create1',
                     'zaza.charm_tests.ks.test.project_create2']}]}
        lc_func_test_runner.func_test_runner()
        prepare_calls = [
            mock.call('m1', test_directory=None),
            mock.call('m2', test_directory=None),
            mock.call('m3', test_directory=None),
            mock.call('m4', test_directory=None)]
        cwd = os.getcwd()
        deploy_calls = [
            mock.call(cwd + '/tests/bundles/bundle1.yaml', 'm1',
                      model_ctxt={'default_alias': 'm1'}, force=False,
                      test_directory=None, trust=False,
                      ignore_hard_deploy_errors=False),
            mock.call(cwd + '/tests/bundles/bundle2.yaml', 'm2',
                      model_ctxt={'default_alias': 'm2'}, force=False,
                      test_directory=None, trust=False,
                      ignore_hard_deploy_errors=False),
            mock.call(
                cwd + '/tests/bundles/bundle5.yaml',
                'm3',
                model_ctxt={'model_alias_5': 'm3', 'model_alias_6': 'm4'},
                force=False, test_directory=None, trust=False,
                ignore_hard_deploy_errors=False),
            mock.call(
                cwd + '/tests/bundles/bundle6.yaml',
                'm4',
                model_ctxt={'model_alias_5': 'm3', 'model_alias_6': 'm4'},
                force=False, test_directory=None, trust=False,
                ignore_hard_deploy_errors=False)]
        configure_calls = [
            mock.call('m1', [
                'zaza.charm_tests.mycharm.setup.basic_setup',
                'zaza.charm_tests.othercharm.setup.setup'],
                test_directory=None),
            mock.call('m2', [
                'zaza.charm_tests.mycharm.setup.basic_setup',
                'zaza.charm_tests.othercharm.setup.setup'],
                test_directory=None),
            mock.call('m3', [
                'zaza.charm_tests.vault.setup.basic_setup1',
                'zaza.charm_tests.vault.setup.basic_setup2'],
                test_directory=None),
            mock.call('m4', [
                'zaza.charm_tests.ks.setup.user_setup'],
                test_directory=None)]
        test_calls = [
            mock.call('m1', [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest'],
                test_directory=None),
            mock.call('m2', [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest'],
                test_directory=None),
            mock.call('m3', [
                'zaza.charm_tests.vault.test.decrpy'], test_directory=None),
            mock.call('m4', [
                'zaza.charm_tests.ks.test.project_create1',
                'zaza.charm_tests.ks.test.project_create2'],
                test_directory=None)]
        destroy_calls = [
            mock.call('m1'),
            mock.call('m2'),
            mock.call('m3'),
            mock.call('m4')]
        self.prepare.assert_has_calls(prepare_calls)
        self.deploy.assert_has_calls(deploy_calls)
        self.configure.assert_has_calls(configure_calls)
        self.test.assert_has_calls(test_calls)
        self.destroy.assert_has_calls(destroy_calls)

    def test_func_test_runner_with_before_script(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.before_deploy, 'before_deploy')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.patch_object(
            lc_func_test_runner.zaza.model,
            'block_until_all_units_idle')
        self.generate_model_name.return_value = 'newmodel'
        self.get_charm_config.return_value = {
            'charm_name': 'mycharm',
            'gate_bundles': ['bundle1', 'bundle2'],
            'smoke_bundles': ['bundle2'],
            'dev_bundles': ['bundle3', 'bundle4'],
            'before_deploy': [
                'zaza.charm_tests.prepare.first',
                'zaza.charm_tests.prepare.second'],
            'tests': [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest']}
        lc_func_test_runner.func_test_runner()
        cwd = os.getcwd()
        prepare_calls = [
            mock.call('newmodel', test_directory=None),
            mock.call('newmodel', test_directory=None)]
        deploy_calls = [
            mock.call(cwd + '/tests/bundles/bundle1.yaml', 'newmodel',
                      model_ctxt={'default_alias': 'newmodel'}, force=False,
                      test_directory=None, trust=False,
                      ignore_hard_deploy_errors=False),
            mock.call(cwd + '/tests/bundles/bundle2.yaml', 'newmodel',
                      model_ctxt={'default_alias': 'newmodel'}, force=False,
                      test_directory=None, trust=False,
                      ignore_hard_deploy_errors=False)]
        before_deploy_calls = [
            mock.call('newmodel', [
                'zaza.charm_tests.prepare.first',
                'zaza.charm_tests.prepare.second'],
                test_directory=None),
            mock.call('newmodel', [
                'zaza.charm_tests.prepare.first',
                'zaza.charm_tests.prepare.second'],
                test_directory=None)]
        test_calls = [
            mock.call('newmodel', [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest'],
                test_directory=None),
            mock.call('newmodel', [
                'zaza.charm_tests.mycharm.tests.SmokeTest',
                'zaza.charm_tests.mycharm.tests.ComplexTest'],
                test_directory=None)]
        destroy_calls = [
            mock.call('newmodel'),
            mock.call('newmodel')]
        self.prepare.assert_has_calls(prepare_calls)
        self.deploy.assert_has_calls(deploy_calls)
        self.before_deploy.assert_has_calls(before_deploy_calls)
        self.test.assert_has_calls(test_calls)
        self.destroy.assert_has_calls(destroy_calls)

    def test_func_test_runner_smoke(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.before_deploy, 'before_deploy')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.patch_object(
            lc_func_test_runner.zaza.model,
            'block_until_all_units_idle')
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
        cwd = os.getcwd()
        deploy_calls = [
            mock.call(cwd + '/tests/bundles/bundle2.yaml', 'newmodel',
                      model_ctxt={'default_alias': 'newmodel'},
                      force=False,
                      test_directory=None, trust=False,
                      ignore_hard_deploy_errors=False)]
        self.deploy.assert_has_calls(deploy_calls)

    def test_func_test_runner_dev(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.before_deploy, 'before_deploy')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.generate_model_name.return_value = 'newmodel'
        self.patch_object(
            lc_func_test_runner.zaza.model,
            'block_until_all_units_idle')
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
        cwd = os.getcwd()
        deploy_calls = [
            mock.call(cwd + '/tests/bundles/bundle3.yaml', 'newmodel',
                      model_ctxt={'default_alias': 'newmodel'}, force=False,
                      test_directory=None, trust=False,
                      ignore_hard_deploy_errors=False),
            mock.call(cwd + '/tests/bundles/bundle4.yaml', 'newmodel',
                      model_ctxt={'default_alias': 'newmodel'}, force=False,
                      test_directory=None, trust=False,
                      ignore_hard_deploy_errors=False)]
        self.deploy.assert_has_calls(deploy_calls)

    def test_func_test_runner_specify_bundle(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.before_deploy, 'before_deploy')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.patch_object(
            lc_func_test_runner.zaza.model,
            'block_until_all_units_idle')
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
        lc_func_test_runner.func_test_runner(bundles=['maveric-filebeat'])
        cwd = os.getcwd()
        deploy_calls = [
            mock.call(
                cwd + '/tests/bundles/maveric-filebeat.yaml',
                'newmodel',
                model_ctxt={'default_alias': 'newmodel'},
                force=False,
                test_directory=None, trust=False,
                ignore_hard_deploy_errors=False)]
        self.deploy.assert_has_calls(deploy_calls)

    def test_func_test_runner_specify_bundle_with_alias(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.before_deploy, 'before_deploy')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.patch_object(
            lc_func_test_runner.zaza.model,
            'block_until_all_units_idle')
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
        lc_func_test_runner.func_test_runner(
            bundles=['alias:maveric-filebeat'])
        cwd = os.getcwd()
        deploy_calls = [
            mock.call(
                cwd + '/tests/bundles/maveric-filebeat.yaml',
                'newmodel',
                model_ctxt={'alias': 'newmodel'},
                force=False,
                test_directory=None, trust=False,
                ignore_hard_deploy_errors=False)]
        self.deploy.assert_has_calls(deploy_calls)

    def test_func_test_runner_specify_bundle_with_implicit_alias(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.before_deploy, 'before_deploy')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.patch_object(
            lc_func_test_runner.zaza.model,
            'block_until_all_units_idle')
        self.generate_model_name.return_value = 'newmodel'
        self.get_charm_config.return_value = {
            'charm_name': 'mycharm',
            'gate_bundles': [{'alias': 'maveric-filebeat'}],
        }
        lc_func_test_runner.func_test_runner(
            bundles=['maveric-filebeat'])
        cwd = os.getcwd()
        deploy_calls = [
            mock.call(
                cwd + '/tests/bundles/maveric-filebeat.yaml',
                'newmodel',
                model_ctxt={'alias': 'newmodel'},
                force=False,
                test_directory=None, trust=False,
                ignore_hard_deploy_errors=False)]
        self.deploy.assert_has_calls(deploy_calls)

    def test_func_test_runner_cmr_specify_bundle_with_alias(self):
        self.patch_object(lc_func_test_runner.utils, 'get_charm_config')
        self.patch_object(lc_func_test_runner.utils, 'generate_model_name')
        self.patch_object(lc_func_test_runner.prepare, 'prepare')
        self.patch_object(lc_func_test_runner.before_deploy, 'before_deploy')
        self.patch_object(lc_func_test_runner.deploy, 'deploy')
        self.patch_object(lc_func_test_runner.configure, 'configure')
        self.patch_object(lc_func_test_runner.test, 'test')
        self.patch_object(lc_func_test_runner.destroy, 'destroy')
        self.patch_object(
            lc_func_test_runner.zaza.model,
            'block_until_all_units_idle')
        self.generate_model_name.side_effect = ['newmodel1', 'newmodel2']
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
        lc_func_test_runner.func_test_runner(
            bundles=['alias:maveric-filebeat',
                     'another_alias:maverick-things'])
        cwd = os.getcwd()
        deploy_calls = [
            mock.call(
                cwd + '/tests/bundles/maveric-filebeat.yaml',
                'newmodel1',
                model_ctxt={'alias': 'newmodel1',
                            'another_alias': 'newmodel2'},
                force=False,
                test_directory=None, trust=False,
                ignore_hard_deploy_errors=False),
            mock.call(
                cwd + '/tests/bundles/maverick-things.yaml',
                'newmodel2',
                model_ctxt={'alias': 'newmodel1',
                            'another_alias': 'newmodel2'},
                force=False,
                test_directory=None, trust=False,
                ignore_hard_deploy_errors=False)]
        self.deploy.assert_has_calls(deploy_calls)

    def test_main_smoke_dev_ambiguous(self):
        self.patch_object(lc_func_test_runner, 'parse_args')
        self.patch_object(lc_func_test_runner, 'cli_utils')
        self.patch_object(lc_func_test_runner, 'func_test_runner')
        self.patch_object(lc_func_test_runner, 'asyncio')
        self.patch_object(
            lc_func_test_runner.zaza.model,
            'block_until_all_units_idle')
        _args = mock.Mock()
        _args.loglevel = 'DEBUG'
        _args.keep_last_model = False
        _args.keep_all_models = False
        _args.keep_faulty_model = False
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
        _args.keep_last_model = False
        _args.keep_all_models = False
        _args.keep_faulty_model = False
        _args.dev = True
        _args.smoke = False
        _args.bundles = ['foo.yaml']
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
        _args.keep_last_model = False
        _args.keep_all_models = False
        _args.keep_faulty_model = False
        _args.dev = False
        _args.smoke = True
        _args.bundles = ['foo.yaml']
        self.parse_args.return_value = _args
        with self.assertRaises(ValueError) as context:
            lc_func_test_runner.main()
        self.assertEqual(
            ('Ambiguous arguments: --bundle and --smoke '
             'cannot be used together'),
            str(context.exception))

    def __keep_model_ambiguous(
        self, last_model=False, all_models=False, faulty_model=False
    ):
        self.patch_object(lc_func_test_runner, 'parse_args')
        self.patch_object(lc_func_test_runner, 'cli_utils')
        self.patch_object(lc_func_test_runner, 'func_test_runner')
        self.patch_object(lc_func_test_runner, 'asyncio')
        _args = mock.Mock()
        _args.loglevel = 'DEBUG'
        _args.keep_last_model = last_model
        _args.keep_all_models = all_models
        _args.keep_faulty_model = faulty_model
        self.parse_args.return_value = _args
        with self.assertRaises(ValueError) as context:
            lc_func_test_runner.main()
        self.assertEqual(
            ('Ambiguous arguments: --keep-last-model '
             '(previously, --keep-model), --keep-all-models '
             'and --keep-faulty-model cannot be used together'),
            str(context.exception))

    def test_main_bundle_keep_model_ambiguous_case1(self):
        self.__keep_model_ambiguous(True, True, False)

    def test_main_bundle_keep_model_ambiguous_case2(self):
        self.__keep_model_ambiguous(True, False, True)

    def test_main_bundle_keep_model_ambiguous_case3(self):
        self.__keep_model_ambiguous(False, True, True)
