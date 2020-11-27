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

import zaza.charm_lifecycle.prepare as lc_prepare
import unit_tests.utils as ut_utils


class TestCharmLifecyclePrepare(ut_utils.BaseTestCase):

    def test_prepare(self):
        self.patch_object(lc_prepare.zaza.controller, 'add_model')
        self.patch_object(lc_prepare.deployment_env, 'get_model_settings')
        self.patch_object(lc_prepare.deployment_env, 'get_model_constraints')
        self.patch_object(lc_prepare.deployment_env, 'get_cloud_region')
        self.patch_object(lc_prepare.zaza.model, 'set_model_constraints')
        self.get_model_settings.return_value = {'default-series': 'hardy'}
        self.get_model_constraints.return_value = {'image-stream': 'released'}
        lc_prepare.prepare('newmodel')
        self.add_model.assert_called_once_with(
            'newmodel',
            config={
                'default-series': 'hardy'},
            region=None)
        self.set_model_constraints.assert_called_once_with(
            constraints={'image-stream': 'released'},
            model_name='newmodel')

    def test_parser(self):
        args = lc_prepare.parse_args([])
        self.assertTrue(args.model_name.startswith('zaza-'))

    def test_parser_model(self):
        args = lc_prepare.parse_args(['-m', 'newmodel'])
        self.assertEqual(args.model_name, 'newmodel')

    def test_parser_logging(self):
        # Using defaults
        args = lc_prepare.parse_args(['-m', 'model'])
        self.assertEqual(args.loglevel, 'INFO')
        # Using args
        args = lc_prepare.parse_args(['-m', 'model', '--log', 'DEBUG'])
        self.assertEqual(args.loglevel, 'DEBUG')
