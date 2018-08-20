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

import zaza.charm_lifecycle.test as lc_test
import unit_tests.utils as ut_utils


class TestCharmLifecycleTest(ut_utils.BaseTestCase):

    def test_run_test_list(self):
        loader_mock = mock.MagicMock()
        runner_mock = mock.MagicMock()
        self.patch_object(lc_test.unittest, 'TestLoader')
        self.patch_object(lc_test.unittest, 'TextTestRunner')
        self.TestLoader.return_value = loader_mock
        self.TextTestRunner.return_value = runner_mock
        self.patch_object(lc_test.utils, 'get_class')
        self.get_class.side_effect = lambda x: x
        test_class1_mock = mock.MagicMock()
        test_class2_mock = mock.MagicMock()
        lc_test.run_test_list([test_class1_mock, test_class2_mock])
        loader_calls = [
            mock.call(test_class1_mock),
            mock.call(test_class2_mock)]
        loader_mock.loadTestsFromTestCase.assert_has_calls(loader_calls)

    def test_test(self):
        self.patch_object(lc_test, 'run_test_list')
        lc_test.run_test_list(['test_class1', 'test_class2'])
        self.run_test_list.assert_called_once_with(
            ['test_class1', 'test_class2'])

    def test_parser(self):
        args = lc_test.parse_args(
            ['-m', 'modelname', '-t', 'my.test_class1', 'my.test_class2'])
        self.assertEqual(
            args.tests,
            ['my.test_class1', 'my.test_class2'])
        self.assertEqual(args.model_name, 'modelname')

    def test_parser_logging(self):
        # Using defaults
        args = lc_test.parse_args(['-m', 'model'])
        self.assertEqual(args.loglevel, 'INFO')
        # Using args
        args = lc_test.parse_args(['-m', 'model', '--log', 'DEBUG'])
        self.assertEqual(args.loglevel, 'DEBUG')
