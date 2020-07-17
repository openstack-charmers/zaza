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

"""Module for interacting with a juju model.

This module contains a number of functions for interacting with a Juju model
mostly via libjuju. Async function also provice a non-async alternative via
'sync_wrapper'.
"""

import asyncio
from async_generator import async_generator, yield_, asynccontextmanager
import logging
import os
import subprocess
import tempfile
import yaml
from oslo_config import cfg
import concurrent

from juju.errors import JujuError
from juju.model import Model

from zaza import sync_wrapper
import zaza.utilities.generic as generic_utils

CURRENT_MODEL = None
MODEL_ALIASES = {}


class ModelTimeout(Exception):
    """Model timeout exception."""

    pass


def set_juju_model(model_name):
    """Point environment at the given model.

    :param model_name: Model to point environment at
    :type model_name: str
    """
    global CURRENT_MODEL
    os.environ["JUJU_MODEL"] = model_name
    CURRENT_MODEL = model_name


def set_juju_model_aliases(model_aliases):
    """Store the model aliases in a global.

    :param model_aliases: Model alias map to store
    :type model_aliases: dict
    """
    global MODEL_ALIASES
    MODEL_ALIASES = model_aliases


def get_juju_model_aliases():
    """Return the model aliases from global.

    :returns: Model alias map
    :rtype: dict
    """
    global MODEL_ALIASES
    return MODEL_ALIASES


def unset_juju_model_aliases():
    """Remove model alias data."""
    set_juju_model_aliases({})


async def async_get_juju_model():
    """Retrieve current model.

    First check the environment for JUJU_MODEL. If this is not set, get the
    current active model.

    :returns: In focus model name
    :rtype: str
    """
    global CURRENT_MODEL
    if CURRENT_MODEL:
        return CURRENT_MODEL
    # LY: I think we should remove the KeyError handling. I don't think we
    #     should ever fall back to the model in focus because it will lead
    #     to functions being added which do not explicitly set a model and
    #     zaza will loose the ability to do concurrent runs.
    try:
        # Check the environment
        CURRENT_MODEL = os.environ["JUJU_MODEL"]
    except KeyError:
        try:
            CURRENT_MODEL = os.environ["MODEL_NAME"]
        except KeyError:
            # If unset connect get the current active model
            CURRENT_MODEL = await async_get_current_model()
    return CURRENT_MODEL

get_juju_model = sync_wrapper(async_get_juju_model)


async def deployed():
    """List deployed applications."""
    # Create a Model instance. We need to connect our Model to a Juju api
    # server before we can use it.
    model = Model()
    # Connect to the currently active Juju model
    await model.connect_current()
    try:
        # list currently deploeyd services
        return list(model.applications.keys())
    finally:
        # Disconnect from the api server and cleanup.
        await model.disconnect()

sync_deployed = sync_wrapper(deployed)


def get_unit_from_name(unit_name, model=None, model_name=None):
    """Return the units that corresponds to the name in the given model.

    :param unit_name: Name of unit to match
    :type unit_name: str
    :param model: Model to perform lookup in
    :type model: model.Model()
    :param model_name: Name of the model to perform lookup in
    :type model_name: string
    :returns: Unit matching given name
    :rtype: juju.unit.Unit or None
    :raises: UnitNotFound
    """
    app = unit_name.split('/')[0]
    unit = None
    try:
        if model is not None:
            units = model.applications[app].units
        else:
            units = get_units(application_name=app, model_name=model_name)
    except KeyError:
        msg = ('Application: {} does not exist in current model'.
               format(app))
        logging.error(msg)
        raise UnitNotFound(unit_name)
    for u in units:
        if u.entity_id == unit_name:
            unit = u
            break
    else:
        raise UnitNotFound(unit_name)
    return unit


@asynccontextmanager
@async_generator
async def run_in_model(model_name):
    """Context manager for executing code inside a libjuju model.

       Example of using run_in_model:
           async with run_in_model(model_name) as model:
               model.do_something()

    :param model_name: Name of model to run function in
    :type model_name: str
    :returns: The juju Model object correcsponding to model_name
    :rtype: Iterator[:class:'juju.Model()']
    """
    model = Model()
    if not model_name:
        model_name = await async_get_juju_model()
    await model.connect_model(model_name)
    try:
        await yield_(model)
    finally:
        await model.disconnect()


async def async_scp_to_unit(unit_name, source, destination, model_name=None,
                            user='ubuntu', proxy=False, scp_opts=''):
    """Transfer files to unit_name in model_name.

    :param model_name: Name of model unit is in
    :type model_name: str
    :param unit_name: Name of unit to scp to
    :type unit_name: str
    :param source: Local path of file(s) to transfer
    :type source: str
    :param destination: Remote destination of transferred files
    :type source: str
    :param user: Remote username
    :type source: str
    :param proxy: Proxy through the Juju API server
    :type proxy: bool
    :param scp_opts: Additional options to the scp command
    :type scp_opts: str
    """
    async with run_in_model(model_name) as model:
        unit = get_unit_from_name(unit_name, model)
        await unit.scp_to(source, destination, user=user, proxy=proxy,
                          scp_opts=scp_opts)

scp_to_unit = sync_wrapper(async_scp_to_unit)


async def async_scp_to_all_units(application_name, source, destination,
                                 model_name=None, user='ubuntu', proxy=False,
                                 scp_opts=''):
    """Transfer files from to all units of an application.

    :param model_name: Name of model unit is in
    :type model_name: str
    :param application_name: Name of application to scp file to
    :type application_name: str
    :param source: Local path of file(s) to transfer
    :type source: str
    :param destination: Remote destination of transferred files
    :type source: str
    :param user: Remote username
    :type source: str
    :param proxy: Proxy through the Juju API server
    :type proxy: bool
    :param scp_opts: Additional options to the scp command
    :type scp_opts: str
    """
    async with run_in_model(model_name) as model:
        for unit in model.applications[application_name].units:
            # FIXME: Should scp in parallel
            await unit.scp_to(source, destination, user=user, proxy=proxy,
                              scp_opts=scp_opts)

scp_to_all_units = sync_wrapper(async_scp_to_all_units)


async def async_scp_from_unit(unit_name, source, destination, model_name=None,
                              user='ubuntu', proxy=False, scp_opts=''):
    """Transfer files from to unit_name in model_name.

    :param model_name: Name of model unit is in
    :type model_name: str
    :param unit_name: Name of unit to scp from
    :type unit_name: str
    :param source: Remote path of file(s) to transfer
    :type source: str
    :param destination: Local destination of transferred files
    :type source: str
    :param user: Remote username
    :type source: str
    :param proxy: Proxy through the Juju API server
    :type proxy: bool
    :param scp_opts: Additional options to the scp command
    :type scp_opts: str
    """
    async with run_in_model(model_name) as model:
        unit = get_unit_from_name(unit_name, model)
        await unit.scp_from(source, destination, user=user, proxy=proxy,
                            scp_opts=scp_opts)


scp_from_unit = sync_wrapper(async_scp_from_unit)


async def async_run_on_unit(unit_name, command, model_name=None, timeout=None):
    """Juju run on unit.

    :param model_name: Name of model unit is in
    :type model_name: str
    :param unit_name: Name of unit to match
    :type unit: str
    :param command: Command to execute
    :type command: str
    :param timeout: How long in seconds to wait for command to complete
    :type timeout: int
    :returns: action.data['results'] {'Code': '', 'Stderr': '', 'Stdout': ''}
    :rtype: dict
    """
    async with run_in_model(model_name) as model:
        unit = get_unit_from_name(unit_name, model)
        action = await unit.run(command, timeout=timeout)
        results = action.data.get('results')
        if results:
            # In Juju 2.7 some keys are dropped from the results if there
            # value was empty. This breaks some functions downstream, so
            # ensure the keys are always present.
            for key in ['Stderr', 'Stdout']:
                results[key] = results.get(key, '')
            return results
        else:
            return {}

run_on_unit = sync_wrapper(async_run_on_unit)


async def async_run_on_leader(application_name, command, model_name=None,
                              timeout=None):
    """Juju run on leader unit.

    :param application_name: Application to match
    :type application_name: str
    :param command: Command to execute
    :type command: str
    :param model_name: Name of model unit is in
    :type model_name: str
    :param timeout: How long in seconds to wait for command to complete
    :type timeout: int
    :returns: action.data['results'] {'Code': '', 'Stderr': '', 'Stdout': ''}
    :rtype: dict
    """
    async with run_in_model(model_name) as model:
        for unit in model.applications[application_name].units:
            is_leader = await unit.is_leader_from_status()
            if is_leader:
                action = await unit.run(command, timeout=timeout)
                if action.data.get('results'):
                    return action.data.get('results')
                else:
                    return {}

run_on_leader = sync_wrapper(async_run_on_leader)


async def async_get_unit_time(unit_name, model_name=None, timeout=None):
    """Get the current time (in seconds since Epoch) on the given unit.

    :param model_name: Name of model to query.
    :type model_name: str
    :param unit_name: Name of unit to run action on
    :type unit_name: str
    :returns: time in seconds since Epoch on unit
    :rtype: int
    """
    out = await async_run_on_unit(
        unit_name=unit_name,
        command="date +'%s'",
        model_name=model_name,
        timeout=timeout)
    return int(out['Stdout'])

get_unit_time = sync_wrapper(async_get_unit_time)


async def async_get_unit_service_start_time(unit_name, service,
                                            model_name=None, timeout=None,
                                            pgrep_full=False):
    r"""Return the time that the given service was started on a unit.

    Return the time (in seconds since Epoch) that the oldest process of the
    given service was started on the given unit. If the service is not running
    raise ServiceNotRunning exception.

    If pgrep_full is True  ensure that any special characters in the name of
    the service are escaped e.g.

        service = 'aodh-evaluator: AlarmEvaluationService worker\(0\)'

    :param model_name: Name of model to query.
    :type model_name: str
    :param unit_name: Name of unit to run action on
    :type unit_name: str
    :param service: Name of service to check is running
    :type service: str
    :param timeout: Time to wait for status to be achieved
    :type timeout: int
    :param pgrep_full: Should pgrep be used rather than pidof to identify
                       a service.
    :type  pgrep_full: bool
    :returns: time in seconds since Epoch on unit
    :rtype: int
    :raises: ServiceNotRunning
    """
    if pgrep_full:
        pid_cmd = r"pgrep -o -f '{}'".format(service)
        cmd = "stat -c %Y /proc/$({})".format(pid_cmd)
    else:
        pid_cmd = r"pidof -x '{}'".format(service)
        cmd = pid_cmd + (
            "| "
            r"tr -d '\n' | "
            "xargs -d' ' -I {} stat -c %Y /proc/{}  | "
            "sort -n |"
            " head -1")
    out = await async_run_on_unit(
        unit_name=unit_name,
        command=cmd,
        model_name=model_name,
        timeout=timeout)
    out = out['Stdout'].strip()
    if out:
        return int(out)
    else:
        raise ServiceNotRunning(service)

get_unit_service_start_time = sync_wrapper(async_get_unit_service_start_time)


async def async_get_application(application_name, model_name=None):
    """Return an application object.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application to retrieve units for
    :type application_name: str
    :returns: Application object
    :rtype: object
    """
    async with run_in_model(model_name) as model:
        return model.applications[application_name]

get_application = sync_wrapper(async_get_application)


async def async_get_units(application_name, model_name=None):
    """Return all the units of a given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application to retrieve units for
    :type application_name: str
    :returns: List of juju units
    :rtype: [juju.unit.Unit, juju.unit.Unit,...]
    """
    async with run_in_model(model_name) as model:
        return model.applications[application_name].units

get_units = sync_wrapper(async_get_units)


async def async_get_machines(application_name, model_name=None):
    """Return all the machines of a given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application to retrieve units for
    :type application_name: str
    :returns: List of juju machines
    :rtype: [juju.machine.Machine, juju.machine.Machine,...]
    """
    async with run_in_model(model_name) as model:
        machines = []
        for unit in model.applications[application_name].units:
            machines.append(unit.machine)
        return machines

get_machines = sync_wrapper(async_get_machines)


def get_first_unit_name(application_name, model_name=None):
    """Return name of lowest numbered unit of given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: Name of lowest numbered unit
    :rtype: str
    """
    return get_units(application_name, model_name=model_name)[0].name


async def async_get_lead_unit_name(application_name, model_name=None):
    """Return name of unit with leader status for given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: Name of unit with leader status
    :rtype: str
    """
    async with run_in_model(model_name) as model:
        for unit in model.applications[application_name].units:
            is_leader = await unit.is_leader_from_status()
            if is_leader:
                return unit.entity_id

get_lead_unit_name = sync_wrapper(async_get_lead_unit_name)


def get_app_ips(application_name, model_name=None):
    """Return public address of all units of an application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: List of ip addresses
    :rtype: [str, str,...]
    """
    return [u.public_address
            for u in get_units(application_name, model_name=model_name)]


async def async_get_lead_unit_ip(application_name, model_name=None):
    """Return the IP address of the lead unit of a given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: IP of the lead unit
    :rtype: str
    """
    async with run_in_model(model_name) as model:
        for unit in model.applications[application_name].units:
            is_leader = await unit.is_leader_from_status()
            if is_leader:
                return unit.public_address


get_lead_unit_ip = sync_wrapper(async_get_lead_unit_ip)


async def async_get_application_config(application_name, model_name=None):
    """Return application configuration.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: Dictionary of configuration
    :rtype: dict
    """
    async with run_in_model(model_name) as model:
        return await model.applications[application_name].get_config()

get_application_config = sync_wrapper(async_get_application_config)


async def async_reset_application_config(application_name, config_keys,
                                         model_name=None):
    """Reset application configuration to default values.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param config_keys: List of configuration keys to reset to their defaults.
    :type config_keys: List[str]
    """
    async with run_in_model(model_name) as model:
        return await (model.applications[application_name]
                      .reset_config(config_keys))

reset_application_config = sync_wrapper(async_reset_application_config)


async def async_set_application_config(application_name, configuration,
                                       model_name=None):
    """Set application configuration.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param configuration: Dictionary of configuration setting(s)
    :type configuration: dict
    """
    async with run_in_model(model_name) as model:
        return await (model.applications[application_name]
                      .set_config(configuration))

set_application_config = sync_wrapper(async_set_application_config)


async def async_get_status(model_name=None):
    """Return full status.

    :param model_name: Name of model to query.
    :type model_name: str
    :returns: dictionary of juju status
    :rtype: dict
    """
    async with run_in_model(model_name) as model:
        return await model.get_status()

get_status = sync_wrapper(async_get_status)


class ActionFailed(Exception):
    """Exception raised when action fails."""

    def __init__(self, action):
        """Set information about action failure in message and raise."""
        params = {key: getattr(action, key, "<not-set>")
                  for key in ['name', 'parameters', 'receiver',
                              'message', 'id', 'status',
                              'enqueued', 'started', 'completed']}
        message = ('Run of action "{name}" with parameters "{parameters}" on '
                   '"{receiver}" failed with "{message}" (id={id} '
                   'status={status} enqueued={enqueued} started={started} '
                   'completed={completed})'
                   .format(**params))
        super(ActionFailed, self).__init__(message)


async def async_run_action(unit_name, action_name, model_name=None,
                           action_params=None, raise_on_failure=False):
    """Run action on given unit.

    :param unit_name: Name of unit to run action on
    :type unit_name: str
    :param action_name: Name of action to run
    :type action_name: str
    :param model_name: Name of model to query.
    :type model_name: str
    :param action_params: Dictionary of config options for action
    :type action_params: dict
    :param raise_on_failure: Raise ActionFailed exception on failure
    :type raise_on_failure: bool
    :returns: Action object
    :rtype: juju.action.Action
    :raises: ActionFailed
    """
    if action_params is None:
        action_params = {}

    async with run_in_model(model_name) as model:
        unit = get_unit_from_name(unit_name, model)
        action_obj = await unit.run_action(action_name, **action_params)
        await action_obj.wait()
        if raise_on_failure and action_obj.status != 'completed':
            raise ActionFailed(action_obj)
        return action_obj

run_action = sync_wrapper(async_run_action)


async def async_run_action_on_leader(application_name, action_name,
                                     model_name=None, action_params=None,
                                     raise_on_failure=False):
    """Run action on lead unit of the given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param action_name: Name of action to run
    :type action_name: str
    :param action_params: Dictionary of config options for action
    :type action_params: dict
    :param raise_on_failure: Raise ActionFailed exception on failure
    :type raise_on_failure: bool
    :returns: Action object
    :rtype: juju.action.Action
    :raises: ActionFailed
    """
    if action_params is None:
        action_params = {}

    async with run_in_model(model_name) as model:
        for unit in model.applications[application_name].units:
            is_leader = await unit.is_leader_from_status()
            if is_leader:
                action_obj = await unit.run_action(action_name,
                                                   **action_params)
                await action_obj.wait()
                if raise_on_failure and action_obj.status != 'completed':
                    raise ActionFailed(action_obj)
                return action_obj

run_action_on_leader = sync_wrapper(async_run_action_on_leader)


async def async_run_action_on_units(units, action_name, action_params=None,
                                    model_name=None, raise_on_failure=False,
                                    timeout=600):
    """Run action on list of unit in parallel.

    The action is run on all units first without waiting for the action to
    complete. Then block until they are done.

    :param units: List of unit names
    :type units: List[str]
    :param action_name: Name of action to run
    :type action_name: str
    :param action_params: Dictionary of config options for action
    :type action_params: dict
    :param model_name: Name of model to query.
    :type model_name: str
    :param raise_on_failure: Raise ActionFailed exception on failure
    :type raise_on_failure: bool
    :param timeout: Time to wait for actions to complete
    :type timeout: int
    :returns: Action object
    :rtype: juju.action.Action
    :raises: ActionFailed
    """
    if action_params is None:
        action_params = {}

    async with run_in_model(model_name) as model:
        actions = []
        for unit_name in units:
            unit = get_unit_from_name(unit_name, model)
            action_obj = await unit.run_action(action_name, **action_params)
            actions.append(action_obj)

        async def _check_actions():
            for action_obj in actions:
                if action_obj.status in ['running', 'pending']:
                    return False
            return True

        await async_block_until(_check_actions, timeout=timeout)

        for action_obj in actions:
            if raise_on_failure and action_obj.status != 'completed':
                raise ActionFailed(action_obj)

run_action_on_units = sync_wrapper(async_run_action_on_units)


async def async_remove_application(application_name, model_name=None,
                                   forcefully_remove_machines=False):
    """Remove application from model.

    :param application_name: Name of application
    :type application_name: str
    :param model_name: Name of model to query.
    :type model_name: str
    :param forcefully_remove_machines: Forcefully remove the machines the
                                      application is runing on.
    :type forcefully_remove_machines: bool
    """
    async with run_in_model(model_name) as model:
        application = model.applications[application_name]
        if forcefully_remove_machines:
            for unit in model.applications[application_name].units:
                await unit.machine.destroy(force=True)
        else:
            await application.remove()

remove_application = sync_wrapper(async_remove_application)


class UnitError(Exception):
    """Exception raised for units in error state."""

    def __init__(self, units):
        """Set units in error state in messgae and raise."""
        message = "Units {} in error state".format(
            ','.join([u.entity_id for u in units]))
        super(UnitError, self).__init__(message)


class ServiceNotRunning(Exception):
    """Exception raised when service not running."""

    def __init__(self, service):
        """Set not running services in messgae and raise."""
        message = "Service {} not running".format(service)
        super(ServiceNotRunning, self).__init__(message)


class CommandRunFailed(Exception):
    """Command failed to run."""

    def __init__(self, cmd, result):
        """Create Command run failed exception.

        :param cmd: Command that was run
        :type cmd: string
        :param result: Dict containing the output of the command
        :type result: dict - {'Code': '0', 'Stdout': '', 'Stderr':''}
        """
        code = result.get('Code')
        output = result.get('Stdout')
        err = result.get('Stderr')
        msg = ('Command {} failed with code {}, output {} and error {}'
               .format(cmd, code, output, err))
        super(CommandRunFailed, self).__init__(msg)


def units_with_wl_status_state(model, state):
    """Return a list of unit which have a matching workload status.

    :returns: Units in error state
    :rtype: [juju.Unit, ...]
    """
    matching_units = []
    for unit in model.units.values():
        wl_status = unit.workload_status
        if wl_status == state:
            matching_units.append(unit)
    return matching_units


async def async_resolve_units(application_name=None, wait=True, timeout=60,
                              erred_hook=None, model_name=None):
    """Mark all the errored units as resolved or limit to an application.

    :param application_name: Name of application
    :type application_name: str
    :param wait: Whether to wait for error state to have cleared.
    :type wait: bool
    :param timeout: Seconds to wait for an individual units state to clear.
    :type timeout: int
    :param erred_hook: Only resolve units that went into an error state when
                       running the specified hook.
    :type erred_hook: str
    :param model_name: Name of model to query.
    :type model_name: str
    """
    async with run_in_model(model_name) as model:
        erred_units = units_with_wl_status_state(model, 'error')

        if application_name:
            erred_units = [u for u in erred_units
                           if u.application == application_name]
        if erred_hook:
            erred_units = [u for u in erred_units
                           if erred_hook in u.workload_status_message]
        for u in erred_units:
            logging.info('Resolving unit: {}'.format(u.entity_id))
            # Use u.resolved() when implemented in libjuju
            cmd = ['juju', 'resolved', '-m', model.info.name, u.entity_id]
            subprocess.check_output(cmd)
        if wait:
            for unit in erred_units:
                await model.block_until(
                    lambda: not unit.workload_status == 'error',
                    timeout=timeout)

resolve_units = sync_wrapper(async_resolve_units)


def check_model_for_hard_errors(model):
    """Check model for any hard errors that should halt a deployment.

       The only check currently implemented is checking for units in an
       error state

    :raises: UnitError
    """
    errored_units = units_with_wl_status_state(model, 'error')
    if errored_units:
        raise UnitError(errored_units)


def check_unit_workload_status(model, unit, states):
    """Check that the units workload status matches the supplied state.

    This function has the side effect of also checking for *any* units
    in an error state and aborting if any are found.

    :param model: Model object to check in
    :type model: juju.Model
    :param unit: Unit to check wl status of
    :type unit: juju.Unit
    :param states: Acceptable unit work load states
    :type states: list
    :raises: UnitError
    :returns: Whether units workload status matches desired state
    :rtype: bool
    """
    check_model_for_hard_errors(model)
    return unit.workload_status in states


def check_unit_workload_status_message(model, unit, message=None,
                                       prefixes=None):
    """Check that the units workload status message.

    Check that the units workload status message matches the supplied
    message or starts with one of the supplied prefixes. Raises an exception
    if neither prefixes or message is set. This function has the side effect
    of also checking for *any* units in an error state and aborting if any
    are found.

    :param model: Model object to check in
    :type model: juju.Model
    :param unit: Unit to check wl status of
    :type unit: juju.Unit
    :param message: Expected message text
    :type message: str
    :param prefixes: Prefixes to match message against
    :type prefixes: list
    :raises: ValueError, UnitError
    :returns: Whether message matches desired string
    :rtype: bool
    """
    check_model_for_hard_errors(model)
    if message is not None:
        return unit.workload_status_message == message
    elif prefixes is not None:
        return unit.workload_status_message.startswith(tuple(prefixes))
    else:
        raise ValueError("Must be called with message or prefixes")


async def async_wait_for_agent_status(model_name=None, status='executing',
                                      timeout=60):
    """Wait for at least one unit to enter a specific agent status.

    This is useful for awaiting execution after mutating charm configuration.

    :param model_name: Name of model to query.
    :type model_name: str
    :param status: The desired agent status we are looking for.
    :type status: str
    :param timeout: Time to wait for status to be achieved.
    :type timeout: int
    """
    def one_agent_status(model, status):
        check_model_for_hard_errors(model)
        for app in model.applications:
            for unit in model.applications[app].units:
                agent_status = unit.data.get('agent-status', {})
                if agent_status.get('current', None) == status:
                    break
            else:
                continue
            break
        else:
            return False
        return True

    async with run_in_model(model_name) as model:
        logging.info('Waiting for at least one unit with agent status "{}"'
                     .format(status))
        await model.block_until(
            lambda: one_agent_status(model, status), timeout=timeout)

wait_for_agent_status = sync_wrapper(async_wait_for_agent_status)


async def async_wait_for_application_states(model_name=None, states=None,
                                            timeout=2700):
    """Wait for model to achieve the desired state.

    Check the workload status and workload status message for every unit of
    every application. By default look for an 'active' workload status and a
    message that starts with one of the approved_message_prefixes.

    Bespoke statuses and messages can be passed in with states. states takes
    the form::

        states = {
            'app': {
                'workload-status': 'blocked',
                'workload-status-message': 'No requests without a prod'}
            'anotherapp': {
                'workload-status-message': 'Unit is super ready'}}
        wait_for_application_states('modelname', states=states)

    :param model_name: Name of model to query.
    :type model_name: str
    :param states: States to look for
    :type states: dict
    :param timeout: Time to wait for status to be achieved
    :type timeout: int
    """
    approved_message_prefixes = ['ready', 'Ready', 'Unit is ready']
    approved_statuses = ['active']

    if not states:
        states = {}
    async with run_in_model(model_name) as model:
        check_model_for_hard_errors(model)
        logging.info("Waiting for a unit to appear")
        await model.block_until(
            lambda: len(model.units) > 0
        )
        logging.info("Waiting for all units to be idle")
        try:
            await model.block_until(
                lambda: units_with_wl_status_state(
                    model, 'error') or model.all_units_idle(),
                timeout=timeout)
        except concurrent.futures._base.TimeoutError:
            raise ModelTimeout("Zaza has timed out waiting on the model to "
                               "reach idle state.")
        errored_units = units_with_wl_status_state(model, 'error')
        if errored_units:
            raise UnitError(errored_units)

        timeout_msg = (
            "Timed out waiting for '{unit_name}'. The {gate_attr} "
            "is '{unit_state}' which is not one of '{approved_states}'")
        for application, app_data in model.applications.items():
            check_info = states.get(application, {})
            for unit in app_data.units:
                app_wls = check_info.get('workload-status')
                if app_wls:
                    all_approved_statuses = approved_statuses + [app_wls]
                else:
                    all_approved_statuses = approved_statuses
                logging.info("Checking workload status of {}".format(
                    unit.entity_id))
                try:
                    await model.block_until(
                        lambda: check_unit_workload_status(
                            model,
                            unit,
                            all_approved_statuses),
                        timeout=timeout)
                except concurrent.futures._base.TimeoutError:
                    raise ModelTimeout(
                        timeout_msg.format(
                            unit_name=unit.entity_id,
                            gate_attr='workload status',
                            unit_state=unit.workload_status,
                            approved_states=all_approved_statuses))

                check_msg = check_info.get('workload-status-message')
                logging.info("Checking workload status message of {}"
                             .format(unit.entity_id))
                prefixes = approved_message_prefixes
                if check_msg is not None:
                    prefixes = approved_message_prefixes + [check_msg]
                else:
                    prefixes = approved_message_prefixes
                try:
                    await model.block_until(
                        lambda: check_unit_workload_status_message(
                            model,
                            unit,
                            prefixes=prefixes),
                        timeout=timeout)
                except concurrent.futures._base.TimeoutError:
                    raise ModelTimeout(
                        timeout_msg.format(
                            unit_name=unit.entity_id,
                            gate_attr='workload status message',
                            unit_state=unit.workload_status_message,
                            approved_states=prefixes))


wait_for_application_states = sync_wrapper(async_wait_for_application_states)


async def async_block_until_all_units_idle(model_name=None, timeout=2700):
    """Block until all units in the given model are idle.

    An example accessing this function via its sync wrapper::

        block_until_all_units_idle('modelname')

    :param model_name: Name of model to query.
    :type model_name: str
    :param timeout: Time to wait for status to be achieved
    :type timeout: float
    """
    async with run_in_model(model_name) as model:
        await model.block_until(
            lambda: units_with_wl_status_state(
                model, 'error') or model.all_units_idle(),
            timeout=timeout)
        errored_units = units_with_wl_status_state(model, 'error')
        if errored_units:
            raise UnitError(errored_units)

block_until_all_units_idle = sync_wrapper(async_block_until_all_units_idle)


async def async_block_until_unit_count(application, target_count,
                                       model_name=None, timeout=2700):
    """Block until the number of units matches target_count.

    An example accessing this function via its sync wrapper::

        block_until_unit_count('keystone', 4)

    :param application_name: Name of application
    :type application_name: str
    :param target_count: Number of expected units.
    :type target_count: int
    :param model_name: Name of model to interact with.
    :type model_name: str
    :param timeout: Time to wait for status to be achieved
    :type timeout: float
    """
    async def _check_unit():
        model_status = await async_get_status()
        unit_count = len(model_status.applications[application]['units'])
        return unit_count == target_count

    assert target_count == int(target_count), "target_count not an int"
    async with run_in_model(model_name):
        await async_block_until(_check_unit, timeout=timeout)

block_until_unit_count = sync_wrapper(
    async_block_until_unit_count)


async def async_block_until_charm_url(application, target_url,
                                      model_name=None, timeout=2700):
    """Block until the charm url matches target_url.

    An example accessing this function via its sync wrapper::

        block_until_charm_url('cinder', 'cs:openstack-charmers-next/cinder')

    :param application_name: Name of application
    :type application_name: str
    :param target_url: Target charm url
    :type target_url: str
    :param model_name: Name of model to interact with.
    :type model_name: str
    :param timeout: Time to wait for status to be achieved
    :type timeout: float
    """
    async def _check_charm_url():
        model_status = await async_get_status()
        charm_url = model_status.applications[application]['charm']
        return charm_url == target_url

    async with run_in_model(model_name):
        await async_block_until(_check_charm_url, timeout=timeout)


block_until_charm_url = sync_wrapper(
    async_block_until_charm_url)


async def async_block_until_service_status(unit_name, services, target_status,
                                           model_name=None, timeout=2700,
                                           pgrep_full=False):
    """Block until all services on the unit are in the desired state.

    Block until all services on the unit are in the desired state (stopped
    or running)::

        block_until_service_status(
            first_unit,
            ['glance-api'],
            'running',
            model_name='modelname')

    :param unit_name: Name of unit to run action on
    :type unit_name: str
    :param services: List of services to check
    :type services: []
    :param target_status: State services should be in (stopped or running)
    :type target_status: str
    :param model_name: Name of model to query.
    :type model_name: str
    :param pgrep_full: Should pgrep be used rather than pidof to identify
                       a service.
    :type  pgrep_full: bool
    :param timeout: Time to wait for status to be achieved
    :type timeout: int
    """
    async def _check_service():
        for service in services:
            if pgrep_full:
                command = r"pgrep -f '{}'".format(service)
            else:
                command = r"pidof -x '{}'".format(service)
            out = await async_run_on_unit(
                unit_name,
                command,
                model_name=model_name,
                timeout=timeout)
            response_size = len(out['Stdout'].strip())
            if target_status == "running" and response_size == 0:
                return False
            elif target_status == "stopped" and response_size > 0:
                return False
        return True
    async with run_in_model(model_name):
        await async_block_until(_check_service, timeout=timeout)

block_until_service_status = sync_wrapper(async_block_until_service_status)


def get_actions(application_name, model_name=None):
    """Get the actions an applications supports.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: Dictionary of actions and their descriptions
    :rtype: dict
    """
    if not model_name:
        model_name = get_juju_model()
    # libjuju has not implemented get_actions yet
    # https://github.com/juju/python-libjuju/issues/226
    cmd = ['juju', 'actions', '-m', model_name, application_name,
           '--format', 'yaml']
    return yaml.safe_load(subprocess.check_output(cmd))


async def async_get_current_model():
    """Return the current active model name.

    Connect to the current active model and return its name.

    :returns: String curenet model name
    :rtype: str
    """
    model = Model()
    await model.connect()
    model_name = model.info.name
    await model.disconnect()
    return model_name


get_current_model = sync_wrapper(async_get_current_model)


async def async_block_until(*conditions, timeout=None, wait_period=0.5,
                            loop=None):
    """Return only after all async conditions are true.

    Based on juju.utils.block_until which currently does not support
    async methods as conditions.

    :param conditions: Functions to evaluate.
    :type conditions: functions
    :param timeout: Timeout in seconds
    :type timeout: float
    :param wait_period: Time to wait between re-assessing conditions.
    :type wait_period: float
    :param loop: The event loop to use
    :type loop: An event loop
    """
    async def _block():
        while True:
            evaluated = []
            for c in conditions:
                result = await c()
                evaluated.append(result)
            if all(evaluated):
                return
            else:
                await asyncio.sleep(wait_period, loop=loop)
    await asyncio.wait_for(_block(), timeout, loop=loop)


block_until = sync_wrapper(async_block_until)


async def async_block_until_file_ready(application_name, remote_file,
                                       check_function, model_name=None,
                                       timeout=2700):
    """Block until the check_function passes against.

    Block until the check_function passes against the provided file. It is
    unlikely that a test would call this function directly, rather it is
    provided as scaffolding for tests with a more specialised purpose.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param remote_file: Remote path of file to transfer
    :type remote_file: str
    :param check_function: Function to use to check if file is ready, must take
                           exactly one argument which is the file contents.
    :type check_function: function
    :param timeout: Time to wait for contents to appear in file
    :type timeout: float
    """
    async def _check_file():
        units = model.applications[application_name].units
        for unit in units:
            try:
                output = await unit.run('cat {}'.format(remote_file))
                contents = output.data.get('results').get('Stdout', '')
                if not check_function(contents):
                    return False
            # libjuju throws a generic error for connection failure. So we
            # cannot differentiate between a connectivity issue and a
            # target file not existing error. For now just assume the
            # latter.
            except JujuError:
                return False
        else:
            return True

    async with run_in_model(model_name) as model:
        await async_block_until(_check_file, timeout=timeout)


async def async_block_until_file_has_contents(application_name, remote_file,
                                              expected_contents,
                                              model_name=None, timeout=2700):
    """Block until the expected_contents are present on all units.

    Block until the given string (expected_contents) is present in the file
    (remote_file) on all units of the given application.

    An example accessing this function via its sync wrapper::

        block_until_file_has_contents(
            'modelname'
            'keystone',
            '/etc/apache2/apache2.conf',
            'KeepAlive On')


    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param remote_file: Remote path of file to transfer
    :type remote_file: str
    :param expected_contents: String to look for in file
    :type expected_contents: str
    :param timeout: Time to wait for contents to appear in file
    :type timeout: float
    """
    def f(x):
        return expected_contents in x
    return await async_block_until_file_ready(
        application_name,
        remote_file,
        f,
        timeout=timeout,
        model_name=model_name)

block_until_file_has_contents = sync_wrapper(
    async_block_until_file_has_contents)


async def async_block_until_file_missing(
        app, path, model_name=None, timeout=2700):
    """Block until the file at path is not there.

    Block until the file at the param 'path' is not present on the file system
    for all units on a given application.

    An example accessing this function via its sync wrapper::

        block_until_file_missing(
            'keystone',
            '/some/path/name')


    :param app: the application name
    :type app: str
    :param path: the file name to check for.
    :type path: str
    :param model_name: Name of model to query.
    :type model_name: str
    :param timeout: Time to wait for contents to appear in file
    :type timeout: float
    """
    async def _check_for_file(model):
        units = model.applications[app].units
        results = []
        for unit in units:
            try:
                output = await unit.run('test -e "{}"; echo $?'.format(path))
                contents = output.data.get('results')['Stdout']
                results.append("1" in contents)
            # libjuju throws a generic error for connection failure. So we
            # cannot differentiate between a connectivity issue and a
            # target file not existing error. For now just assume the
            # latter.
            except JujuError:
                results.append(False)
        return all(results)

    async with run_in_model(model_name) as model:
        await async_block_until(lambda: _check_for_file(model),
                                timeout=timeout)

block_until_file_missing = sync_wrapper(async_block_until_file_missing)


async def async_block_until_oslo_config_entries_match(application_name,
                                                      remote_file,
                                                      expected_contents,
                                                      model_name=None,
                                                      timeout=2700):
    """Block until dict is represented in the file using oslo.config parser.

    Block until the expected_contents are in the given file on all units of
    the application. For example to check for the following configuration::

        [DEFAULT]
        debug = False

        [glance_store]
        filesystem_store_datadir = /var/lib/glance/images/
        default_store = file

    Call the check via its sync wrapper::

        expected_contents = {
            'DEFAULT': {
                'debug': ['False']},
            'glance_store': {
                'filesystem_store_datadir': ['/var/lib/glance/images/'],
                 'default_store': ['file']}}

        block_until_oslo_config_entries_match(
            'modelname',
            'glance',
            '/etc/glance/glance-api.conf',
            expected_contents)

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param remote_file: Remote path of file to transfer
    :type remote_file: str
    :param expected_contents: The key value pairs in their corresponding
                              sections to be looked for in the remote_file
    :type expected_contents: {}
    :param timeout: Time to wait for contents to appear in file
    :type timeout: float

    """
    def f(x):
        # Writing out the file that was just read is suboptimal
        with tempfile.NamedTemporaryFile(mode='w', delete=True) as fp:
            fp.write(x)
            fp.seek(0)
            sections = {}
            parser = cfg.ConfigParser(fp.name, sections)
            parser.parse()
            for section, entries in expected_contents.items():
                for key, value in entries.items():
                    if sections.get(section, {}).get(key) != value:
                        return False
        return True
    return await async_block_until_file_ready(
        application_name,
        remote_file,
        f,
        timeout=timeout,
        model_name=model_name)


block_until_oslo_config_entries_match = sync_wrapper(
    async_block_until_oslo_config_entries_match)


async def async_block_until_services_restarted(application_name, mtime,
                                               services, model_name=None,
                                               timeout=2700, pgrep_full=False):
    """Block until the given services have a start time later then mtime.

    For example to check that the glance-api service has been restarted::

        block_until_services_restarted(
            'modelname'
            'glance',
            1528294585,
            ['glance-api'])

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param mtime: Time in seconds since Epoch to check against
    :type mtime: int
    :param services: Listr of services to check restart time of
    :type services: []
    :param timeout: Time to wait for services to be restarted
    :type timeout: float
    :param pgrep_full: Should pgrep be used rather than pidof to identify
                       a service.
    :type  pgrep_full: bool
    """
    async def _check_service():
        units = model.applications[application_name].units
        for unit in units:
            for service in services:
                try:
                    svc_mtime = await async_get_unit_service_start_time(
                        unit.entity_id,
                        service,
                        timeout=timeout,
                        model_name=model_name,
                        pgrep_full=pgrep_full)
                except ServiceNotRunning:
                    return False
                if svc_mtime < mtime:
                    return False
        return True
    async with run_in_model(model_name) as model:
        await async_block_until(_check_service, timeout=timeout)


block_until_services_restarted = sync_wrapper(
    async_block_until_services_restarted)


async def async_block_until_unit_wl_status(unit_name, status, model_name=None,
                                           negate_match=False, timeout=2700,
                                           subordinate_principal=None):
    """Block until the given unit has the desired workload status.

    A units workload status may change during a given action. This function
    blocks until the given unit has the desired workload status::

         block_until_unit_wl_status(
            aunit,
            'active'
            model_name='modelname')

    NOTE: unit.workload_status was actually reporting the application workload
          status. Using the full status output from model.get_status() gives us
          unit by unit workload status.

    :param unit_name: Name of unit
    :type unit_name: str
    :param status: Status to wait for (active, maintenance etc)
    :type status: str
    :param model_name: Name of model to query.
    :type model_name: str
    :param negate_match: Wait until the match is not true.
    :type negate_match: bool
    :param timeout: Time to wait for unit to achieved desired status
    :type timeout: float
    :param subordinate_principal: Name of the principal of unit_name, if
                                  unit_name is a subordinate
    :type subordinate_principal: str
    """
    async def _unit_status():
        app = unit_name.split("/")[0]
        model_status = await async_get_status()
        try:
            v = model_status.applications[app]['units'][unit_name][
                'workload-status']['status']
        except (TypeError, KeyError):
            # For when the unit is a subordinate we need to get it's
            # leader, and then get the status for the subordinate from its
            # unit
            lead_app_name = subordinate_principal
            if not subordinate_principal:
                lead_app_name = model_status.applications[app][
                    'subordinate-to'][0]
            units = model_status.applications[lead_app_name]['units']
            for unit in units.values():
                try:
                    v = unit['subordinates'][unit_name][
                        'workload-status']['status']
                    break
                except KeyError:
                    pass
            else:  # pragma: no cover
                raise ValueError('{} does not exist as a subordinate under a '
                                 'principal'.format(unit_name))
        if negate_match:
            return v != status
        else:
            return v == status

    async with run_in_model(model_name):
        await async_block_until(_unit_status, timeout=timeout)

block_until_unit_wl_status = sync_wrapper(
    async_block_until_unit_wl_status)


async def async_block_until_wl_status_info_starts_with(
        app, status, model_name=None, negate_match=False, timeout=2700):
    """Block until the all the units have a desired workload status.

    Block until all of the units have a desired workload status that starts
    with the string in the status param.

    :param app: the application to check against
    :type app: str
    :param status: Status to wait for at the start of the string
    :type status: str
    :param model_name: Name of model to query.
    :type model_name: Union[None, str]
    :param negate_match: Wait until the match is not true; i.e. none match
    :type negate_match: Union[None, bool]
    :param timeout: Time to wait for unit to achieved desired status
    :type timeout: float
    """
    async def _unit_status():
        model_status = await async_get_status()
        wl_infos = [v['workload-status']['info']
                    for k, v in model_status.applications[app]['units'].items()
                    if k.split('/')[0] == app]
        g = (s.startswith(status) for s in wl_infos)
        if negate_match:
            return not(any(g))
        else:
            return all(g)

    async with run_in_model(model_name):
        await async_block_until(_unit_status, timeout=timeout)


block_until_wl_status_info_starts_with = sync_wrapper(
    async_block_until_wl_status_info_starts_with)


async def async_get_relation_id(application_name, remote_application_name,
                                model_name=None,
                                remote_interface_name=None):
    """
    Get relation id of relation from model.

    :param model_name: Name of model to operate on
    :type model_name: str
    :param application_name: Name of application on this side of relation
    :type application_name: str
    :param remote_application_name: Name of application on other side of
                                    relation
    :type remote_application_name: str
    :param remote_interface_name: Name of interface on remote end of relation
    :type remote_interface_name: Optional(str)
    :returns: Relation id of relation if found or None
    :rtype: any
    """
    async with run_in_model(model_name) as model:
        for rel in model.applications[application_name].relations:
            spec = '{}'.format(remote_application_name)
            if remote_interface_name is not None:
                spec += ':{}'.format(remote_interface_name)
            if rel.matches(spec):
                return(rel.id)

get_relation_id = sync_wrapper(async_get_relation_id)


async def async_add_relation(application_name, local_relation, remote_relation,
                             model_name=None):
    """
    Add relation between applications.

    :param application_name: Name of application on this side of relation
    :type application_name: str
    :param local_relation: Name of relation on this application
    :type local_relation: str
    :param remote_relation: Name of relation on the other application.
    :type remote_relation: str ‘<application>[:<relation_name>]’
    :param model_name: Name of model to operate on.
    :type model_name: str
    """
    async with run_in_model(model_name) as model:
        app = model.applications[application_name]
        await app.add_relation(local_relation, remote_relation)

add_relation = sync_wrapper(async_add_relation)


async def async_remove_relation(application_name, local_relation,
                                remote_relation, model_name=None):
    """
    Remove relation between applications.

    :param application_name: Name of application on this side of relation
    :type application_name: str
    :param local_relation: Name of relation on this application
    :type local_relation: str
    :param remote_relation: Name of relation on the other application.
    :type remote_relation: str ‘<application>[:<relation_name>]’
    :param model_name: Name of model to operate on.
    :type model_name: str
    """
    async with run_in_model(model_name) as model:
        app = model.applications[application_name]
        await app.destroy_relation(local_relation, remote_relation)

remove_relation = sync_wrapper(async_remove_relation)


async def async_add_unit(application_name, count=1, to=None, model_name=None,
                         wait_appear=False):
    """
    Add unit(s) to an application.

    :param application_name: Name of application to add unit(s) to
    :type application_name: str
    :param count: Number of units to add
    :type count: int
    :param to: Location to add unit i.e. lxd:0
    :type to: str
    :param model_name: Name of model to operate on.
    :type model_name: str
    :param wait_appear: Whether to wait for the unit to appear in juju status
    :type wait_appear: bool
    """
    async with run_in_model(model_name) as model:
        app = model.applications[application_name]
        current_unit_count = len(app.units)
        await app.add_unit(count=count, to=to)
        if wait_appear:
            target_count = current_unit_count + count
            await async_block_until_unit_count(
                application_name,
                target_count,
                model_name=model_name)

add_unit = sync_wrapper(async_add_unit)


async def async_destroy_unit(application_name, *unit_names, model_name=None,
                             wait_disappear=False):
    """
    Remove unit(s) of an application.

    :param application_name: Name of application to remove unit(s) from
    :type application_name: str
    :parm unit_names: One or more unit names. i.e. app/0
    :type unit_name: str(s)
    :param model_name: Name of model to operate on.
    :type model_name: str
    :param wait_disappear: Whether to wait for the unit to disappear from juju
                           status
    :type wait_disappear: bool
    """
    async with run_in_model(model_name) as model:
        app = model.applications[application_name]
        current_unit_count = len(app.units)
        await app.destroy_unit(*unit_names)
        if wait_disappear:
            target_count = current_unit_count - len(unit_names)
            await async_block_until_unit_count(
                application_name,
                target_count,
                model_name=model_name)

destroy_unit = sync_wrapper(async_destroy_unit)


def set_model_constraints(constraints, model_name=None):
    """
    Set constraints on a model.

    Note: Subprocessing out to 'juju' is a temporary solution until
          https://bit.ly/2ujbVPA lands in libjuju.

    :param model_name: Name of model to operate on
    :type model_name: str
    :param constraints: Constraints to be applied to model
    :type constraints: dict

    """
    if not constraints:
        return
    if not model_name:
        model_name = get_juju_model()
    cmd = ['juju', 'set-model-constraints', '-m', model_name]
    cmd.extend(['{}={}'.format(k, v) for k, v in constraints.items()])
    subprocess.check_call(cmd)


async def async_upgrade_charm(application_name, channel=None,
                              force_series=False, force_units=False,
                              path=None, resources=None, revision=None,
                              switch=None, model_name=None):
    """
    Upgrade the given charm.

    :param application_name: Name of application on this side of relation
    :type application_name: str
    :param channel: Channel to use when getting the charm from the charm store,
                    e.g. 'development'
    :type channel: str
    :param force_series: Upgrade even if series of deployed application is not
                         supported by the new charm
    :type force_series: bool
    :param force_units: Upgrade all units immediately, even if in error state
    :type force_units: bool
    :param path: Uprade to a charm located at path
    :type path: str
    :param resources: Dictionary of resource name/filepath pairs
    :type resources: dict
    :param revision: Explicit upgrade revision
    :type revision: int
    :param switch: Crossgrade charm url
    :type switch: str
    :param model_name: Name of model to operate on
    :type model_name: str
    """
    async with run_in_model(model_name) as model:
        app = model.applications[application_name]
        await app.upgrade_charm(
            channel=channel,
            force_series=force_series,
            force_units=force_units,
            path=path,
            resources=resources,
            revision=revision,
            switch=switch)

upgrade_charm = sync_wrapper(async_upgrade_charm)


async def async_get_latest_charm_url(charm_url, channel=None, model_name=None):
    """Get charm url, including revision number, for latest charm version.

    :param charm_url: Charm url without revision number
    :type charm_url: str
    :param channel: Channel to use when getting the charm from the charm store,
                    e.g. 'development'
    :type channel: str
    :param model_name: Name of model to operate on
    :type model_name: str
    """
    async with run_in_model(model_name) as model:
        charmstore_entity = await model.charmstore.entity(
            charm_url,
            channel=channel)
        return charmstore_entity['Id']

get_latest_charm_url = sync_wrapper(async_get_latest_charm_url)


class UnitNotFound(Exception):
    """Unit was not found in model."""

    def __init__(self, unit_name):
        """Create a UnitNotFound exception.

        :param unit_name: Name of the unit
        :type unit_name: string
        """
        msg = ('Unit: {} was not found in current model'.
               format(unit_name))
        super(UnitNotFound, self).__init__(msg)


# NOTE: The following are series upgrade related functions which are new
# features in juju. We can migrate to libjuju calls when the feature
# stabilizes.
def prepare_series_upgrade(machine_num, to_series="xenial"):
    """Execute juju series-upgrade prepare on machine.

    NOTE: This is a new feature in juju behind a feature flag and not yet in
    libjuju.
    export JUJU_DEV_FEATURE_FLAGS=upgrade-series

    :param machine_num: Machine number
    :type machine_num: str
    :param to_series: The series to which to upgrade
    :type to_series: str
    :returns: None
    :rtype: None
    """
    juju_model = get_juju_model()
    cmd = ["juju", "upgrade-series", "-m", juju_model,
           machine_num, "prepare", to_series, "--yes"]
    subprocess.check_call(cmd)


def complete_series_upgrade(machine_num):
    """Execute juju series-upgrade complete on machine.

    NOTE: This is a new feature in juju behind a feature flag and not yet in
    libjuju.
    export JUJU_DEV_FEATURE_FLAGS=upgrade-series

    :param machine_num: Machine number
    :type machine_num: str
    :returns: None
    :rtype: None
    """
    juju_model = get_juju_model()
    cmd = ["juju", "upgrade-series", "-m", juju_model,
           machine_num, "complete"]
    subprocess.check_call(cmd)


def set_series(application, to_series):
    """Execute juju set-series complete on application.

    NOTE: This is a new feature in juju and not yet in libjuju.

    :param application: Name of application to upgrade series
    :type application: str
    :param to_series: The series to which to upgrade
    :type to_series: str
    :returns: None
    :rtype: None
    """
    juju_model = get_juju_model()
    cmd = ["juju", "set-series", "-m", juju_model,
           application, to_series]
    subprocess.check_call(cmd)


def attach_resource(application, resource_name, resource_path):
    """Attach resource to charm.

    :param application: Application to get leader settings from.
    :type application: str
    :param resource_name: The name of the resource as defined in metadata.yaml
    :type resource_name: str
    :param resource_path: The path to the resource on disk
    :type resource_path: str
    :returns: None
    :rtype: None
    """
    juju_model = get_juju_model()
    cmd = ["juju", "attach-resource", "-m", juju_model,
           application, "{}={}".format(resource_name, resource_path)]
    subprocess.check_call(cmd)


async def async_run_on_machine(
    machine,
    command,
    model_name=None,
    timeout=None
):
    """Juju run on unit.

    This function uses a spawned process to run the `juju run` command rather
    that a native libjuju call as libjuju hasn't implemented `juju.Machine.run`
    yet: https://github.com/juju/python-libjuju/issues/403

    :param model_name: Name of model unit is in
    :type model_name: str
    :param unit_name: Name of unit to match
    :type unit: str
    :param command: Command to execute
    :type command: str
    :param timeout: How long in seconds to wait for command to complete
    :type timeout: int
    :returns: action.data['results'] {'Code': '', 'Stderr': '', 'Stdout': ''}
    :rtype: dict
    """
    cmd = ['juju', 'run', '--machine={}'.format(machine)]
    if model_name:
        cmd.append('--model={}'.format(model_name))
    if timeout:
        cmd.append('--timeout={}'.format(timeout))
    cmd.append(command)
    logging.info("About to call '{}'".format(cmd))
    await generic_utils.check_call(cmd)


run_on_machine = sync_wrapper(async_run_on_machine)


async def async_wait_for_unit_idle(
    unit_name,
    timeout=600,
    include_subordinates=False
):
    """Wait until the unit's agent is idle.

    :param unit_name: The unit name of the application, ex: mysql/0
    :type unit_name: str
    :param timeout: How long to wait before timing out
    :type timeout: int
    :param include_subordinates: Should this function wait for subordinate idle
    :type include_subordinates: bool
    :returns: None
    :rtype: None
    """
    app = unit_name.split('/')[0]

    def _unit_idle(app, unit_name):
        async def f():
            x = await async_get_agent_status(app, unit_name)
            if include_subordinates:
                subs_idle = await async_check_if_subordinates_idle(
                    app, unit_name)
            else:
                subs_idle = True
            return x == "idle" and subs_idle
        return f

    try:
        await async_block_until(
            _unit_idle(app, unit_name),
            timeout=timeout)
    except concurrent.futures._base.TimeoutError:
        raise ModelTimeout("Zaza has timed out waiting on {} to "
                           "reach idle state.".format(unit_name))


wait_for_unit_idle = sync_wrapper(async_wait_for_unit_idle)


async def async_get_agent_status(app, unit_name):
    """Get the current status of the specified unit.

    :param app: The name of the Juju application, ex: mysql
    :type app: str
    :param unit_name: The unit name of the application, ex: mysql/0
    :type unit_name: str
    :returns: The agent status, either active / idle, returned by Juju
    :rtype: str
    """
    return (await async_get_status()). \
        applications[app]['units'][unit_name]['agent-status']['status']


get_agent_status = sync_wrapper(async_get_agent_status)


async def async_check_if_subordinates_idle(app, unit_name):
    """Check if the specified unit's subordinatesare idle.

    :param app: The name of the Juju application, ex: mysql
    :type app: str
    :param unit_name: The unit name of the application, ex: mysql/0
    :type unit_name: str
    :returns: The agent status, either active / idle, returned by Juju
    :rtype: str
    """
    status = await async_get_status()
    subordinates = status.applications[app]['units'][unit_name].get(
        'subordinates', [])
    if not subordinates:
        return True
    statuses = [
        unit['agent-status']['status']
        for name, unit in subordinates.items()]
    return len(set(statuses)) == 1 and statuses[0] == 'idle'
