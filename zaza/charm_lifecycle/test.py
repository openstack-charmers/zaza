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

"""Run test phase."""
import asyncio
import argparse
import logging
import unittest
import sys

import zaza.model
import zaza.charm_lifecycle.utils as utils
import zaza.utilities.cli as cli_utils
import zaza.utilities.run_report as run_report

UNITTEST = 'unittest'
DIRECT = 'direct'


class Stream2Logger():
    """Act as a stream for the unit test runner."""

    def write(self, messages):
        r"""Write out the messages.

        :param messages: Message(s) to write out.
        :type str: 'msg1\nmsg2'
        """
        for message in messages.split('\n'):
            if message:
                logging.info("{}".format(message))

    def flush(self):
        """Flush not need as logger flushes messages."""
        pass


def get_test_runners():
    """Return mapping of test runner types to methods for those types.

    :returns: Mapping of test runner types to methods
    :rtype: dict
    """
    return {
        UNITTEST: run_unittest,
        DIRECT: run_direct}


def run_unittest(testcase, test_name):
    """Test runner for unittest test cases.

    :param testcase: Class to pass to unittest test runner
    :type testcase: Class
    :param test_name: Name of test for logging.
    :type test_name: str
    """
    suite = unittest.TestLoader().loadTestsFromTestCase(testcase)
    test_result = unittest.TextTestRunner(
        stream=Stream2Logger(),
        verbosity=2).run(suite)
    run_report.register_event_finish('Test {}'.format(test_name))
    assert test_result.wasSuccessful(), "Test run failed"


def run_direct(testcase, test_name):
    """Test runner for standalone tests.

    Test runner for tests which have not been build with
    any particular test framework. The should expose a 'run'
    method which will be called to execute the test.

    :param testcase: Class that encapsulates the test to be run.
    :type testcase: Class
    :param test_name: Name of test for logging.
    :type test_name: str
    """
    test_run = testcase().run()
    assert test_run, "Test run failed"
    run_report.register_event_finish('Test {}'.format(test_name))


def run_test_list(tests):
    """Run each test in the list using the appropriate test runner.

    Test classes should declare the class viariable 'test_runner'
    which will indicate which runner should be used. If none is provided
    then the unittest runner is used.

    :param tests: List of tests to be run.
    :type tests: List
    """
    for _testcase in tests:
        run_report.register_event_start('Test {}'.format(_testcase))
        logging.info('## Running Test {} ##'.format(_testcase))
        testcase = utils.get_class(_testcase)
        try:
            runner = testcase.test_runner
        except AttributeError:
            runner = UNITTEST
        get_test_runners()[runner](testcase, _testcase)


def test(model_name, tests):
    """Run all steps to execute tests against the model."""
    zaza.model.set_juju_model(model_name)
    run_test_list(tests)


def parse_args(args):
    """Parse command line arguments.

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--tests', nargs='+',
                        help='Space separated list of test classes',
                        required=False)
    cli_utils.add_model_parser(parser)
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    parser.set_defaults(loglevel='INFO')
    return parser.parse_args(args)


def main():
    """Run the tests defined by the command line args.

    Run the tests defined by the command line args or if none were provided
    read the tests from the charms tests.yaml config file
    """
    args = parse_args(sys.argv[1:])
    cli_utils.setup_logging(log_level=args.loglevel.upper())
    zaza.model.set_juju_model_aliases(args.model)
    for model_alias, model_name in args.model.items():
        if args.tests:
            tests = args.tests
        else:
            test_steps = utils.get_test_steps()
            tests = test_steps.get(model_alias, [])
        test(model_name, tests)
    run_report.output_event_report()
    asyncio.get_event_loop().close()
