import asyncio
import argparse
import collections
import logging
import unittest
import sys

import zaza.charm_lifecycle.utils as utils


class ZazaTestLoader(unittest.TestLoader):
    def loadTestsFromTestCase(self, testCaseClass, charm_name, args=None):
        """
        Return a suite of all tests cases contained in testCaseClass

        NOTE(fnordahl): Origin unittest.TestLoader.loadTestsFromTestCase
                        Overloaded and extended to pass arguments as we
                        instantiate test classes.
        """
        if issubclass(testCaseClass, unittest.suite.TestSuite):
            raise TypeError("Test cases should not be derived from "
                            "TestSuite. Maybe you meant to derive from "
                            "TestCase?")
        testCaseNames = self.getTestCaseNames(testCaseClass)
        if not testCaseNames and hasattr(testCaseClass, 'runTest'):
            testCaseNames = ['runTest']
        loaded_suite = self.suiteClass(
            map(testCaseClass(charm_name, args), testCaseNames)
        )
        return loaded_suite


def run_test_list(charm_name, tests):
    """Run the tests as defined in the list of test classes in series.

    :param tests: List of test class strings
    :type tests: ['zaza.charms_tests.svc.TestSVCClass1', ...]
    :raises: AssertionError if test run fails
    """
    for test in tests:
        if type(test) is collections.OrderedDict:
            # when test is specified as a mapping in the yaml we get the name
            # from the single outer key in the dict
            class_name = next(iter(test.keys()))
            # the datastructure deserialized from the mappings children is
            # passed on as argument to the test
            class_args = test.get(class_name)
        else:
            class_name = test
            class_args = None

        testcase = utils.get_class(class_name)
        loader = ZazaTestLoader()
        suite = loader.loadTestsFromTestCase(testcase, charm_name, class_args)
        test_result = unittest.TextTestRunner(verbosity=2).run(suite)
        assert test_result.wasSuccessful(), "Test run failed"


def test(charm_name, model_name, tests):
    """Run all steps to execute tests against the model"""
    utils.set_juju_model(model_name)
    run_test_list(charm_name, tests)


def parse_args(args):
    """Parse command line arguments

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--tests', nargs='+',
                        help='Space sperated list of test classes',
                        required=False)
    parser.add_argument('-m', '--model-name', help='Name of model to remove',
                        required=True)
    return parser.parse_args(args)


def main():
    """Run the tests defined by the command line args or if none were provided
       read the tests from the charms tests.yaml config file"""
    logging.basicConfig(level=logging.INFO)
    args = parse_args(sys.argv[1:])
    tests = args.tests or utils.get_charm_config()['tests']
    test(args.model_name, tests)
    asyncio.get_event_loop().close()
