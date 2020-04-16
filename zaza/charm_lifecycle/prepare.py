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

"""Run prepare phase."""
import argparse
import logging
import sys

import zaza.controller
import zaza.model

import zaza.charm_lifecycle.utils as utils
import zaza.utilities.cli as cli_utils
import zaza.utilities.run_report as run_report
import zaza.utilities.deployment_env as deployment_env


@run_report.register_event_wrapper('Prepare Environment')
def prepare(model_name):
    """Run all steps to prepare the environment before a functional test run.

    :param model: Name of model to add
    :type bundle: str
    """
    zaza.controller.add_model(
        model_name,
        config=deployment_env.get_model_settings(),
        region=deployment_env.get_cloud_region())
    zaza.model.set_model_constraints(
        model_name=model_name,
        constraints=deployment_env.get_model_constraints())


def parse_args(args):
    """Parse command line arguments.

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model-name', help='Name of model to add')
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    parser.set_defaults(loglevel='INFO')
    parser.set_defaults(model_name=utils.generate_model_name())
    return parser.parse_args(args)


def main():
    """Add a new model."""
    args = parse_args(sys.argv[1:])
    cli_utils.setup_logging(log_level=args.loglevel.upper())
    logging.info('model_name: {}'.format(args.model_name))
    prepare(args.model_name)
    run_report.output_event_report()
