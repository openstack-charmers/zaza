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

import zaza.charm_lifecycle.destroy as lc_destroy
import unit_tests.utils as ut_utils


class TestCharmLifecycleDestroy(ut_utils.BaseTestCase):

    def test_destroy(self):
        self.patch_object(lc_destroy.zaza.controller, 'destroy_model')
        lc_destroy.destroy('doomed')
        self.destroy_model.assert_called_once_with('doomed')

    def test_parser(self):
        args = lc_destroy.parse_args(['-m', 'doomed'])
        self.assertEqual(args.model_name, 'doomed')

    def test_parser_logging(self):
        # Using defaults
        args = lc_destroy.parse_args(['-m', 'doomed'])
        self.assertEqual(args.loglevel, 'INFO')
        # Using args
        args = lc_destroy.parse_args(['-m', 'doomed', '--log', 'DEBUG'])
        self.assertEqual(args.loglevel, 'DEBUG')
