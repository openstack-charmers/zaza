# Copyright 2019 Canonical Ltd.
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
"""Module for working with zaza setup file."""

import copy
import logging
import os
import functools
import yaml

import zaza.model

ZAZA_SETUP_FILE_LOCATIONS = [
    '{home}/.zaza.yaml']

SECRETS = 'secrets'
RUNTIME_CONFIG = 'runtime_config'

DEPLOYMENT_CONTEXT_SECTIONS = [
    SECRETS,
    RUNTIME_CONFIG]

MODEL_SETTINGS_SECTION = 'model_settings'
MODEL_CONSTRAINTS_SECTION = 'model_constraints'

VALID_ENVIRONMENT_KEY_PREFIXES = [
    'OS_',
    'TEST_',
    'MOJO_',
    'JUJU_',
    'CHARM_',
    'MODEL_',
]

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

MODEL_DEFAULT_CONSTRAINTS = {}


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
    """Return model settings from defaults, config file and env variables.

    :returns: Settings to use for model
    :rtype: Dict
    """
    model_settings = copy.deepcopy(MODEL_DEFAULTS)
    model_settings.update(get_setup_file_section(MODEL_SETTINGS_SECTION))
    model_settings.update(
        parse_option_list_string(os.environ.get('MODEL_SETTINGS', '')))
    return model_settings


def get_model_constraints():
    """Return constraints for model from defaults, config file & env variables.

    :returns: Constraints to apply to model
    :rtype: Dict
    """
    model_constraints = copy.deepcopy(MODEL_DEFAULT_CONSTRAINTS)
    model_constraints.update(get_setup_file_section(MODEL_CONSTRAINTS_SECTION))
    model_constraints.update(
        parse_option_list_string(os.environ.get('MODEL_CONSTRAINTS', '')))
    return model_constraints


def get_cloud_region():
    """Return a configured cloud name to support multi-cloud controllers.

    :returns: A string configured in .zaza.yaml or None
    :rtype: Union[str, None]
    """
    return get_setup_file_contents().get('region')


def is_valid_env_key(key):
    """Check if key is a valid environment variable name for use with template.

    :param key: List of configure functions functions
    :type key: str
    :returns: Whether key is a valid environment variable name
    :rtype: bool
    """
    valid = False
    for _k in VALID_ENVIRONMENT_KEY_PREFIXES:
        if key.startswith(_k):
            valid = True
            break
    return valid


def find_setup_file():
    """Search for zaza config file.

    :returns: Location of zaza config file or None if not found.
    :rtype: str or None
    """
    ctxt = {
        'home': os.environ.get('HOME')}
    for setup_file in ZAZA_SETUP_FILE_LOCATIONS:
        if os.path.isfile(setup_file.format(**ctxt)):
            return setup_file.format(**ctxt)


def get_setup_file_contents():
    """Return a dictionary of tha zaza config files contents.

    :returns: Return dict of tha zaza config files contents or an empty dict if
              no file was found.
    :rtype: dict
    """
    setup_file = find_setup_file()
    setup_file_data = {}
    if setup_file:
        with open(setup_file, 'r') as stream:
            try:
                _file_data = yaml.safe_load(stream)
                if _file_data:
                    setup_file_data.update(_file_data)
            except yaml.YAMLError:
                logging.warn("Unable to load data from {}".format(setup_file))
    return setup_file_data


def get_setup_file_section(section_name):
    """Return the contents of a section from the zaza config file."""
    return get_setup_file_contents().get(section_name, {})


get_secrets = functools.partial(get_setup_file_section, section_name=SECRETS)


def get_deployment_context():
    """Return the context used for rendering deployment config and bundles.

    Extract key value pairs from zaza config file and environment. Environment
    variables take presedent over config file values.

    :returns: Context constructed from zaza config file and environment
              variables.
    :rtype: dict
    """
    runtime_config = {}
    conf_file_ctxt = get_setup_file_contents()
    for section in DEPLOYMENT_CONTEXT_SECTIONS:
        runtime_config.update(conf_file_ctxt.get(section, {}))
    for k, v in os.environ.items():
        if is_valid_env_key(k):
            runtime_config[k] = v
    return runtime_config


def get_tmpdir(model_name=None):
    """Return a model specific temp directory.

    Return a model specific temp directory. If the dirctory does not already
    exist then create it.

    :param model_name: Model name temp dir is associated with.
    :type model_name: str
    """
    model_name = model_name or zaza.model.get_juju_model()
    tmp_dir = '/tmp/{}'.format(model_name)
    if not os.path.exists(tmp_dir):
        os.mkdir(tmp_dir)
    return tmp_dir
