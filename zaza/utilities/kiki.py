#!/usr/bin/env python
# Copyright 2014-2017 Canonical Limited.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
kiki is a set of helpers to allow coding against both Juju 1.25 and 2.1
commands.

Usage:

from . import kiki

cmd = [kiki.cmd(), kiki.remove_unit(), unit]
subprocess.check_call(cmd)

if kiki.min_version('2.1'):
   ...

"""

from distutils.version import LooseVersion
from functools import wraps
import os
import subprocess

import six

__author__ = 'David Ames <david.ames@canonical.com>'

cache = {}


class JujuBinaryNotFound(Exception):
    pass


class UnsupportedJujuVersion(Exception):
    pass


def cached(func):
    """Cache return values for multiple executions of func + args

    For example::

        @cached
        def min_version(attribute):
            pass

        min_version('2.1')

    will cache the result of min_version + '2.1' for future calls.
    @returns fuction
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        global cache
        key = str((func, args, kwargs))
        try:
            return cache[key]
        except KeyError:
            pass  # Drop out of the exception handler scope.
        res = func(*args, **kwargs)
        cache[key] = res
        return res
    wrapper._wrapped = func
    return wrapper


@cached
def cmd():
    """Return the Juju command

    There are times when multiple versions of Juju may be installed or
    unpacked requiring testing.
    This function leverages two environment variables to select the correct
    Juju binary. Thus allowing easy switching from one version to another.

     JUJU_BINARY: The full path location to a Juju binary that may not be in
                  $PATH.
                  Example:
                  /home/ubuntu/Downloads/juju/usr/lib/juju-2.1-rc1/bin/juju

     JUJU_VERSION: The full binary name of Juju that is in $PATH.
                   Example: juju-2.1-rc1
                   The result of $(which juju-2.1-rc1)

    If neither of these environment variables is set, the default Juju binary
    in $PATH is selected.
    Example: juju
    The result of $(which juju)

    @returns string Juju command
    """

    if os.environ.get('JUJU_BINARY'):
        juju = os.environ.get('JUJU_BINARY')
    elif os.environ.get('JUJU_VERSION'):
        ver = (".".join(os.environ.get('JUJU_VERSION')
               .split('-')[0].split('.')[:2]))
        juju = 'juju-{}'.format(ver)
    else:
        juju = 'juju'
    return juju


@cached
def version():
    """Return the Juju version

    @raises JujuBinaryNotFound: If command not found.
    @returns string Juju version
    """
    try:
        output = subprocess.check_output([cmd(), 'version']).rstrip()
        if six.PY3:
            output = output.decode('utf-8')
        return output
    except OSError as e:
        raise JujuBinaryNotFound("Juju is not installed at {}. Error: {}"
                                 "".format(cmd(), e))


@cached
def min_version(minimum_version='2.1'):
    """Return True if the Juju version is at least the provided version

    @param minimum_version: string version of Juju
    @returns boolean
    """
    return LooseVersion(version()) >= LooseVersion(minimum_version)


@cached
def supported_juju_version():
    """Validate supported version of Juju

    kiki currently supports Juju 1.25.x and >= 2.1.0 CLI command structures.
    Juju 2.0.x has a third set of command structure that could be added to kiki
    at a later date if it becomes necessary.

    kiki currently does not support 2.0.x. Explicitly fail if the Juju binary
    is 2.0.x.

    @raises UnsupportedJujuVersion: If Juju version 2.0.x
    @returns boolean
    """
    if (not min_version('2.1') and
            min_version('2.0')):
        raise UnsupportedJujuVersion("Kiki does not support Juju 2.0.x "
                                     "command structure")
    return True


# Assert this is a valid version of Juju immediately
assert supported_juju_version()


@cached
def application():
    """Translate argument for application

    @returns string Juju argument for application
    """
    if min_version('2.1'):
        return "application"
    else:
        return "service"


@cached
def applications():
    """Translate identifier for applications

    In Juju status yaml/json output the dictionary key for the set of deployed
    charms is referred to in the plural.

    Example:
    juju_status = subprocess.check_call([kiki.cmd(), 'status', '--format',
                                        'yaml'])
    juju_status[kiki.applications()]['myapp']['units']

    @returns string Juju identifier for applications
    """
    return '{}s'.format(application())


@cached
def get_config():
    """Translate argument for config get

    @returns string Juju argument for config (get)
    """
    if min_version('2.1'):
        return "config"
    else:
        return "get"


@cached
def set_config():
    """Translate argument for config set

    @returns string Juju argument for config (set)
    """
    if min_version('2.1'):
        return "config"
    else:
        return "set"


@cached
def get_model_config():
    """Translate argument for model-config get

    @returns string Juju argument for model-config (get)
    """
    if min_version('2.1'):
        return "model-config"
    else:
        return "get-environment"


@cached
def set_model_config():
    """Translate argument for model-config get

    @returns string Juju argument for model-config (get)
    """
    if min_version('2.1'):
        return "model-config"
    else:
        return "set-environment"


@cached
def remove_unit():
    """Translate argument for remove-unit

    @returns string Juju argument for remove-unit
    """
    if min_version('2.1'):
        return "remove-unit"
    else:
        return "destroy-unit"


@cached
def remove_application():
    """Translate argument for remove-unit

    @returns string Juju argument for remove-unit
    """
    if min_version('2.1'):
        return "remove-application"
    else:
        return "remove-service"


@cached
def juju_state():
    """Translate identifier for juju-state

    @returns string Juju identifier for juju-state
    """
    if min_version('2.1'):
        return "juju-status"
    else:
        return "agent-state"


def get_unit_info_state(unit_info):
    """Translate juju unit information

    @param unit_info: Dictionary of unit information
    @returns string Juju unit information state
    """

    if min_version('2.1'):
        return unit_info[juju_state()]['current']
    else:
        return unit_info['agent-state']


@cached
def actions():
    """Translate argument for actions

    @returns string Juju argument for actions
    """
    if min_version('2.1'):
        return "actions"
    else:
        return "action"


@cached
def action_show_action_output():
    """Translate argument for show-action-output

    @returns string Juju argument for show-action-output
    """
    if min_version('2.1'):
        return "show-action-output"
    else:
        return "fetch"


@cached
def run_action():
    """Translate argument for run-action

    @returns string Juju argument for run-action
    """
    if min_version('2.1'):
        return "run-action"
    else:
        return "do"


@cached
def show_action_output_cmd():
    """Translate command for show-action-output

    The command structure for retrieving the results of an action is quite
    different from Juju 1.25.x to Juju 2.1.

    Build and return the whole command required to retrieve action results.

    @returns list of Juju command arguments for show-action-output
    """
    command = [cmd()]
    if not min_version('2.1'):
        command.append(actions())
    command.append(action_show_action_output())
    return command


@cached
def run_action_cmd():
    """Translate command for run-action

    The command structure for running an action is quite different from Juju
    1.25.x to Juju 2.1.

    Build and return the whole command required to run an action.

    @returns list of Juju command arguments for run-action
    """
    command = [cmd()]
    if not min_version('2.1'):
        command.append(actions())
    command.append(run_action())
    return command
