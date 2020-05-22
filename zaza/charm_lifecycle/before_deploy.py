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

"""Run configuration phase."""
import asyncio
import argparse
import sys

import zaza.model
import zaza.charm_lifecycle.utils as utils
import zaza.utilities.cli as cli_utils
import zaza.utilities.run_report as run_report


def run_before_deploy_list(functions):
    """Run the pre-deploy scripts.

    Run the pre-deploy scripts as defined in the list of methods in
    series.

    :param functions: List of pre-deploy functions functions
    :type tests: ['zaza.charms_tests.svc.setup', ...]
    """
    for func in functions:
        run_report.register_event_start('Before Deploy {}'.format(func))
        utils.get_class(func)()
        run_report.register_event_finish('Before Deploy {}'.format(func))


def before_deploy(model_name, functions):
    """Run all post-deployment configuration steps.

    :param functions: List of pre-deploy functions functions
    :type tests: ['zaza.charms_tests.svc.setup', ...]
    """
    zaza.model.set_juju_model(model_name)
    run_before_deploy_list(functions)


def parse_args(args):
    """Parse command line arguments.

    :param args: List of before_deploy functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--beforefuncs', nargs='+',
                        help='Space separated list of config functions',
                        required=False)
    parser.add_argument('-m', '--model-name', help='Name of model to remove',
                        required=True)
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
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
    funcs = args.configfuncs or utils.get_charm_config()['before_deploy']
    before_deploy(args.model_name, funcs)
    run_report.output_event_report()
    asyncio.get_event_loop().close()
