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
import logging
import sys

import zaza.model
import zaza.charm_lifecycle.utils as utils


def run_configure_list(functions):
    """Run the configure scripts.

    Run the configure scripts as defined in the list of test classes in
    series.

    :param functions: List of configure functions functions
    :type tests: ['zaza.charms_tests.svc.setup', ...]
    """
    for func in functions:
        utils.get_class(func)()


def configure(model_name, functions):
    """Run all post-deployment configuration steps.

    :param functions: List of configure functions functions
    :type tests: ['zaza.charms_tests.svc.setup', ...]
    """
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
    level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid log level: "{}"'.format(args.loglevel))
    logging.basicConfig(level=level)
    funcs = args.configfuncs or utils.get_charm_config()['configure']
    configure(args.model_name, funcs)
    asyncio.get_event_loop().close()
