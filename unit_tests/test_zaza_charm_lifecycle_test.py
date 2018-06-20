"""Module containing unit tests for zaza.charm_lifecycle.test."""
import mock

import zaza.charm_lifecycle.test as lc_test
import unit_tests.utils as ut_utils


class TestCharmLifecycleTest(ut_utils.BaseTestCase):
    """Unit tests for zaza.charm_lifecycle.test."""

    def test_run_test_list(self):
        """Test run_test_list."""
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
        """Test the test function."""
        self.patch_object(lc_test, 'run_test_list')
        lc_test.run_test_list(['test_class1', 'test_class2'])
        self.run_test_list.assert_called_once_with(
            ['test_class1', 'test_class2'])

    def test_parser(self):
        """Test parse_args."""
        args = lc_test.parse_args(
            ['-m', 'modelname', '-t', 'my.test_class1', 'my.test_class2'])
        self.assertEqual(
            args.tests,
            ['my.test_class1', 'my.test_class2'])
        self.assertEqual(args.model_name, 'modelname')
