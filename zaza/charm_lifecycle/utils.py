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

"""Utilities to support running lifecycle phases."""
import collections
import importlib
import logging
import subprocess
import uuid
import sys
import yaml

BUNDLE_DIR = "./tests/bundles/"
DEFAULT_TEST_CONFIG = "./tests/tests.yaml"
DEFAULT_MODEL_ALIAS = "default_alias"
DEFAULT_DEPLOY_NAME = 'default{}'

ModelDeploy = collections.namedtuple(
    'ModelDeploy', ['model_alias', 'model_name', 'bundle'])
EnvironmentDeploy = collections.namedtuple(
    'EnvironmentDeploy', ['name', 'model_deploys', 'run_in_series'])

default_deploy_number = 0


def _model_alias_str_fmt(data):
    """Convert to model_alias:str format if needed.

    If a string is passed in then the string is mapped to the
    DEFAULT_MODEL_ALIAS. If a dict is passed then this is a noop.

    :param data: String or Model Alias to data map
    :type data: Union[str, Dict[str, str]]
    :returns: Model Alias to data map
    :rtype: Dict[str, str]
    """
    if isinstance(data, collections.Mapping):
        return data
    else:
        return {DEFAULT_MODEL_ALIAS: data}


def _concat_model_alias_maps(data):
    """Iterate over list and construct single dict of model alias maps.

    Any elements in list which are not dicts are added to a list and assigned
    to DEFAULT_MODEL_ALIAS.

    eg If input is ['e1', 'e2', {'alias1': ['e3'], 'alias2': ['e4']}]
       this function will return:
       {
           DEFAULT_MODEL_ALIAS: ['e1', 'e2'],
           'alias1': ['e3'],
           'alias2': ['e4']}

    :param data: List comprised of str elements or dict elements.
    :type data: List[Union[str, Dict[str, List[str]]]]
    :returns: Model Alias to data map
    :rtype: Dict[str, List[str]]
    """
    new_data = {DEFAULT_MODEL_ALIAS: []}
    for item in data:
        if isinstance(item, collections.Mapping):
            new_data.update(item)
        else:
            new_data[DEFAULT_MODEL_ALIAS].append(item)
    return new_data


def get_test_bundle_mappings(bundle_key):
    """Get test bundles with their model alias.

    Get a list of test bundles with their model alias. If no model alias is
    supplied then DEFAULT_MODEL_ALIAS is used.
    eg if test.yaml contained:
        gate_bundles:
          - bundle1
          - bundle2
          - model_alias1: bundle_3
            model_alias2: bundle_4
       then get_test_bundles('gate_bundles') would return:
            [
                {'default_alias': 'bundle1'},
                {'default_alias': 'bundle2'},
                {'model_alias1': 'bundle1', 'model_alias2': 'bundle2'}])
    :param bundle_key: Name of group of bundles eg gate_bundles
    :type bundle_key: str
    :returns: A list of dicts where the dict contain a model alias to bundle
              mapping.
    :rtype: List[Dict[str, str]]
    """
    return [_model_alias_str_fmt(b)
            for b in get_charm_config()[bundle_key]]


def get_default_env_deploy_name():
    """Generate a default name for the environment deploy.

    :returns: Environment name
    :rtype: str
    """
    global default_deploy_number
    default_deploy_number = default_deploy_number + 1
    return DEFAULT_DEPLOY_NAME.format(default_deploy_number)


def get_environment_deploys(bundle_key, deployment_name=None):
    """Describe environment deploys for a given set ug bundles.

    Get a list of test bundles with their model alias. If no model alias is
    supplied then DEFAULT_MODEL_ALIAS is used.

    eg if test.yaml contained:

        gate_bundles:
          - bundle1
          - bundle2
          - model_alias1: bundle_3
            model_alias2: bundle_4
          - my-cmr-test:
            - model_alias3: bundle_5
            - model_alias4: bundle_6

       then get_test_bundles('gate_bundles') would return:

            [
                {'default_alias': 'bundle1'},
                {'default_alias': 'bundle2'},
                {'model_alias1': 'bundle_3', 'model_alias2': 'bundle_5'},
                {'model_alias3': 'bundle_4', 'model_alias2': 'bundle_6'}]

    :param bundle_key: Name of group of bundles eg gate_bundles
    :type bundle_key: str
    :returns: A list of dicts where the dict contain a model alias to bundle
              mapping.
    :rtype: List[EnvironmentDeploy, EnvironmentDeploy, ...]
    """
    bundle_mappings = get_test_bundle_mappings(bundle_key)
    environment_deploys = []
    for b in bundle_mappings:
        env_deploy_name = None
        model_deploys = []
        for alias, bundle in b.items():
            model_name = generate_model_name()
            if isinstance(bundle, list):
                env_deploy_name = alias
                model_deploys.append(ModelDeploy(alias, model_name, bundle))
                run_in_series = True
            else:
                if not env_deploy_name:
                    env_deploy_name = get_default_env_deploy_name()
                model_deploys.append(ModelDeploy(alias, model_name, bundle))
                run_in_series = False
        environment_deploys.append(EnvironmentDeploy(
            env_deploy_name,
            model_deploys,
            run_in_series))
    return environment_deploys


def get_config_steps():
    """Get configuration steps and their associated model aliases.

    Get a map of configuration steps to model aliases. If there are
    configuration steps which are not mapped to a model alias then these are
    associated with the the DEFAULT_MODEL_ALIAS.

    eg if test.yaml contained:

        configure:
        - conf.class1
        - conf.class2
        - model_alias1:
          - conf.class3

       then get_config_steps() would return:

        {
            'default_alias': ['conf.class1', 'conf.class2'],
            'model_alias1': ['conf.class3']}

    :returns: A dict mapping config steps to model aliases
    :rtype: Dict[str, List[str]]
    """
    return _concat_model_alias_maps(get_charm_config().get('configure', []))


def get_test_steps():
    """Get test steps and their associated model aliases.

    Get a map of test steps to model aliases. If there are test
    steps which are not mapped to a model alias then these are associated with
    the the DEFAULT_MODEL_ALIAS.

    eg if test.yaml contained:

        test:
        - test.class1
        - test.class2
        - model_alias1:
          - test.class3

       then get_test_steps() would return:

        {
            'default_alias': ['test.class1', 'test.class2'],
            'model_alias1': ['test.class3']}

    :returns: A dict mapping test steps to model aliases
    :rtype: Dict[str, List[str]]
    """
    return _concat_model_alias_maps(get_charm_config().get('tests', []))


def get_charm_config(yaml_file=None):
    """Read the yaml test config file and return the resulting config.

    :param yaml_file: File to be read
    :type yaml_file: str
    :returns: Config dictionary
    :rtype: dict
    """
    if not yaml_file:
        yaml_file = DEFAULT_TEST_CONFIG
    with open(yaml_file, 'r') as stream:
        return yaml.safe_load(stream)


def get_class(class_str):
    """Get the class represented by the given string.

    For example, get_class('zaza.charms_tests.svc.TestSVCClass1')
    returns zaza.charms_tests.svc.TestSVCClass1

    :param class_str: Class to be returned
    :type class_str: str
    :returns: Test class
    :rtype: class
    """
    old_syspath = sys.path
    sys.path.insert(0, '.')
    module_name = '.'.join(class_str.split('.')[:-1])
    class_name = class_str.split('.')[-1]
    module = importlib.import_module(module_name)
    sys.path = old_syspath
    return getattr(module, class_name)


def generate_model_name():
    """Generate a unique model name.

    :returns: Model name
    :rtype: str
    """
    return 'zaza-{}'.format(str(uuid.uuid4())[-12:])


def check_output_logging(cmd):
    """Run command and log output.

    :param cmd: Shell command to run
    :type cmd: List
    :raises: subprocess.CalledProcessError
    """
    popen = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True)
    for line in iter(popen.stdout.readline, ""):
        # popen.poll checks if child process has terminated. If it has it
        # returns the returncode. If it has not it returns None.
        if popen.poll() is not None:
            break
        logging.info(line.strip())
    popen.stdout.close()
    return_code = popen.poll()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)
