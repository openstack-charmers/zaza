import zaza.charm_lifecycle.deploy as lc_deploy
import unit_tests.utils as ut_utils


class TestCharmLifecycleDeploy(ut_utils.BaseTestCase):

    def test_deploy_bundle(self):
        self.patch_object(lc_deploy.subprocess, 'check_call')
        lc_deploy.deploy_bundle('bun.yaml', 'newmodel')
        self.check_call.assert_called_once_with(
            ['juju', 'deploy', '-m', 'newmodel', 'bun.yaml'])

    def test_deploy(self):
        self.patch_object(lc_deploy, 'deploy_bundle')
        self.patch_object(lc_deploy.juju_wait, 'wait')
        lc_deploy.deploy('bun.yaml', 'newmodel')
        self.deploy_bundle.assert_called_once_with('bun.yaml', 'newmodel')
        self.wait.assert_called_once_with()

    def test_deploy_nowait(self):
        self.patch_object(lc_deploy, 'deploy_bundle')
        self.patch_object(lc_deploy.juju_wait, 'wait')
        lc_deploy.deploy('bun.yaml', 'newmodel', wait=False)
        self.deploy_bundle.assert_called_once_with('bun.yaml', 'newmodel')
        self.assertFalse(self.wait.called)

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
