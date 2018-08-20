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

"""Run destroy phase."""
import argparse
import logging
import sys

import zaza.controller


def destroy(model_name):
    """Run all steps to cleaup after a test run.

    :param model: Name of model to remove
    :type bundle: str
    """
    zaza.controller.destroy_model(model_name)


def parse_args(args):
    """Parse command line arguments.

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model-name', help='Name of model to remove',
                        required=True)
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    parser.set_defaults(loglevel='INFO')
    return parser.parse_args(args)


def main():
    """Cleanup after test run."""
    args = parse_args(sys.argv[1:])
    level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid log level: "{}"'.format(args.loglevel))
    logging.basicConfig(level=level)
    destroy(args.model_name)
