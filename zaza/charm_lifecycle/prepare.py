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
import copy
import logging
import os
import sys

import zaza.controller
import zaza.model

MODEL_DEFAULTS = {
    # Model defaults from charm-test-infra
    #   https://jujucharms.com/docs/2.1/models-config
    'default-series': 'xenial',
    'image-stream': 'daily',
    'test-mode': 'true',
    'transmit-vendor-metrics': 'false',
    # https://bugs.launchpad.net/juju/+bug/1685351
    # enable-os-refresh-update: false
    'enable-os-upgrade': 'false',
    'automatically-retry-hooks': 'false',
    'use-default-secgroup': 'true',
}


def parse_option_list_string(option_list, delimiter=None):
    """Convert the given string to a dictionary of options.

    Each pair must be of the form 'k=v', the delimiter seperates the
    pairs from each other not the key from the value.

    :param option_list: A string representation of key value pairs.
    :type option_list: str
    :param delimiter: Delimiter to use to seperate each pair.
    :type delimiter: str
    :returns: A dictionary of settings.
    :rtype: Dict
    """
    settings = {}
    if delimiter is None:
        delimiter = ';'
    for setting in option_list.split(delimiter):
        if not setting:
            continue
        key, value = setting.split('=')
        settings[key.strip()] = value.strip()
    return settings


def get_model_settings():
    """Construct settings for model from defaults and env variables.

    :returns: Settings to use for model
    :rtype: Dict
    """
    model_settings = copy.deepcopy(MODEL_DEFAULTS)
    model_settings.update(
        parse_option_list_string(os.environ.get('MODEL_SETTINGS', '')))
    return model_settings


def get_model_constraints():
    """Construct constraints for model.

    :returns: Constraints to apply to model
    :rtype: Dict
    """
    return parse_option_list_string(os.environ.get('MODEL_CONSTRAINTS', ''))


def prepare(model_name):
    """Run all steps to prepare the environment before a functional test run.

    :param model: Name of model to add
    :type bundle: str
    """
    zaza.controller.add_model(model_name, config=get_model_settings())
    zaza.model.set_model_constraints(
        model_name=model_name,
        constraints=get_model_constraints())


def parse_args(args):
    """Parse command line arguments.

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model-name', help='Name of model to add',
                        required=True)
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    parser.set_defaults(loglevel='INFO')
    return parser.parse_args(args)


def main():
    """Add a new model."""
    args = parse_args(sys.argv[1:])
    level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid log level: "{}"'.format(args.loglevel))
    logging.basicConfig(level=level)
    prepare(args.model_name)
