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

"""Module containing utilities for working with commandline tools."""

import argparse
import logging
import os


def parse_arg(options, arg, multiargs=False):
    """Parse argparse argments.

    :param options: Argparse options
    :type options: argparse object
    :param arg: Argument attribute key
    :type arg: string
    :param multiargs: More than one arugment or not
    :type multiargs: boolean
    :returns: Argparse atrribute value
    :rtype: string
    """
    if arg.upper() in os.environ:
        if multiargs:
            return os.environ[arg.upper()].split()
        else:
            return os.environ[arg.upper()]
    else:
        return getattr(options, arg)


def setup_logging(log_level='INFO'):
    """Do setup for logging.

    :returns: Nothing: This fucntion is executed for its sideffect
    :rtype: None
    """
    level = getattr(logging, log_level.upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid log level: "{}"'.format(log_level))
    logFormatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")
    rootLogger = logging.getLogger()
    rootLogger.setLevel(level)
    if not rootLogger.hasHandlers():
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)
        rootLogger.addHandler(consoleHandler)


class StoreModelMapping(argparse.Action):
    """Implement the Action API to process model arguments."""

    def __call__(self, parser, namespace, values, option_strings=None):
        """Process the models argument(s).

        :param parser: The ArgumentParser object which contains this action.
        :type parser: argparse.ArgumentParser
        :param namespace: The Namespace object that will be returned by
                          parse_args().
        :type namespace: argparse.Namespace
        :param values: The associated command-line arguments.
        :type values: str
        :param option_string: The option string that was used to invoke this
                              action.
        :type option_string: str
        """
        model_alias = 'default_alias'
        if ':' in values:
            model_alias, values = values.split(':')
        model_map = getattr(namespace, self.dest) or {}
        model_map[model_alias] = values
        setattr(namespace, self.dest, model_map)


def add_model_parser(parser):
    """Add parser for model argument to supplied parser.

    :param parser: argparse parser
    :type parser: argparse.ArgumentParser
    """
    parser.add_argument('-m', '--model', '--model-name', '--models',
                        help='Model to deploy to',
                        action=StoreModelMapping,
                        required=True)
