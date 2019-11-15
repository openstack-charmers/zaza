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


def run_test_list(tests):
    """Run the tests as defined in the list of test classes in series.

    :param tests: List of test class strings
    :type tests: ['zaza.charms_tests.svc.TestSVCClass1', ...]
    :raises: AssertionError if test run fails
    """
    for _testcase in tests:
        run_report.register_event_start('Test {}'.format(_testcase))
        logging.info('## Running Test {} ##'.format(_testcase))
        testcase = utils.get_class(_testcase)
        suite = unittest.TestLoader().loadTestsFromTestCase(testcase)
        test_result = unittest.TextTestRunner(
            stream=Stream2Logger(),
            verbosity=2).run(suite)
        run_report.register_event_finish('Test {}'.format(_testcase))
        assert test_result.wasSuccessful(), "Test run failed"


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
    for model_alias, model_name in args.model.items():
        if args.tests:
            tests = args.tests
        else:
            test_steps = utils.get_test_steps()
            tests = test_steps.get(model_alias, [])
        test(model_name, tests)
    run_report.output_event_report()
    asyncio.get_event_loop().close()
