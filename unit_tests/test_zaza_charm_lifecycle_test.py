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
        self.patch_object(lc_test, 'run_unittest')
        self.patch_object(lc_test, 'run_direct')
        self.patch_object(lc_test.utils, 'get_class')

        class TestClassOne():

            def run(self):
                return

        class TestClassTwo():

            test_runner = 'direct'

            def run(self):
                return

        test_classes = {
            'TestClassOne': TestClassOne,
            'TestClassTwo': TestClassTwo}
        self.get_class.side_effect = lambda x: test_classes[x]
        lc_test.run_test_list(['TestClassOne', 'TestClassTwo'])
        self.run_unittest.assert_called_once_with(
            TestClassOne,
            'TestClassOne')
        self.run_direct.assert_called_once_with(
            TestClassTwo,
            'TestClassTwo')

    def test_get_test_runners(self):
        self.assertEqual(
            lc_test.get_test_runners(),
            {
                'direct': lc_test.run_direct,
                'unittest': lc_test.run_unittest}),

    def test_run_unittest(self):
        loader_mock = mock.MagicMock()
        runner_mock = mock.MagicMock()
        self.patch_object(lc_test.unittest, 'TestLoader')
        self.patch_object(lc_test.unittest, 'TextTestRunner')
        self.TestLoader.return_value = loader_mock
        self.TextTestRunner.return_value = runner_mock
        test_class1_mock = mock.MagicMock()
        lc_test.run_unittest(test_class1_mock, 'class name')
        loader_mock.loadTestsFromTestCase.assert_called_once_with(
            test_class1_mock)

    def test_run_direct(self):
        test_class2_mock = mock.MagicMock()
        lc_test.run_direct(test_class2_mock, 'class name')
        test_class2_mock().run.assert_called_once_with()

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
        self.assertEqual(args.model, {'default_alias': 'modelname'})

    def test_parser_logging(self):
        # Using defaults
        args = lc_test.parse_args(['-m', 'model'])
        self.assertEqual(args.loglevel, 'INFO')
        # Using args
        args = lc_test.parse_args(['-m', 'model', '--log', 'DEBUG'])
        self.assertEqual(args.loglevel, 'DEBUG')
