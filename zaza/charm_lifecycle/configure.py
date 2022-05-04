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

"""Run configuration phase."""
import asyncio
import argparse
import sys

import zaza.model
import zaza.charm_lifecycle.utils as utils
from zaza.notifications import (
    notify_around,
    NotifyEvents,
)
import zaza.utilities.cli as cli_utils
import zaza.utilities.run_report as run_report


@notify_around(NotifyEvents.CONFIGURE)
def run_configure_list(functions):
    """Run the configure scripts.

    Run the configure scripts as defined in the list of configuration methods
    in series.

    :param functions: List of configure functions functions
    :type tests: ['zaza.charms_tests.svc.setup', ...]
    """
    for func in functions:
        with notify_around(NotifyEvents.CONFIGURE_FUNCTION, function=func):
            # TODO: change run_report to use zaza.notifications
            run_report.register_event_start('Configure {}'.format(func))
            utils.get_class(func)()
            run_report.register_event_finish('Configure {}'.format(func))


def configure(model_name, functions, test_directory=None):
    """Run all post-deployment configuration steps.

    :param functions: List of configure functions functions
    :type tests: ['zaza.charms_tests.svc.setup', ...]
    :param test_directory: Set the directory containing tests.yaml and bundles.
    :type test_directory: str
    """
    utils.set_base_test_dir(test_dir=test_directory)
    zaza.model.set_juju_model(model_name)
    run_configure_list(functions)


def parse_args(args):
    """Parse command line arguments.

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--configfuncs', nargs='+',
                        help='Space separated list of config functions',
                        required=False)
    cli_utils.add_model_parser(parser)
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    cli_utils.add_test_directory_argument(parser)
    parser.set_defaults(loglevel='INFO')
    return parser.parse_args(args)


def main():
    """Run the configuration defined by the command line args.

    Run the configuration defined by the command line args or if none were
    provided read the configuration functions  from the charms tests.yaml
    config file
    """
    args = parse_args(sys.argv[1:])
    cli_utils.setup_logging(log_level=args.loglevel.upper())
    for model_alias, model_name in args.model.items():
        if args.configfuncs:
            funcs = args.configfuncs
        else:
            config_steps = utils.get_config_steps()
            funcs = config_steps.get(model_alias, [])
        configure(model_name, funcs)
    run_report.output_event_report()
    zaza.clean_up_libjuju_thread()
    asyncio.get_event_loop().close()
