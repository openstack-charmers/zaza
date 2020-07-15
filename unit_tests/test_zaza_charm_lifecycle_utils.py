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

import io
import mock
import subprocess

import zaza.charm_lifecycle.utils as lc_utils
import unit_tests.utils as ut_utils


class TestCharmLifecycleUtils(ut_utils.BaseTestCase):

    def test__concat_model_alias_maps(self):
        # - test1
        self.assertEqual(
            lc_utils._concat_model_alias_maps(['test1']),
            {'default_alias': ['test1']})
        # - test1
        # - test2
        self.assertEqual(
            lc_utils._concat_model_alias_maps(['test1', 'test2']),
            {'default_alias': ['test1', 'test2']})
        # - default_alias1:
        #   - test1
        self.assertEqual(
            lc_utils._concat_model_alias_maps([{'default_alias': ['test1']}]),
            {'default_alias': ['test1']})
        # - test1
        # - test2
        # - model_alias1:
        #   - test3
        # - model_alias2:
        #   - test4
        self.assertEqual(
            lc_utils._concat_model_alias_maps(
                [
                    'test1',
                    'test2',
                    {
                        'model_alias1': ['test3']},
                    {
                        'model_alias2': ['test4']}]),
            {
                'default_alias': ['test1', 'test2'],
                'model_alias1': ['test3'],
                'model_alias2': ['test4']})

    def test_get_default_env_deploy_name(self):
        self.assertEqual(
            lc_utils.get_default_env_deploy_name(reset_count=True),
            'default1')

    def test_get_deployment_type_raw(self):
        self.assertEqual(
            lc_utils.get_deployment_type('xenial-keystone'),
            lc_utils.RAW_BUNDLE)

    def test_get_deployment_type_multi_ordered(self):
        self.assertEqual(
            lc_utils.get_deployment_type({
                'model_alias1': 'bundle1',
                'model_alias2': 'bundle2'}),
            lc_utils.MUTLI_UNORDERED)

    def test_get_deployment_type_single_aliased(self):
        self.assertEqual(
            lc_utils.get_deployment_type(
                {'model_alias1': 'bundle1'}),
            lc_utils.SINGLE_ALIASED)

    def test_get_deployment_type_multi_unordered(self):
        self.assertEqual(
            lc_utils.get_deployment_type({
                'env-test-alias': [
                    {'model_alias1': 'bundle1'},
                    {'model_alias2': 'bundle2'}]}),
            lc_utils.MUTLI_ORDERED)

    def test_get_config_options(self):
        self.patch_object(lc_utils, 'get_charm_config')
        self.get_charm_config.return_value = {
            'configure_options': {
                'a.module.function.path.key': 'aValue',
            }
        }
        self.assertEqual(
            lc_utils.get_config_options(),
            {'a.module.function.path.key': 'aValue'})

    def test_get_config_steps(self):
        self.patch_object(lc_utils, "get_charm_config")
        self.get_charm_config.return_value = {
            'configure': [
                'conf.class1',
                'conf.class2',
                {'model_alias1': ['conf.class3']}]}
        self.assertEqual(
            lc_utils.get_config_steps(),
            {'default_alias': ['conf.class1', 'conf.class2'],
             'model_alias1': ['conf.class3']})

    def test_get_test_steps(self):
        self.patch_object(lc_utils, "get_charm_config")
        self.get_charm_config.return_value = {
            'tests': [
                'test.class1',
                'test.class2',
                {'model_alias1': ['test.class3']}]}
        self.assertEqual(
            lc_utils.get_test_steps(),
            {'default_alias': ['test.class1', 'test.class2'],
             'model_alias1': ['test.class3']})

    def test_get_environment_deploys(self):
        self.patch_object(lc_utils, 'get_charm_config')
        charm_config = {
            'smoke_bundles': ['map1', 'map2', 'map3']}
        self.patch_object(lc_utils, 'get_environment_deploy')
        env_depl1 = lc_utils.EnvironmentDeploy('ed1', [], True)
        env_depl2 = lc_utils.EnvironmentDeploy('ed2', [], True)
        env_depl3 = lc_utils.EnvironmentDeploy('ed3', [], True)
        env_deploys = {
            'map1': env_depl1,
            'map2': env_depl2,
            'map3': env_depl3
        }
        self.get_charm_config.return_value = charm_config
        self.get_environment_deploy.side_effect = lambda x: env_deploys[x]
        self.assertEqual(
            lc_utils.get_environment_deploys('smoke_bundles'),
            [env_depl1, env_depl2, env_depl3])

    def test_get_environment_deploy_single_aliased(self):
        self.patch_object(
            lc_utils,
            'generate_model_name',
            return_value='zaza-model-1')
        self.patch_object(
            lc_utils,
            'get_default_env_deploy_name',
            return_value='env-alias-1')
        expect = lc_utils.EnvironmentDeploy(
            'env-alias-1',
            [lc_utils.ModelDeploy('alias', 'zaza-model-1', 'bundle')],
            True)
        self.assertEqual(
            lc_utils.get_environment_deploy_single_aliased(
                {'alias': 'bundle'}),
            expect)

    def test_generate_model_name(self):
        self.patch_object(lc_utils.uuid, "uuid4")
        self.uuid4.return_value = "longer-than-12characters"
        self.assertEqual(lc_utils.generate_model_name(),
                         "zaza-12characters")

    def test_get_charm_config(self):
        self.patch("builtins.open",
                   new_callable=mock.mock_open(),
                   name="_open")
        self.patch_object(lc_utils, 'yaml')
        _yaml = "testconfig: someconfig"
        _yaml_dict = {'test_config': 'someconfig'}
        self.yaml.safe_load.return_value = _yaml_dict
        _filename = "filename"
        _fileobj = mock.MagicMock()
        _fileobj.__enter__.return_value = _yaml
        self._open.return_value = _fileobj

        self.assertEqual(lc_utils.get_charm_config(yaml_file=_filename),
                         _yaml_dict)
        self._open.assert_called_once_with(_filename, "r")
        self.yaml.safe_load.assert_called_once_with(_yaml)
        self._open.side_effect = FileNotFoundError
        self.patch_object(lc_utils.os, 'getcwd')
        self.getcwd.return_value = '/absoulte/path/to/fakecwd'
        with self.assertRaises(FileNotFoundError):
            lc_utils.get_charm_config()
        self.assertEqual(lc_utils.get_charm_config(fatal=False),
                         {'charm_name': 'fakecwd'})
        self.getcwd.return_value = '/absoulte/path/to/charm-fakecwd'
        self.assertEqual(lc_utils.get_charm_config(fatal=False),
                         {'charm_name': 'fakecwd'})

    def test_is_config_deploy_forced_for_bundle(self):
        self.patch_object(lc_utils, 'get_charm_config')
        # test that no options at all returns value
        self.get_charm_config.return_value = {}
        self.assertFalse(lc_utils.is_config_deploy_forced_for_bundle('x'))
        # test that if options exist but no bundle
        self.get_charm_config.return_value = {
            'tests_options': {}
        }
        self.assertFalse(lc_utils.is_config_deploy_forced_for_bundle('x'))
        self.get_charm_config.return_value = {
            'tests_options': {
                'force_deploy': []
            }
        }
        self.assertFalse(lc_utils.is_config_deploy_forced_for_bundle('x'))
        # verify that it returns True if the bundle is mentioned
        self.get_charm_config.return_value = {
            'tests_options': {
                'force_deploy': ['x']
            }
        }
        self.assertTrue(lc_utils.is_config_deploy_forced_for_bundle('x'))

    def test_get_class(self):
        self.assertEqual(
            type(lc_utils.get_class('unit_tests.'
                                    'test_zaza_charm_lifecycle_utils.'
                                    'TestCharmLifecycleUtils')()),
            type(self))

    def test_check_output_logging(self):
        self.patch_object(lc_utils.logging, 'info')
        self.patch_object(lc_utils.subprocess, 'Popen')
        popen_mock = mock.MagicMock()
        popen_mock.stdout = io.StringIO("logline1\nlogline2\nlogline3\n")
        poll_output = [0, 0, None, None, None]
        popen_mock.poll.side_effect = poll_output.pop
        self.Popen.return_value = popen_mock
        lc_utils.check_output_logging(['cmd', 'arg1', 'arg2'])
        log_calls = [
            mock.call('logline1'),
            mock.call('logline2'),
            mock.call('logline3')]
        self.info.assert_has_calls(log_calls)

    def test_check_output_logging_process_error(self):
        self.patch_object(lc_utils.logging, 'info')
        self.patch_object(lc_utils.subprocess, 'Popen')
        popen_mock = mock.MagicMock()
        popen_mock.stdout = io.StringIO("logline1\n")
        poll_output = [1, 1, None]
        popen_mock.poll.side_effect = poll_output.pop
        self.Popen.return_value = popen_mock
        with self.assertRaises(subprocess.CalledProcessError):
            lc_utils.check_output_logging(['cmd', 'arg1', 'arg2'])
