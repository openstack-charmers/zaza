"""Module containing unit tests for zaza.charm_lifecycle.deploy."""
import jinja2
import mock

import zaza.charm_lifecycle.deploy as lc_deploy
import unit_tests.utils as ut_utils


class TestCharmLifecycleDeploy(ut_utils.BaseTestCase):
    """Unit tests for zaza.charm_lifecycle.deploy."""

    def test_is_valid_env_key(self):
        """Test is_valid_env_key for different env vars."""
        self.assertTrue(lc_deploy.is_valid_env_key('OS_VIP04'))
        self.assertTrue(lc_deploy.is_valid_env_key('FIP_RANGE'))
        self.assertTrue(lc_deploy.is_valid_env_key('GATEWAY'))
        self.assertTrue(lc_deploy.is_valid_env_key('NAME_SERVER'))
        self.assertTrue(lc_deploy.is_valid_env_key('NET_ID'))
        self.assertTrue(lc_deploy.is_valid_env_key('VIP_RANGE'))
        self.assertFalse(lc_deploy.is_valid_env_key('AMULET_OS_VIP'))
        self.assertFalse(lc_deploy.is_valid_env_key('ZAZA_TEMPLATE_VIP00'))
        self.assertFalse(lc_deploy.is_valid_env_key('PATH'))

    def test_get_template_context_from_env(self):
        """Test get_template_context_from_env."""
        self.patch_object(lc_deploy.os, 'environ')
        self.environ.items.return_value = [
            ('AMULET_OS_VIP', '10.10.0.2'),
            ('OS_VIP04', '10.10.0.2'),
            ('ZAZA_TEMPLATE_VIP00', '20.3.4.5'),
            ('PATH', 'aa')]
        self.assertEqual(
            lc_deploy.get_template_context_from_env(),
            {'OS_VIP04': '10.10.0.2'}
        )

    def test_get_charm_config_context(self):
        """Test get_charm_config_context."""
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        self.get_charm_config.return_value = {
            'charm_name': 'mycharm'}
        self.assertEqual(
            lc_deploy.get_charm_config_context(),
            {'charm_location': '../../../mycharm', 'charm_name': 'mycharm'})

    def test_get_template_overlay_context(self):
        """Test get_template_overlay_context."""
        self.patch_object(lc_deploy, 'get_template_context_from_env')
        self.patch_object(lc_deploy, 'get_charm_config_context')
        self.get_template_context_from_env.return_value = {
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

    def test_get_overlay_template_dir(self):
        """Test get_overlay_template_dir."""
        self.assertEqual(
            lc_deploy.get_overlay_template_dir(),
            'tests/bundles/overlays')

    def test_get_jinja2_env(self):
        """Test get_jinja2_env."""
        self.patch_object(lc_deploy, 'get_overlay_template_dir')
        self.get_overlay_template_dir.return_value = 'mytemplatedir'
        self.patch_object(lc_deploy.jinja2, 'Environment')
        self.patch_object(lc_deploy.jinja2, 'FileSystemLoader')
        jinja_env_mock = mock.MagicMock()
        self.Environment.return_value = jinja_env_mock
        self.assertEqual(
            lc_deploy.get_jinja2_env(),
            jinja_env_mock)
        self.FileSystemLoader.assert_called_once_with('mytemplatedir')

    def test_get_template_name(self):
        """Test get_template_name."""
        self.assertEqual(
            lc_deploy.get_template_name('mybundles/mybundle.yaml'),
            'mybundle.yaml.j2')

    def test_get_template(self):
        """Test get_template."""
        self.patch_object(lc_deploy, 'get_jinja2_env')
        jinja_env_mock = mock.MagicMock()
        self.get_jinja2_env.return_value = jinja_env_mock
        jinja_env_mock.get_template.return_value = 'mytemplate'
        self.assertEqual(
            lc_deploy.get_template('mybundle.yaml'),
            'mytemplate')

    def test_get_template_missing_template(self):
        """Test get_template when template is missing."""
        self.patch_object(lc_deploy, 'get_jinja2_env')
        jinja_env_mock = mock.MagicMock()
        self.get_jinja2_env.return_value = jinja_env_mock
        jinja_env_mock.get_template.side_effect = \
            jinja2.exceptions.TemplateNotFound(name='bob')
        self.assertIsNone(lc_deploy.get_template('mybundle.yaml'))

    def test_render_template(self):
        """Test render_template."""
        self.patch_object(lc_deploy, 'get_template_overlay_context')
        template_mock = mock.MagicMock()
        template_mock.render.return_value = 'Template contents'
        m = mock.mock_open()
        with mock.patch('zaza.charm_lifecycle.deploy.open', m, create=True):
            lc_deploy.render_template(template_mock, '/tmp/mybundle.yaml')
        m.assert_called_once_with('/tmp/mybundle.yaml', 'w')
        handle = m()
        handle.write.assert_called_once_with('Template contents')

    def test_render_overlay(self):
        """Test render_overlay."""
        self.patch_object(lc_deploy, 'render_template')
        template_mock = mock.MagicMock()
        self.patch_object(lc_deploy, 'get_template')
        self.get_template.return_value = template_mock
        lc_deploy.render_overlay('my_overlay.yaml', '/tmp/special-dir')
        self.render_template.assert_called_once_with(
            template_mock,
            '/tmp/special-dir/my_overlay.yaml')

    def test_render_overlay_no_template(self):
        """Test render_overlay when template is missing."""
        self.patch_object(lc_deploy, 'get_template')
        self.get_template.return_value = None
        self.assertIsNone(lc_deploy.render_overlay('mybundle.yaml', '/tmp/'))

    def test_render_overlays(self):
        """Test render_overlays."""
        RESP = {
            'mybundles/mybundle.yaml': '/tmp/mybundle.yaml'}
        self.patch_object(lc_deploy, 'render_local_overlay')
        self.render_local_overlay.return_value = '/tmp/local-overlay.yaml'
        self.patch_object(lc_deploy, 'render_overlay')
        self.render_overlay.side_effect = lambda x, y: RESP[x]
        self.assertEqual(
            lc_deploy.render_overlays('mybundles/mybundle.yaml', '/tmp'),
            ['/tmp/local-overlay.yaml', '/tmp/mybundle.yaml'])

    def test_render_overlays_missing(self):
        """Test render_overlays when template is missing."""
        RESP = {'mybundles/mybundle.yaml': None}
        self.patch_object(lc_deploy, 'render_overlay')
        self.patch_object(lc_deploy, 'render_local_overlay')
        self.render_local_overlay.return_value = '/tmp/local.yaml'
        self.render_overlay.side_effect = lambda x, y: RESP[x]
        self.assertEqual(
            lc_deploy.render_overlays('mybundles/mybundle.yaml', '/tmp'),
            ['/tmp/local.yaml'])

    def test_deploy_bundle(self):
        """Test deploy_bundle."""
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        self.get_charm_config.return_value = {}
        self.patch_object(lc_deploy, 'render_overlays')
        self.patch_object(lc_deploy.subprocess, 'check_call')
        self.render_overlays.return_value = []
        lc_deploy.deploy_bundle('bun.yaml', 'newmodel')
        self.check_call.assert_called_once_with(
            ['juju', 'deploy', '-m', 'newmodel', 'bun.yaml'])

    def test_deploy(self):
        """Test deploy."""
        self.patch_object(lc_deploy.zaza.model, 'wait_for_application_states')
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        self.get_charm_config.return_value = {}
        self.patch_object(lc_deploy, 'deploy_bundle')
        lc_deploy.deploy('bun.yaml', 'newmodel')
        self.deploy_bundle.assert_called_once_with('bun.yaml', 'newmodel')
        self.wait_for_application_states.assert_called_once_with(
            'newmodel',
            {})

    def test_deploy_bespoke_states(self):
        """Test deploy with bespoke states."""
        self.patch_object(lc_deploy.zaza.model, 'wait_for_application_states')
        self.patch_object(lc_deploy.utils, 'get_charm_config')
        self.get_charm_config.return_value = {
            'target_deploy_status': {
                'vault': {
                    'workload-status': 'blocked',
                    'workload-status-message': 'Vault needs to be inited'}}}
        self.patch_object(lc_deploy, 'deploy_bundle')
        lc_deploy.deploy('bun.yaml', 'newmodel')
        self.deploy_bundle.assert_called_once_with('bun.yaml', 'newmodel')
        self.wait_for_application_states.assert_called_once_with(
            'newmodel',
            {'vault': {
                'workload-status': 'blocked',
                'workload-status-message': 'Vault needs to be inited'}})

    def test_deploy_nowait(self):
        """Test deploy without checking wl states."""
        self.patch_object(lc_deploy.zaza.model, 'wait_for_application_states')
        self.patch_object(lc_deploy, 'deploy_bundle')
        lc_deploy.deploy('bun.yaml', 'newmodel', wait=False)
        self.deploy_bundle.assert_called_once_with('bun.yaml', 'newmodel')
        self.assertFalse(self.wait_for_application_states.called)

    def test_parser(self):
        """Test parse_args."""
        args = lc_deploy.parse_args([
            '-m', 'mymodel',
            '-b', 'bun.yaml'])
        self.assertEqual(args.model, 'mymodel')
        self.assertEqual(args.bundle, 'bun.yaml')
        self.assertTrue(args.wait)

    def test_parser_nowait(self):
        """Test parse_args processes --no-wait correctly."""
        args = lc_deploy.parse_args([
            '-m', 'mymodel',
            '-b', 'bun.yaml',
            '--no-wait'])
        self.assertFalse(args.wait)
