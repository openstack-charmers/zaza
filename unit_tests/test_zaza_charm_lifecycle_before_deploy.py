# Copyright 2020 Canonical Ltd.
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

import zaza.charm_lifecycle.before_deploy as lc_before_deploy
import unit_tests.utils as ut_utils


class TestCharmLifecycleBeforeDeploy(ut_utils.BaseTestCase):

    def test_run_before_deploy_list(self):
        self.patch_object(lc_before_deploy.utils, 'get_class')
        self.get_class.side_effect = lambda x: x
        mock1 = mock.MagicMock()
        mock2 = mock.MagicMock()
        lc_before_deploy.run_before_deploy_list([mock1, mock2])
        self.assertTrue(mock1.called)
        self.assertTrue(mock2.called)

    def test_before_deploy(self):
        self.patch_object(lc_before_deploy, 'run_before_deploy_list')
        mock1 = mock.MagicMock()
        mock2 = mock.MagicMock()
        lc_before_deploy.before_deploy('modelname', [mock1, mock2])
        self.run_before_deploy_list.assert_called_once_with([mock1, mock2])

    def test_parser(self):
        args = lc_before_deploy.parse_args(
            ['-m', 'modelname', '-c', 'my.func1', 'my.func2'])
        self.assertEqual(args.beforefuncs, ['my.func1', 'my.func2'])
        self.assertEqual(args.model_name, 'modelname')

    def test_parser_logging(self):
        # Using defaults
        args = lc_before_deploy.parse_args(['-m', 'model'])
        self.assertEqual(args.loglevel, 'INFO')
        # Using args
        args = lc_before_deploy.parse_args(['-m', 'model', '--log', 'DEBUG'])
        self.assertEqual(args.loglevel, 'DEBUG')
