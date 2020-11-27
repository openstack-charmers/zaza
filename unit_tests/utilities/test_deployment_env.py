# Copyright 2019 Canonical Ltd.
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

import copy
import mock
import yaml

import zaza.utilities.deployment_env as deployment_env
import unit_tests.utils as ut_utils


class TestUtilitiesDeploymentEnv(ut_utils.BaseTestCase):

    MODEL_CONFIG_DEFAULTS = deployment_env.MODEL_DEFAULTS
    MODEL_DEFAULT_CONSTRAINTS = deployment_env.MODEL_DEFAULT_CONSTRAINTS

    def test_parse_option_list_string_empty_config(self):
        self.assertEqual(
            deployment_env.parse_option_list_string(option_list=""),
            {})

    def test_parse_option_list_string_single_value(self):
        self.assertEqual(
            deployment_env.parse_option_list_string(
                option_list='image-stream=released'),
            {'image-stream': 'released'})

    def test_parse_option_list_string_multiple_values(self):
        self.assertEqual(
            deployment_env.parse_option_list_string(
                option_list='image-stream=released;no-proxy=jujucharms.com'),
            {
                'image-stream': 'released',
                'no-proxy': 'jujucharms.com'})

    def test_parse_option_list_string_whitespace(self):
        self.assertEqual(
            deployment_env.parse_option_list_string(
                option_list=' test-mode= false ; image-stream=  released'),
            {
                'test-mode': 'false',
                'image-stream': 'released'})

    def base_get_model_settings(self, env, expect):
        with mock.patch.dict(deployment_env.os.environ, env):
            self.assertEqual(deployment_env.get_model_settings(), expect)

    def test_get_model_settings_no_config(self):
        self.base_get_model_settings({}, self.MODEL_CONFIG_DEFAULTS)

    def test_get_model_settings_multiple_values_override(self):
        expect_config = copy.deepcopy(self.MODEL_CONFIG_DEFAULTS)
        expect_config.update({'test-mode': 'false'})
        self.base_get_model_settings(
            {'MODEL_SETTINGS': 'test-mode=false'},
            expect_config)

    def test_get_model_settings_file_override(self):
        expect_config = copy.deepcopy(self.MODEL_CONFIG_DEFAULTS)
        expect_config.update({'default-series': 'file-setting'})
        self.patch_object(
            deployment_env,
            'get_setup_file_section',
            return_value={'default-series': 'file-setting'})
        self.base_get_model_settings({}, expect_config)

    def test_get_model_settings_file_override_env_override(self):
        # Check that env variables override defaults and file
        expect_config = copy.deepcopy(self.MODEL_CONFIG_DEFAULTS)
        expect_config.update({'default-series': 'env-setting'})
        self.patch_object(
            deployment_env,
            'get_setup_file_section',
            return_value={'default-series': 'file-setting'})
        self.base_get_model_settings(
            {'MODEL_SETTINGS': 'default-series=env-setting'},
            expect_config)

    def base_get_model_constraints(self, env, expect):
        with mock.patch.dict(deployment_env.os.environ, env):
            self.assertEqual(deployment_env.get_model_constraints(), expect)

    def test_get_model_constraints_no_config(self):
        self.base_get_model_constraints({}, self.MODEL_DEFAULT_CONSTRAINTS)

    def test_get_model_constraints_multiple_values_override(self):
        expect_config = copy.deepcopy(self.MODEL_DEFAULT_CONSTRAINTS)
        expect_config.update({'mem': 'from-env'})
        self.base_get_model_constraints(
            {'MODEL_CONSTRAINTS': 'mem=from-env'},
            expect_config)

    def test_get_model_constraints_file_override(self):
        expect_config = copy.deepcopy(self.MODEL_DEFAULT_CONSTRAINTS)
        expect_config.update({'mem': 'from-file'})
        self.patch_object(
            deployment_env,
            'get_setup_file_section',
            return_value={'mem': 'from-file'})
        self.base_get_model_constraints({}, expect_config)

    def test_get_model_constraints_file_override_env_override(self):
        # Check that env variables override defaults and file
        expect_config = copy.deepcopy(self.MODEL_DEFAULT_CONSTRAINTS)
        expect_config.update({'mem': 'from-env'})
        self.patch_object(
            deployment_env,
            'get_setup_file_section',
            return_value={'mem': 'from-file'})
        self.base_get_model_constraints(
            {'MODEL_CONSTRAINTS': 'mem=from-env'},
            expect_config)

    def test_is_valid_env_key(self):
        self.assertTrue(deployment_env.is_valid_env_key('TEST_VIP04'))
        self.assertTrue(deployment_env.is_valid_env_key('TEST_FIP_RANGE'))
        self.assertTrue(deployment_env.is_valid_env_key('TEST_GATEWAY'))
        self.assertTrue(deployment_env.is_valid_env_key('TEST_NAME_SERVER'))
        self.assertTrue(deployment_env.is_valid_env_key('TEST_NET_ID'))
        self.assertTrue(deployment_env.is_valid_env_key('TEST_VIP_RANGE'))
        self.assertFalse(
            deployment_env.is_valid_env_key('ZAZA_TEMPLATE_VIP00'))
        self.assertFalse(deployment_env.is_valid_env_key('PATH'))

    def test_find_setup_file(self):
        self.patch_object(
            deployment_env.os.path,
            'isfile',
            return_value=True)
        with mock.patch.dict(deployment_env.os.environ,
                             {'HOME': '/home/testuser'}):
            self.assertEqual(
                deployment_env.find_setup_file(),
                '/home/testuser/.zaza.yaml')

    def test_get_setup_file_contents(self):
        self.patch_object(
            deployment_env,
            'find_setup_file',
            return_value='/home/testuser/.zaza.yaml')
        self.patch("builtins.open",
                   new_callable=mock.mock_open(),
                   name="_open")
        self.patch_object(deployment_env, 'yaml')
        _yaml = "testconfig: someconfig"
        _yaml_dict = {'test_config': 'someconfig'}
        self.yaml.safe_load.return_value = _yaml_dict
        _fileobj = mock.MagicMock()
        _fileobj.__enter__.return_value = _yaml
        self._open.return_value = _fileobj

        self.assertEqual(
            deployment_env.get_setup_file_contents(),
            _yaml_dict)
        self._open.assert_called_once_with('/home/testuser/.zaza.yaml', "r")
        self.yaml.safe_load.assert_called_once_with(_yaml)

    def test_get_setup_file_contents_yaml_error(self):
        self.patch_object(deployment_env, 'logging')
        self.patch_object(
            deployment_env,
            'find_setup_file',
            return_value='/home/testuser/.zaza.yaml')
        self.patch("builtins.open",
                   new_callable=mock.mock_open(),
                   name="_open")
        self.patch_object(deployment_env.yaml, 'safe_load')
        self.safe_load.side_effect = yaml.YAMLError

        _fileobj = mock.MagicMock()
        _fileobj.__enter__.return_value = ''
        self._open.return_value = _fileobj

        self.assertEqual(
            deployment_env.get_setup_file_contents(),
            {})

    def test_get_setup_file_section(self):
        self.patch_object(
            deployment_env,
            'get_setup_file_contents',
            return_value={
                'secrets': {'setting1': 'value1'}})
        self.assertEqual(
            deployment_env.get_setup_file_section('secrets'),
            {'setting1': 'value1'})
        self.assertEqual(
            deployment_env.get_setup_file_section('absent-section'),
            {})

    def test_get_deployment_context(self):
        self.patch_object(deployment_env.os, 'environ')
        self.patch_object(
            deployment_env,
            'get_setup_file_contents',
            return_value={'runtime_config': {
                'OS_SETTING1': 'from-file',
                'OS_SETTING2': 'from-file'}})
        self.environ.items.return_value = [
            ('AMULET_OS_VIP', '10.10.0.2'),
            ('TEST_VIP', '10.10.0.1'),
            ('OS_SETTING2', 'from-env'),
            ('TEST_VIP04', '10.10.0.4'),
            ('ZAZA_TEMPLATE_VIP00', '20.3.4.5'),
            ('PATH', 'aa')]
        self.assertEqual(
            deployment_env.get_deployment_context(),
            {'TEST_VIP': '10.10.0.1',
             'TEST_VIP04': '10.10.0.4',
             'OS_SETTING1': 'from-file',
             'OS_SETTING2': 'from-env'}
        )

    def test_get_cloud_region(self):
        self.patch_object(
            deployment_env,
            'get_setup_file_contents',
            return_value={
                'region': 'test'})
        self.assertEqual(
            deployment_env.get_cloud_region(),
            'test')

    def test_get_cloud_region_default(self):
        self.patch_object(
            deployment_env,
            'get_setup_file_contents',
            return_value={})
        self.assertEqual(
            deployment_env.get_cloud_region(),
            None)

    def test_get_tmpdir(self):
        self.patch_object(deployment_env.os, 'mkdir')
        self.patch_object(deployment_env.os.path, 'exists')
        self.exists.return_value = False
        deployment_env.get_tmpdir(model_name='mymodel')
        self.mkdir.assert_called_once_with('/tmp/mymodel')
        self.mkdir.reset_mock()
        self.exists.return_value = True
        deployment_env.get_tmpdir(model_name='mymodel')
        self.assertFalse(self.mkdir.called)
