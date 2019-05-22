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
import importlib
import logging
import subprocess
import uuid
import sys
import yaml

BUNDLE_DIR = "./tests/bundles/"
DEFAULT_TEST_CONFIG = "./tests/tests.yaml"


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
    sys.path.append('.')
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
    """
    popen = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True)
    for line in iter(popen.stdout.readline, ""):
        logging.info(line.strip())
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)
