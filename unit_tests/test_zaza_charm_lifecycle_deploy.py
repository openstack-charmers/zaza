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

import jinja2
import mock

import zaza.charm_lifecycle.deploy as lc_deploy
import zaza.utilities.exceptions as zaza_exceptions
import unit_tests.utils as ut_utils


class TestCharmLifecycleDeploy(ut_utils.BaseTestCase):

    def test_get_template_overlay_context(self):
        self.patch_object(lc_deploy.deployment_env, 'get_deployment_context')
        self.patch_object(lc_deploy, 'get_charm_config_context')
        self.get_deployment_context.return_value = {
            'OS_VIP04': '10.10.0.2'}
        self.get_charm_config_context.return_value = {
            'charm_location': '../../../mycharm',
            'charm_name': 'mycharm'}
        self.assertEqual(
            lc_deploy.get_template_overlay_context(),
            {
                'OS_VIP04': '10.10.0.2',
                'charm_location': '../../../mycharm',
                'charm_name': 'mycharm'})

    def test_get_charm_config_context(self):
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        self.patch_object(lc_deploy.os.path, 'abspath')
        self.get_charm_config.return_value = {
            'charm_name': 'mycharm'}
        self.abspath.return_value = '/some/absolute/path'
        self.assertEqual(
            lc_deploy.get_charm_config_context(),
            {'charm_location': '/some/absolute/path/../../../mycharm',
             'charm_name': 'mycharm'})

    def test_get_overlay_template_dir(self):
        self.assertEqual(
            lc_deploy.get_overlay_template_dir(),
            'tests/bundles/overlays')

    def test_get_jinja2_loader(self):
        self.patch_object(lc_deploy, 'get_overlay_template_dir')
        self.patch_object(lc_deploy.os, 'path')
        self.patch_object(lc_deploy.zaza.controller, 'get_cloud_type')
        self.get_overlay_template_dir.return_value = 'mytemplatedir'
        self.patch_object(lc_deploy.jinja2, 'ChoiceLoader')
        self.patch_object(lc_deploy.jinja2, 'FileSystemLoader')
        self.path.join.return_value = 'mytemplatedir/someprovider'
        self.path.exists.return_value = False
        self.path.isdir.return_value = False
        lc_deploy.get_jinja2_loader()
        self.assertFalse(self.ChoiceLoader.called)
        self.FileSystemLoader.assert_called_once_with('mytemplatedir')
        self.path.exists.return_value = True
        self.path.isdir.return_value = True
        self.FileSystemLoader.reset_mock()
        self.FileSystemLoader.side_effect = [
            'mytemplatedir/someprovider', 'mytemplatedir']
        lc_deploy.get_jinja2_loader()
        self.ChoiceLoader.assert_called_once_with(
            ['mytemplatedir/someprovider', 'mytemplatedir'])
        self.FileSystemLoader.assert_has_calls([
            mock.call('mytemplatedir/someprovider'),
            mock.call('mytemplatedir'),
        ])

    def test_get_jinja2_env(self):
        self.patch_object(lc_deploy, 'get_jinja2_loader')
        self.patch_object(lc_deploy.jinja2, 'Environment')
        jinja_env_mock = mock.MagicMock()
        self.Environment.return_value = jinja_env_mock
        self.assertEqual(
            lc_deploy.get_jinja2_env(),
            jinja_env_mock)
        self.get_jinja2_loader.assert_called_once_with(
            template_dir=None)

    def test_get_template_name(self):
        self.assertEqual(
            lc_deploy.get_template_name('mybundles/mybundle.yaml'),
            'mybundle.yaml.j2')

    def test_get_template(self):
        self.patch_object(lc_deploy, 'get_jinja2_env')
        jinja_env_mock = mock.MagicMock()
        self.get_jinja2_env.return_value = jinja_env_mock
        jinja_env_mock.get_template.return_value = 'mytemplate'
        self.assertEqual(
            lc_deploy.get_template('mybundle.yaml'),
            'mytemplate')

    def test_get_template_missing_template(self):
        self.patch_object(lc_deploy, 'get_jinja2_env')
        jinja_env_mock = mock.MagicMock()
        self.get_jinja2_env.return_value = jinja_env_mock
        jinja_env_mock.get_template.side_effect = \
            jinja2.exceptions.TemplateNotFound(name='bob')
        self.assertIsNone(lc_deploy.get_template('mybundle.yaml'))

    def test_render_template(self):
        self.patch_object(lc_deploy, 'get_template_overlay_context',
                          return_value={})
        template_mock = mock.MagicMock()
        template_mock.render.return_value = 'Template contents'
        m = mock.mock_open()
        with mock.patch('zaza.charm_lifecycle.deploy.open', m, create=True):
            lc_deploy.render_template(template_mock, '/tmp/mybundle.yaml')
        m.assert_called_once_with('/tmp/mybundle.yaml', 'w')
        handle = m()
        handle.write.assert_called_once_with('Template contents')

    def test_render_overlay(self):
        self.patch_object(lc_deploy, 'render_template')
        template_mock = mock.MagicMock()
        self.patch_object(lc_deploy, 'get_template')
        self.get_template.return_value = template_mock
        lc_deploy.render_overlay('my_overlay.yaml', '/tmp/special-dir')
        self.render_template.assert_called_once_with(
            template_mock,
            '/tmp/special-dir/my_overlay.yaml',
            model_ctxt=None)

    def test_template_missing_required_variables(self):
        self.patch_object(lc_deploy, 'get_template_overlay_context')
        self.get_template_overlay_context.return_value = {}
        self.patch_object(lc_deploy.sys, 'exit')
        self.patch_object(lc_deploy.logging, 'error')
        self.patch_object(lc_deploy, 'get_jinja2_loader', return_value=None)
        jinja2_env = lc_deploy.get_jinja2_env()
        template = jinja2_env.from_string('{{required_variable}}')
        m = mock.mock_open()
        with mock.patch('zaza.charm_lifecycle.deploy.open', m, create=True):
            lc_deploy.render_template(template, '/tmp/mybundle.yaml')
        m.assert_called_once_with('/tmp/mybundle.yaml', 'w')
        self.error.assert_called_once_with(
            "Template error. You may be missing"
            " a mandatory environment variable : "
            "'required_variable' is undefined")
        self.exit.assert_called_once_with(1)

    def test_render_overlay_no_template(self):
        self.patch_object(lc_deploy, 'get_template')
        self.get_template.return_value = None
        self.assertIsNone(lc_deploy.render_overlay('mybundle.yaml', '/tmp/'))

    def test_render_local_overlay(self):
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        self.get_charm_config.return_value = {
            'charm_name': 'mycharm'}
        self.patch_object(lc_deploy.jinja2, 'Environment')
        self.patch_object(lc_deploy, 'get_template', return_value='atemplate')
        self.patch_object(lc_deploy, 'render_template')
        self.assertEqual(
            lc_deploy.render_local_overlay('/target'),
            '/target/local-charm-overlay.yaml')
        self.assertFalse(self.Environment.called)
        self.render_template.assert_called_once_with(
            'atemplate',
            '/target/local-charm-overlay.yaml',
            model_ctxt=None)

    def test_render_local_overlay_default(self):
        jenv_mock = mock.MagicMock()
        jenv_mock.from_string.return_value = 'atemplate'
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        self.get_charm_config.return_value = {
            'charm_name': 'mycharm'}
        self.patch_object(lc_deploy.jinja2, 'Environment',
                          return_value=jenv_mock)
        self.patch_object(lc_deploy, 'get_template', return_value=None)
        self.patch_object(lc_deploy, 'render_template')
        self.assertEqual(
            lc_deploy.render_local_overlay('/target'),
            '/target/local-charm-overlay.yaml')
        jenv_mock.from_string.assert_called_once_with(mock.ANY)
        self.render_template.assert_called_once_with(
            'atemplate',
            '/target/local-charm-overlay.yaml',
            model_ctxt=None)

    def yaml_read_patch(self, yaml, yaml_dict):
        self.patch("builtins.open",
                   new_callable=mock.mock_open(),
                   name="_open")
        self.patch_object(lc_deploy, 'yaml')
        self.yaml.safe_load.return_value = yaml_dict
        _fileobj = mock.MagicMock()
        _fileobj.__enter__.return_value = yaml
        self._open.return_value = _fileobj

    def test_is_local_overlay_enabled_in_bundle_in_bundle_unset(self):
        _yaml = "testconfig: someconfig"
        _yaml_dict = {'test_config': 'someconfig'}
        _filename = "filename"
        self.yaml_read_patch(_yaml, _yaml_dict)

        self.assertTrue(
            lc_deploy.is_local_overlay_enabled_in_bundle(_filename))
        self._open.assert_called_once_with(_filename, "r")
        self.yaml.safe_load.assert_called_once_with(_yaml)

    def test_is_local_overlay_enabled_in_bundle_disabled(self):
        _yaml = "local_overlay_enabled: False"
        _yaml_dict = {'local_overlay_enabled': False}
        _filename = "filename"
        self.yaml_read_patch(_yaml, _yaml_dict)

        self.assertFalse(
            lc_deploy.is_local_overlay_enabled_in_bundle(_filename))
        self._open.assert_called_once_with(_filename, "r")
        self.yaml.safe_load.assert_called_once_with(_yaml)

    def test_is_local_overlay_enabled_in_bundle_enabled(self):
        _yaml = "local_overlay_enabled: True"
        _yaml_dict = {'local_overlay_enabled': True}
        _filename = "filename"
        self.yaml_read_patch(_yaml, _yaml_dict)

        self.assertTrue(
            lc_deploy.is_local_overlay_enabled_in_bundle(_filename))
        self._open.assert_called_once_with(_filename, "r")

    def test_should_render_local_overlay(self):
        self.patch_object(
            lc_deploy.os.path,
            'isfile',
            return_value=True)
        self.patch_object(
            lc_deploy,
            'is_local_overlay_enabled_in_bundle',
            return_value=True)
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        _bundle = "bundle.yaml"

        # File exists no bundle override
        self.assertTrue(lc_deploy.should_render_local_overlay(_bundle))

        # File exists bundle overrides False
        self.is_local_overlay_enabled_in_bundle.return_value = False
        self.assertFalse(lc_deploy.should_render_local_overlay(_bundle))

        # No file, charm_name present
        self.isfile.return_value = False
        self.get_charm_config.return_value = {"charm_name": "CHARM"}
        self.assertTrue(lc_deploy.should_render_local_overlay(_bundle))

        # No file, charm_name not present
        self.isfile.return_value = False
        self.get_charm_config.return_value = {}
        self.assertFalse(lc_deploy.should_render_local_overlay(_bundle))

    def test_render_overlays(self):
        RESP = {
            'mybundles/mybundle.yaml': '/tmp/mybundle.yaml'}
        self.patch_object(
            lc_deploy,
            'is_local_overlay_enabled_in_bundle',
            return_value=True)
        self.patch_object(lc_deploy, 'render_local_overlay')
        self.render_local_overlay.return_value = '/tmp/local-overlay.yaml'
        self.patch_object(lc_deploy, 'render_overlay')
        self.render_overlay.side_effect = lambda x, y, model_ctxt: RESP[x]
        self.assertEqual(
            lc_deploy.render_overlays('mybundles/mybundle.yaml', '/tmp'),
            ['/tmp/local-overlay.yaml', '/tmp/mybundle.yaml'])

    def test_render_overlays_missing(self):
        RESP = {'mybundles/mybundle.yaml': None}
        self.patch_object(
            lc_deploy,
            'is_local_overlay_enabled_in_bundle',
            return_value=True)
        self.patch_object(lc_deploy, 'render_overlay')
        self.patch_object(lc_deploy, 'render_local_overlay')
        self.render_local_overlay.return_value = '/tmp/local.yaml'
        self.render_overlay.side_effect = lambda x, y, model_ctxt: RESP[x]
        self.assertEqual(
            lc_deploy.render_overlays('mybundles/mybundle.yaml', '/tmp'),
            ['/tmp/local.yaml'])

    def test_render_overlays_no_local(self):
        RESP = {
            'mybundles/mybundle.yaml': '/tmp/mybundle.yaml'}
        self.patch_object(
            lc_deploy,
            'is_local_overlay_enabled_in_bundle',
            return_value=False)
        self.patch_object(lc_deploy, 'render_local_overlay')
        self.render_local_overlay.return_value = '/tmp/local-overlay.yaml'
        self.patch_object(lc_deploy, 'render_overlay')
        self.render_overlay.side_effect = lambda x, y, model_ctxt: RESP[x]
        self.assertEqual(
            lc_deploy.render_overlays('mybundles/mybundle.yaml', '/tmp'),
            ['/tmp/mybundle.yaml'])

    def test_deploy_bundle(self):
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        self.get_charm_config.return_value = {}
        self.patch_object(lc_deploy.tempfile, 'TemporaryDirectory')
        enter_mock = mock.MagicMock()
        enter_mock.__enter__.return_value = '/tmp/mytmpdir'
        self.TemporaryDirectory.return_value = enter_mock
        self.patch_object(lc_deploy, 'render_overlays')
        self.patch_object(lc_deploy.utils, 'check_output_logging')
        self.render_overlays.return_value = []
        lc_deploy.deploy_bundle(
            './tests/bundles/bionic.yaml',
            'newmodel',
            force=True)
        self.check_output_logging.assert_called_once_with(
            ['juju', 'deploy', '-m', 'newmodel', '--force',
             './tests/bundles/bionic.yaml'])

    def test_deploy_bundle_template(self):
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        self.patch_object(lc_deploy, 'get_template')
        self.get_template.return_value = './tests/bundles/bionic.yaml.j2'
        self.patch_object(lc_deploy.os.path, 'exists')
        self.exists.return_value = False
        self.patch_object(lc_deploy, 'render_template')
        self.render_template.return_value = '/tmp/mytmpdir/bionic.yaml'
        self.get_charm_config.return_value = {}
        self.patch_object(lc_deploy.tempfile, 'TemporaryDirectory')
        enter_mock = mock.MagicMock()
        enter_mock.__enter__.return_value = '/tmp/mytmpdir'
        self.TemporaryDirectory.return_value = enter_mock
        self.patch_object(lc_deploy, 'render_overlays')
        self.patch_object(lc_deploy.utils, 'check_output_logging')
        self.render_overlays.return_value = []
        lc_deploy.deploy_bundle(
            './tests/bundles/bionic.yaml',
            'newmodel',
            force=True)
        self.check_output_logging.assert_called_once_with(
            ['juju', 'deploy', '-m', 'newmodel', '--force',
             '/tmp/mytmpdir/bionic.yaml'])
        self.get_template.assert_called_once_with(
            './tests/bundles/bionic.yaml',
            template_dir='./tests/bundles')
        self.render_template.assert_called_once_with(
            './tests/bundles/bionic.yaml.j2',
            '/tmp/mytmpdir/bionic.yaml',
            model_ctxt=None)

    def test_deploy_bundle_template_conflict(self):
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        template_mock = mock.MagicMock()
        template_mock.filename = './tests/bundles/bionic.yaml.j2'
        self.patch_object(lc_deploy, 'get_template')
        self.get_template.return_value = template_mock
        self.patch_object(lc_deploy.os.path, 'exists')
        self.exists.return_value = True
        self.get_charm_config.return_value = {}
        self.patch_object(lc_deploy.tempfile, 'TemporaryDirectory')
        enter_mock = mock.MagicMock()
        enter_mock.__enter__.return_value = '/tmp/mytmpdir'
        self.TemporaryDirectory.return_value = enter_mock
        with self.assertRaises(zaza_exceptions.TemplateConflict):
            lc_deploy.deploy_bundle(
                './tests/bundles/bionic.yaml',
                'newmodel',
                force=True)

    def test_deploy(self):
        self.patch_object(lc_deploy.zaza.model, 'wait_for_application_states')
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        self.get_charm_config.return_value = {}
        self.patch_object(lc_deploy, 'deploy_bundle')
        lc_deploy.deploy('bun.yaml', 'newmodel')
        self.deploy_bundle.assert_called_once_with('bun.yaml', 'newmodel',
                                                   model_ctxt=None,
                                                   force=False)
        self.wait_for_application_states.assert_called_once_with(
            'newmodel',
            {},
            timeout=3600)

    def test_deploy_bespoke_states(self):
        self.patch_object(lc_deploy.zaza.model, 'wait_for_application_states')
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        self.get_charm_config.return_value = {
            'target_deploy_status': {
                'vault': {
                    'workload-status': 'blocked',
                    'workload-status-message': 'Vault needs to be inited'}}}
        self.patch_object(lc_deploy, 'deploy_bundle')
        lc_deploy.deploy('bun.yaml', 'newmodel')
        self.deploy_bundle.assert_called_once_with('bun.yaml', 'newmodel',
                                                   model_ctxt=None,
                                                   force=False)
        self.wait_for_application_states.assert_called_once_with(
            'newmodel',
            {'vault': {
                'workload-status': 'blocked',
                'workload-status-message': 'Vault needs to be inited'}},
            timeout=3600)

    def test_deploy_nowait(self):
        self.patch_object(lc_deploy.zaza.model, 'wait_for_application_states')
        self.patch_object(lc_deploy, 'deploy_bundle')
        lc_deploy.deploy('bun.yaml', 'newmodel', wait=False)
        self.deploy_bundle.assert_called_once_with('bun.yaml', 'newmodel',
                                                   model_ctxt=None,
                                                   force=False)
        self.assertFalse(self.wait_for_application_states.called)

    def test_parser(self):
        args = lc_deploy.parse_args([
            '-m', 'mymodel',
            '-b', 'bun.yaml'])
        self.assertEqual(args.model, 'mymodel')
        self.assertEqual(args.bundle, 'bun.yaml')
        self.assertTrue(args.wait)

    def test_parser_nowait(self):
        args = lc_deploy.parse_args([
            '-m', 'mymodel',
            '-b', 'bun.yaml',
            '--no-wait'])
        self.assertFalse(args.wait)

    def test_parser_logging(self):
        args = lc_deploy.parse_args([
            '-m', 'mymodel',
            '-b', 'bun.yaml'
        ])
        # Using defaults
        self.assertEqual(args.loglevel, 'INFO')
        # Specify the parameter
        args = lc_deploy.parse_args([
            '-m', 'mymodel',
            '-b', 'bun.yaml',
            '--log', 'DEBUG'
        ])
        self.assertEqual(args.loglevel, 'DEBUG')

    def test_parser_force(self):
        args = lc_deploy.parse_args(['-m', 'model', '-b', 'bundle.yaml'])
        self.assertFalse(args.force)
        # Now test we can override
        args = lc_deploy.parse_args(['-m', 'model', '-b', 'bundle.yaml',
                                     '--force'])
        self.assertTrue(args.force)
        args = lc_deploy.parse_args(['-m', 'model', '-b', 'bundle.yaml', '-f'])
        self.assertTrue(args.force)
