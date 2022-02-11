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
import collections
import datetime
import logging
import os
import re
import subprocess
import tempfile
import yaml
from oslo_config import cfg
import concurrent
import time

import juju.client
from juju.errors import JujuError
from juju.model import Model

from zaza import sync_wrapper
import zaza.utilities.generic as generic_utils
import zaza.utilities.exceptions as zaza_exceptions

# Default for the Juju MAX_FRAME_SIZE to be 256MB to stop
# "RPC: Connection closed, reconnecting" errors and then a failure in the log.
# See https://github.com/juju/python-libjuju/issues/458 for more details
JUJU_MAX_FRAME_SIZE = 2**30

CURRENT_MODEL = None
MODEL_ALIASES = {}


class ModelTimeout(Exception):
    """Model timeout exception."""

    pass


class RemoteFileError(Exception):
    """Error with a remote file."""

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


async def deployed(model_name=None):
    """List deployed applications.

    :param model_name: Name of the model to list applications from
    :type model_name: string
    """
    # Create a Model instance. We need to connect our Model to a Juju api
    # server before we can use it.
    # NOTE(tinwood): Due to https://github.com/juju/python-libjuju/issues/458
    # set the max frame size to something big to stop
    # "RPC: Connection closed, reconnecting" messages and then failures.
    model = Model(max_frame_size=JUJU_MAX_FRAME_SIZE)
    if not model_name:
        # Connect to the currently active Juju model
        await model.connect_current()
    else:
        await model.connect_model(model_name)

    try:
        # list currently deployed services
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


# A collection of model name -> libjuju models associations; use to either
# instantiate or handout a model, or start a new one.
ModelRefs = {}


async def get_model_memo(model_name):
    model = None
    if model_name in ModelRefs:
        model = ModelRefs[model_name]
        if is_model_disconnected(model):
            try:
                await model.disconnect()
            except Exception:
                pass
            model = None
            del ModelRefs[model_name]
    if model is None:
        # NOTE(tinwood): Due to
        # https://github.com/juju/python-libjuju/issues/458 set the max frame
        # size to something big to stop "RPC: Connection closed, reconnecting"
        # messages and then failures.
        model = Model(max_frame_size=JUJU_MAX_FRAME_SIZE)
        await model.connect(model_name)
        ModelRefs[model_name] = model
    return model


async def remove_model_memo(model_name):
    global ModelRefs
    try:
        model = ModelRefs[model_name]
        del ModelRefs[model_name]
        await model.disconnect()
    except Exception:
        pass


async def remove_models_memo():
    model_names = list(ModelRefs.keys())
    for model_name in model_names:
        await remove_model_memo(model_name)


@asynccontextmanager
@async_generator
async def run_in_model(model_name):
    """Context manager for executing code inside a libjuju model.

       Example of using run_in_model:
           async with run_in_model(model_name) as model:
               model.do_something()

    Note: that this function re-uses an existing Model connection as zaza (now)
    tries to keep the model connected for the entire run that it is needed.
    This is so that libjuju objects connected to the model continue to be
    updated and that associated methods on those objects continue to function.

    Use zaza.model.connect_model(model_name) and
    zaza.model.disconnect_mode(model_name) to control the lifetime of
    connecting to a model.

    :param model_name: Name of model to run function in
    :type model_name: str
    :returns: The juju Model object correcsponding to model_name
    :rtype: Iterator[:class:'juju.Model()']
    """
    # NOTE(tinwood): Due to https://github.com/juju/python-libjuju/issues/458
    # set the max frame size to something big to stop
    # "RPC: Connection closed, reconnecting" messages and then failures.
    # model = Model(max_frame_size=JUJU_MAX_FRAME_SIZE)
    # if not model_name:
        # model_name = await async_get_juju_model()
    # await model.connect_model(model_name)
    # try:
        # await yield_(model)
    # finally:
        # await model.disconnect()
    if not model_name:
        model_name = await async_get_juju_model()
    model = await get_model_memo(model_name)
    # This doesn't need to be a generator as we now keep models alive until
    # they are disconnected.
    await yield_(model)


def is_model_disconnected(model):
    """Return True if the model is disconnected.

    :param model: the model to check
    :type model: :class:'juju.Model'
    :returns: True if disconnected
    :rtype: bool
    """
    return not (model.is_connected() and model.connection().is_open)


async def ensure_model_connected(model):
    """Ensure that the model is connected.

    If model is disconnected then reconnect it.

    :param model: the model to check
    :type model: :class:'juju.Model'
    """
    if is_model_disconnected(model):
        model_name = model.info.name
        logging.warning(
            "model: %s has disconnected, forcing full disconnection "
            "and then reconnecting ...", model_name)
        try:
            await model.disconnect()
        except Exception:
            # We don't care if disconnect fails; we're much more
            # interested in re-connecting, and this is just to clean up
            # anything that might be left over (i.e.
            # model.is_connected() might be true, but
            # model.connection().is_open may be false
            pass
        logging.warning("Attempting to reconnect model %s", model_name)
        await model.connect_model(model_name)


async def block_until_auto_reconnect_model(*conditions,
                                           model=None,
                                           aconditions=None,
                                           timeout=None,
                                           wait_period=0.5):
    """Async block on the model until conditions met.

    This function doesn't use model.block_until() which unfortunately raises
    websockets.exceptions.ConnectionClosed if the connections gets closed,
    which seems to happen quite frequently.  This funtion blocks until the
    conditions are met or a timeout occurs, and reconnects the model if it
    becomes disconnected.

    Note that conditions are just passed as an unamed list in the function call
    to make it work more like the more simple 'block_until' function.

    Note: conditions must capture libjuju objects in closures as the model may
    change if it is disconnected. The closures should refetch the juju objects
    from the model as needed.

    :param model: the model to use
    :type model: :class:'juju.Model()'
    :param conditions: a list of callables that need to evaluate to True.
    :type conditions: [List[Callable[[:class:'juju.Model()'], bool]]]
    :param aconditions: an optional list of async callables that need to
        evaluate to True.
    :type aconditions:
        Optional[List[AsyncCallable[[:class:'juju.Model()'], bool]]]
    :param timeout: the timeout to wait for the block on.
    :type timeout: float
    :param wait_period: The time to sleep between checking the conditions.
    :type wait_period: float
    :raises: TimeoutError if the conditions never match (assuming timeout is
        not None).
    """
    assert model is not None, ("model can't be None in "
                               "block_until_auto_reconnect_model()")
    aconditions = aconditions or []

    def _done():
        return all(c() for c in conditions)

    async def _adone():
        evaluated = []
        # note Python 3.5 doesn't support async comprehensions; do it the old
        # fashioned way.
        for c in aconditions:
            evaluated.append(await c())
            if is_model_disconnected(model):
                return False
        return all(evaluated)

    async def _block():
        while True:
            # reconnect if disconnected, as the conditions still need to be
            # checked.
            await ensure_model_connected(model)
            result = _done()
            aresult = await _adone()
            if all((not is_model_disconnected(model), result, aresult)):
                return
            else:
                await asyncio.sleep(wait_period)

    # finally wait for all the conditions to be true
    await asyncio.wait_for(_block(), timeout)


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
    """Transfer files to all units of an application.

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
    """Transfer files from unit_name in model_name.

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


def _normalise_action_results(results):
    """Put action results in a consistent format.

    :param results: Results dictionary to process.
    :type results: Dict[str, str]
    :returns: {
        'Code': '',
        'Stderr': '',
        'Stdout': '',
        'stderr': '',
        'stdout': ''}
    :rtype: Dict[str, str]
    """
    if results:
        # In Juju 2.7 some keys are dropped from the results if their
        # value was empty. This breaks some functions downstream, so
        # ensure the keys are always present.
        for key in ['Stderr', 'Stdout', 'stderr', 'stdout']:
            results[key] = results.get(key, '')
        # Juju has started using a lowercase "stdout" key in new action
        # commands in recent versions. Ensure the old capatalised keys and
        # the new lowercase keys are present and point to the same value to
        # avoid breaking functions downstream.
        for key in ['stderr', 'stdout']:
            old_key = key.capitalize()
            if results.get(key) and not results.get(old_key):
                results[old_key] = results[key]
            elif results.get(old_key) and not results.get(key):
                results[key] = results[old_key]
        return results
    else:
        return {}


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
        return _normalise_action_results(results)

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
                results = action.data.get('results')
                return _normalise_action_results(results)

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


async def async_get_systemd_service_active_time(unit_name, service,
                                                model_name=None, timeout=None):
    r"""Return the time that the given service was last active.

    Note: The service does not have to be currently running, the time returned
          relates to the last time the systemd service entered an 'active'
          state.

    :param unit_name: Name of unit to run action on
    :type unit_name: str
    :param service: Name of service to check active time
    :type service: str
    :param model_name: Name of model to query.
    :type model_name: str
    :param timeout: Time to wait for status to be achieved
    :type timeout: int
    """
    cmd = "systemctl show {} --property=ActiveEnterTimestamp".format(service)
    out = await async_run_on_unit(
        unit_name=unit_name,
        command=cmd,
        model_name=model_name,
        timeout=timeout)
    str_time = out['Stdout'].rstrip().replace('ActiveEnterTimestamp=', '')
    start_time = datetime.datetime.strptime(
        str_time,
        '%a %Y-%m-%d %H:%M:%S %Z')
    return start_time

get_systemd_service_active_time = sync_wrapper(
    async_get_systemd_service_active_time)


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


# FIXME: this is unsafe as it closes the model and returns the libjuju object
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


# FIXME: this is unsafe as it closes the model and returns the libjuju object
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


# FIXME: this is unsafe as it closes the model and returns the libjuju object
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


# FIXME: this is unsafe as it closes the model and returns the libjuju object
async def async_get_lead_unit(application_name, model_name=None):
    """Return the leader unit for a given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: Name of unit with leader status
    :raises: zaza.utilities.exceptions.JujuError
    """
    async with run_in_model(model_name) as model:
        for unit in model.applications[application_name].units:
            is_leader = await unit.is_leader_from_status()
            if is_leader:
                return unit
    raise zaza_exceptions.JujuError("No leader found for application {}"
                                    .format(application_name))


get_lead_unit = sync_wrapper(async_get_lead_unit)


async def async_get_lead_unit_name(application_name, model_name=None):
    """Return name of unit with leader status for given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: Name of unit with leader status
    :rtype: str
    :raises: zaza.utilities.exceptions.JujuError
    """
    return (await async_get_lead_unit(application_name, model_name)).entity_id


get_lead_unit_name = sync_wrapper(async_get_lead_unit_name)


# FIXME: this is unsafe as it takes a libjuju model
async def async_get_unit_public_address(unit, model_name=None):
    """Get the public address of a unit.

    Based on a feature flag "ZAZA_FEATURE_BUG472" existing, the function will
    call `get_unit_public_address__libjuju()`.  Otherwise, it will fall back to
    using `get_unit_public_address__fallback()` so that the public address can
    be extracted.

    Bug: https://github.com/openstack-charmers/zaza/issues/472

    :param unit: The libjuju unit object to get the public address for.
    :type unit: juju.Unit
    :returns: the IP address of the unit, or None
    :rtype: Optional(str)
    """
    if os.environ.get('ZAZA_FEATURE_BUG472', None):
        return await async_get_unit_public_address__libjuju(
            unit, model_name=model_name)
    else:
        return await async_get_unit_public_address__fallback(
            unit, model_name=model_name)


get_unit_public_address = sync_wrapper(async_get_unit_public_address)


# FIXME: this is unsafe as it takes a libjuju model
async def async_get_unit_public_address__libjuju(unit, model_name=None):
    """Get the public address of a unit.

    The libjuju library, in theory, supports a unit.public_address attribute
    that provides the publick address of the unit.  However, when the unit is
    an OpenStack VM, there is a race and it's possible it will be None.
    Therefore, there is a 'get_public_address()' funtion on unit that does
    provide the function.  See [1].

    Note, if the underlying provider hasn't provided an address (yet) then this
    will return None.

    1. https://github.com/juju/python-libjuju/issues/551

    :param unit: The libjuju unit object to get the public address for.
    :type unit: juju.Unit
    :returns: the IP address of the unit.
    :rtype: Optional(str)
    """
    return await unit.get_public_address()


# FIXME: This should probably pass the unit.name
async def async_get_unit_public_address__fallback(unit, model_name=None):
    """Get the public address of a unit via juju status shell command.

    Due to bug [1], this function calls juju status and extracts the public
    address as provided by the juju go client, as libjuju is unreliable.
    This is a stop-gap solution to work around the bug.  If the IP address
    can't be found, then None is returned.

    [1]: https://github.com/juju/python-libjuju/issues/615

    :param unit: The libjuju unit object to get the public address for.
    :type unit: juju.Unit
    :returns: the IP address of the unit.
    :rtype: Optional[str]
    """
    if model_name is None:
        model_name = await async_get_juju_model()
    cmd = "juju status --format=yaml -m {}".format(model_name)
    result = await generic_utils.check_output(
        cmd.split(), log_stderr=False, log_stdout=False)
    status = yaml.safe_load(result['Stdout'])
    try:
        app = unit.name.split('/')[0]
        return (
            status['applications'][app]['units'][unit.name]['public-address'])
    except KeyError:
        logging.warn("Public address not found for %s", unit.name)
        return None


async def async_get_app_ips(application_name, model_name=None):
    """Return public address of all units of an application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: List of ip addresses
    :rtype: [str, str,...]
    """
    addresses = []
    for u in await async_get_units(application_name, model_name=model_name):
        addresses.append(
            await async_get_unit_public_address(u, model_name=model_name))
    return addresses


get_app_ips = sync_wrapper(async_get_app_ips)


async def async_get_lead_unit_ip(application_name, model_name=None):
    """Return the IP address of the lead unit of a given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: IP of the lead unit
    :rtype: str
    :raises: zaza.utilities.exceptions.JujuError
    """
    return await async_get_unit_public_address(await async_get_lead_unit(
        application_name, model_name))


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

    NOTE: At the time of this writing python-libjuju requires all values passed
    to `set_config` to be `str`.
    https://github.com/juju/python-libjuju/issues/388

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param configuration: Dictionary of configuration setting(s)
    :type configuration: Dict[str,str]
    """
    async with run_in_model(model_name) as model:
        return await (model.applications[application_name]
                      .set_config(configuration))

set_application_config = sync_wrapper(async_set_application_config)


# A map of model names <-> last time get_status was called, and the result of
# that call.
_GET_STATUS_TIMES = {}
StatusResult = collections.namedtuple("StatusResult", ["time", "result"])


async def async_get_status(model_name=None, interval=4.0, refresh=True):
    """Return the full status, but share calls between different asyncs.

    Return the full status for the model_name (current model is None), but no
    faster than interval time, which is a default of 4 seconds.  If refresh is
    True, then this function waits until the interval is exceeded, and then
    returns the refreshed status.  This is the default.  If refresh is False,
    then the function immediately returns with the cached information.

    This is to enable multiple co-routines to access the status information
    without making multiple calls to Juju which all essentially will return
    identical information.

    Note that this is NOT thread-safe, but is async safe.  i.e. multiple
    different co-operating async futures can call this (in the same thread) and
    all access the same status.

    :param model_name: Name of model to query.
    :type model_name: str
    :param interval: The minimum time between calls to get_status
    :type interval: float
    :param refresh: Force a refresh; do not used cached results
    :type refresh: bool
    :returns: dictionary of juju status
    :rtype: dict
    """
    key = str(model_name)

    async def _update_status_result(key):
        async with run_in_model(model_name) as model:
            status = StatusResult(time.time(), await model.get_status())
            _GET_STATUS_TIMES[key] = status
            return status.result

    try:
        last = _GET_STATUS_TIMES[key]
    except KeyError:
        return await _update_status_result(key)
    now = time.time()
    if last.time + interval <= now:
        # we need to refresh the status time, so let's do that.
        return await _update_status_result(key)
    # otherwise, if we need a refreshed version, then we have to wait;
    if refresh:
        # wait until the min interval is exceeded, and then grab a copy.
        await asyncio.sleep((last.time + interval) - now)
        # now get the status.
        # By passing refresh=False, this WILL return a cached status if another
        # co-routine has already refreshed it.
        return await async_get_status(model_name, interval, refresh=False)
    # Not refreshing, so return the cached version
    return last.result


get_status = sync_wrapper(async_get_status)


class ActionFailed(Exception):
    """Exception raised when action fails."""

    def __init__(self, action, output=None):
        """Set information about action failure in message and raise."""
        # Bug: #314  -- unfortunately, libjuju goes bang even if getattr(x,y,
        # default) is used, which means we physically have to check for
        # KeyError.
        params = {'output': output}
        for key in ['name', 'parameters', 'receiver', 'message', 'id',
                    'status', 'enqueued', 'started', 'completed']:
            try:
                params[key] = getattr(action, key, "<not-set>")
            except KeyError:
                # code around libjuju in its getattr code.
                params[key] = "<not-set>"
        message = ('Run of action "{name}" with parameters "{parameters}" on '
                   '"{receiver}" failed with "{message}" (id={id} '
                   'status={status} enqueued={enqueued} started={started} '
                   'completed={completed} output={output})'
                   .format(**params))
        super(ActionFailed, self).__init__(message)


# FIXME: this is unsafe as it closes the model and returns the libjuju object
# Essentially, it returns the libjuju object after the model is closed.
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
            try:
                output = await model.get_action_output(action_obj.id)
            except KeyError:
                output = None
            raise ActionFailed(action_obj, output=output)
        return action_obj

run_action = sync_wrapper(async_run_action)


# FIXME: this is unsafe as it closes the model and returns the libjuju object
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
                    try:
                        output = await model.get_action_output(action_obj.id)
                    except KeyError:
                        output = None
                    raise ActionFailed(action_obj, output=output)
                return action_obj

run_action_on_leader = sync_wrapper(async_run_action_on_leader)


async def async_run_action_on_units(units, action_name, action_params=None,
# FIXME: this is unsafe as it closes the model and returns the libjuju object
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
                try:
                    output = await model.get_action_output(action_obj.id)
                except KeyError:
                    output = None
                raise ActionFailed(action_obj, output=output)

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
        self.units = units
        super(UnitError, self).__init__(message)


class MachineError(Exception):
    """Exception raised for units in error state."""

    def __init__(self, units):
        """Log machines in error state in message and raise."""
        message = "Machines {} in error state".format(
            ','.join([u.entity_id for u in units]))
        super(MachineError, self).__init__(message)


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


# FIXME: uses blocking subprocess call in async function.
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
                await block_until_auto_reconnect_model(
                    lambda: not unit.workload_status == 'error',
                    model=model,
                    timeout=timeout)

resolve_units = sync_wrapper(async_resolve_units)


def machines_in_state(model, states):
    """Check model for machines whose state is in the list 'states'.

    :param model: Model object to check
    :type model: juju.Model
    :param states: List of states to check for
    :type states: List
    :returns: List of machines
    :rtype: List[juju.machine.Machine]
    """
    machines = []
    for application_name in model.applications.keys():
        for unit in model.applications[application_name].units:
            if unit.machine and unit.machine.status in states:
                machines.append(unit.machine)
    return machines


def check_model_for_hard_errors(model):
    """Check model for any hard errors that should halt a deployment.

       The check for units or machines in an
       error state

    :raises: Union[UnitError, MachineError]
    """
    MACHINE_ERRORS = ['provisioning error']
    errored_units = units_with_wl_status_state(model, 'error')
    if errored_units:
        raise UnitError(errored_units)
    errored_machines = machines_in_state(model, MACHINE_ERRORS)
    if errored_machines:
        raise MachineError(errored_machines)


def check_unit_workload_status(model, unit, states):
    """Check that the units workload status matches the supplied state.

    This function has the side effect of also checking for *any* units
    in an error state and aborting if any are found.

    :param model: Model object to check in
    :type model: juju.Model
    :param unit: Unit to check wl status of
    :type unit: juju.Unit
    :param states: Acceptable unit work load states
    :type states: List[str]
    :raises: UnitError
    :returns: Whether units workload status matches desired state
    :rtype: bool
    """
    check_model_for_hard_errors(model)
    return unit.workload_status in states


def check_unit_workload_status_message(model,
                                       unit,
                                       message=None,
                                       prefixes=None,
                                       regex=None):
    """Check that the units workload status message.

    Check that the units workload status message matches the supplied message,
    matches a regular expression (regex) or starts with one of the supplied
    prefixes. Raises an exception if neither prefixes or message is set. This
    function has the side effect of also checking for *any* units in an error
    state and aborting if any are found.

    Note that the priority of checking is: message, then regex, then prefixes.

    :param model: Model object to check in
    :type model: juju.Model
    :param unit: Unit to check wl status of
    :type unit: juju.Unit
    :param message: Expected message text
    :type message: Optiona[str]
    :param prefixes: Prefixes to match message against
    :type prefixes: Optional[List[str]]
    :param regex: A regular expression against which to test the message
    :type regex: Optional[str]
    :raises: ValueError, UnitError
    :returns: Whether message matches desired string
    :rtype: bool
    """
    check_model_for_hard_errors(model)
    if message is not None:
        return unit.workload_status_message == message
    elif regex is not None:
        # Note: search is used so that pattern doesn't have to use a ".*" at
        # the beginning of the string to match. To match the start use a "^".
        return re.search(regex, unit.workload_status_message) is not None
    elif prefixes is not None:
        return unit.workload_status_message.startswith(tuple(prefixes))
    else:
        raise ValueError("Must be called with message, prefixes or regex")


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
        await block_until_auto_reconnect_model(
            lambda: one_agent_status(model, status),
            model=model,
            timeout=timeout)

wait_for_agent_status = sync_wrapper(async_wait_for_agent_status)


def is_unit_idle(unit):
    """Return True if the unit is in the idle state.

    Note: the unit only makes progress (in terms of updating it's idle status)
    if this function is called as part of an asyncio loop as the status is
    updated in a co-routine/future.

    :param unit: the unit to test
    :type unit: :class:'juju.unit.Unit'
    :returns: True if the unit is in the idle state
    :rtype: bool
    """
    try:
        return unit.data['agent-status']['current'] == 'idle'
    except (AttributeError, KeyError):
        pass
    return False


def is_unit_errored_from_install_hook(unit):
    """Return True if the unit is in error state from the install hook.

    :param unit: the unit to test
    :type unit: :class:'juju.unit.Unit'
    :returns: True if the unit is in the failed state and the workload status
              message indicates the install hook failed.
    :rtype: bool
    """
    return unit.workload_status == 'error' and \
        unit.workload_status_message == 'hook failed: "install"'


async def async_wait_for_application_states(model_name=None, states=None,
                                            timeout=2700, max_resolve_count=0):
    """Wait for model to achieve the desired state.

    Check the workload status and workload status message for every unit of
    every application. By default look for an 'active' workload status and a
    message that starts with one of the approved_message_prefixes.

    Bespoke statuses and messages can be passed in with states. states takes
    the form::

        states = {
            'app': {
                'workload-status': 'blocked',
                'workload-status-message-prefix': 'No requests without a prod',
                'num-expected-units': 3,
            },
            'anotherapp': {
                'workload-status-message-prefix': 'Unit is super ready'}}
        wait_for_application_states('modelname', states=states)

    The keys that can be used are:

     - "workload-status" - an exact match of the workload-status
     - "workload-status-message-prefix" - an exact match, that starts with the
       string passed.
     - "workload-status-message-regex" - the entire string matches if the regex
       matches.
     - "workloaed-status-message" - DEPRECATED; use
           "workload-status-message-prefix" instead.
    - "num-expected-units' - the number of units to be 'ready'.

    To match an empty string, use:
      "workload-status-message-regex": "^$"

    NOTE: all applications that are being waited on are expected to have at
    least one unit for that application to be ready.  Any subordinate charms
    which have not be related to their principle by the time this function is
    called will 'hang' the function; in this case (if this is expected), then
    the application should be passed in the :param:states parameter with a
    'num-expected-units' of 0 for the app in question.

    :param model_name: Name of model to query.
    :type model_name: str
    :param states: States to look for
    :type states: dict
    :param timeout: Time to wait for status to be achieved
    :type timeout: int
    :param max_resolve_count: Maximum number of times a unit can be resolved
        when it is in the error state. This only applies to install hook
        failures and is considered a temporary hack to work around underlying
        provider networking issues.
    :type max_resolve_count: int

    """
    logging.info("Waiting for application states to reach targeted states.")
    # Implementation note: model.block_until() can throw
    # websockets.exceptions.ConnectionClosed if it detects that the connection
    # is closed.  What we want to do then, is re-open the connection, and try
    # again, hence this function uses block_until_auto_reconnect_model
    approved_message_prefixes = ['ready', 'Ready', 'Unit is ready']
    approved_statuses = ['active']

    if not states:
        states = {}
    async with run_in_model(model_name) as model:
        check_model_for_hard_errors(model)
        logging.info("Waiting for an application to be present")
        await block_until_auto_reconnect_model(
            lambda: len(model.units) > 0,
            model=model)

        timeout_msg = (
            "Timed out waiting for '{unit_name}'. The {gate_attr} "
            "is '{unit_state}' which is not one of '{approved_states}'")
        # Loop checking status every few seconds, waiting on applications to
        # reach the approved states.  `applications_left` are the applications
        # still to check.  If the timeout is exceeded we fail.  Note that there
        # are other async futures in libjuju that make progress when this
        # future sleeps.  We also need to check if the model has disconnected,
        # and if so, clean up and reconnect.
        start = time.time()
        applications_left = set(model.applications.keys())

        # print deprecation notices for apps that use "workload-status-message"
        for application in applications_left:
            if (states
                    .get(application, {})
                    .get('workload-status-message', None) is not None):
                logging.warning(
                    "DEPRECATION: Application %s uses "
                    "'workload-status-message'; please use "
                    "'workload-status-message-prefix' instead.", application)

        logging.info("Now checking workload status and status messages")

        # Store the units and how many times they've been resolved for
        # installation failures. If a unit has been resolved 3 times,
        # then this will fail hard.
        resolve_counts = collections.defaultdict(int)
        while True:
            # now we sleep to allow progress to be made in the libjuju futures
            await asyncio.sleep(2)

            await ensure_model_connected(model)
            timed_out = int(time.time() - start) > timeout
            issues = []
            for application in applications_left.copy():
                check_info = states.get(application, {})
                app_data = model.applications.get(application, None)
                units = list(app_data.units)

                # if there are no units then the application may not be ready.
                # However, if the caller explicitly allows that situation then
                # we gate on that.
                num_expected = check_info.get('num-expected-units', None)
                if num_expected is not None:
                    if len(units) != num_expected:
                        continue
                else:
                    # num_expected is None, so 0 units means we are still
                    # waiting
                    if len(units) == 0:
                        continue

                # all_okay is a Boolean of the current state.  It starts as
                # True, but if False by the end of the checks, then the
                # application is not ready.
                all_okay = True
                check_wl_statuses = approved_statuses.copy()
                app_wls = check_info.get('workload-status', None)
                if app_wls is not None:
                    check_wl_statuses.append(app_wls)
                # preferentially try the newer -prefix first, before
                # falling back to the older key without a -prefix
                check_msg = check_info.get(
                    'workload-status-message-prefix',
                    check_info.get('workload-status-message', None))
                check_regex = check_info.get(
                    'workload-status-message-regex', None)
                prefixes = approved_message_prefixes.copy()
                if check_msg is not None:
                    prefixes.append(check_msg)

                # check all the units; any not in status, we continue
                for unit in units:
                    # if a unit isn't idle, then not ready yet.
                    ok = is_unit_idle(unit)
                    all_okay = all_okay and ok
                    if not ok and timed_out:
                        issues.append(
                            timeout_msg.format(
                                unit_name=unit.entity_id,
                                gate_attr="unit status",
                                unit_state="not idle",
                                approved_states=["idle"]))
                        continue

                    try:
                        ok = check_unit_workload_status(
                            model, unit, check_wl_statuses)
                        all_okay = all_okay and ok
                        if not ok and timed_out:
                            issues.append(
                                timeout_msg.format(
                                    unit_name=unit.entity_id,
                                    gate_attr='workload status',
                                    unit_state=unit.workload_status,
                                    approved_states=check_wl_statuses))
                        ok = check_unit_workload_status_message(
                            model, unit, prefixes=prefixes, regex=check_regex)
                        all_okay = all_okay and ok
                        if not ok and timed_out:
                            issues.append(
                                timeout_msg.format(
                                    unit_name=unit.entity_id,
                                    gate_attr='workload status message',
                                    unit_state=unit.workload_status_message,
                                    approved_states=prefixes))
                    except UnitError as e:
                        # Check to see if this error is "resolvable" and try
                        # again.
                        # Note: since the UnitError can be raised for any unit
                        # in any of the calls to the check_unit_* invocations
                        # (which in turn call check_model_for_hard_errors),
                        # we need to check all the units captured in the
                        # UnitError as the current unit may not be the one in
                        # error
                        for u in e.units:
                            if not is_unit_errored_from_install_hook(u):
                                raise

                            resolve_counts[u.name] += 1
                            if resolve_counts[u.name] > max_resolve_count:
                                raise

                            logging.warning("Unit %s is in error state. "
                                            "Attempt number %d to resolve" %
                                            (u.name, resolve_counts[u.name]))
                            await async_resolve_units(
                                application_name=unit.application,
                                erred_hook='install'
                            )
                            # wait until the unit is executing. 60 seconds
                            # seems like a reasonable timeout
                            await async_block_until_unit_wl_status(
                                u.name, 'error', model_name, negate_match=True,
                                timeout=60
                            )

                        all_okay = False

                # if not all states are okay, continue to the next one.
                if not(all_okay):
                    continue

                applications_left.remove(application)
                logging.info("Application %s is ready.", application)

            if not(applications_left):
                logging.info("All applications reached approved status, "
                             "number of units (where relevant), and workload"
                             " status message checks.")
                return

            # check if we've timed-out, if so record the problem charms to the
            # log and raise a ModelTimeout
            if timed_out:
                logging.info("TIMEOUT: Workloads didn't reach acceptable "
                             "status:")
                for issue in issues:
                    logging.info(issue)
                raise ModelTimeout("Work state not achieved within timeout.")


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
        await block_until_auto_reconnect_model(
            lambda: units_with_wl_status_state(
                model, 'error') or model.all_units_idle(),
            model=model,
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
    # NOTE(tinwood): Due to https://github.com/juju/python-libjuju/issues/458
    # set the max frame size to something big to stop
    # "RPC: Connection closed, reconnecting" messages and then failures.
    model = Model(max_frame_size=JUJU_MAX_FRAME_SIZE)
    await model.connect()
    model_name = model.info.name
    await model.disconnect()
    return model_name


get_current_model = sync_wrapper(async_get_current_model)


async def async_block_until(*conditions, timeout=None, wait_period=0.5):
    """Return only after all async conditions are true.

    Based on juju.utils.block_until which currently does not support
    async methods as conditions.

    :param conditions: Functions to evaluate.
    :type conditions: functions
    :param timeout: Timeout in seconds
    :type timeout: float
    :param wait_period: Time to wait between re-assessing conditions.
    :type wait_period: float
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
                await asyncio.sleep(wait_period)
    await asyncio.wait_for(_block(), timeout)


block_until = sync_wrapper(async_block_until)


def file_contents(unit_name, path, timeout=None):
    """Return the contents of a file.

    :param path: File path
    :param unit_name: Unit name, either appname/N or appname/leader
    :type unit_name: str
    :param timeout: Timeout in seconds
    :type timeout: float
    :returns: File contents
    :rtype: str
    """
    app, unit_id = unit_name.split("/")
    if unit_id == "leader":
        target = app
        run_func = run_on_leader
    else:
        target = unit_name
        run_func = run_on_unit
    cmd = "cat {}".format(path)
    result = run_func(target, cmd, timeout=timeout)
    err = result.get("Stderr")
    if err:
        raise RemoteFileError(err)
    return result.get("Stdout")


async def async_block_until_machine_status_is(
    machine, status, model_name=None, invert_check=False, timeout=600,
    interval=4.0, refresh=True
):
    """Block until the agent status for a machine (doesn't) match status.

    Block until the agent status of a machine does (or doesn't with the param
    `invert_status=True`) match the passed string (in param `status`).  If the
    timeout is exceeded then the function raises an Exception.

    :param machine: the machine to watch, as provided from the get_status()
    :type machine: str
    :param status: the string to match the machine's agent status to.
    :type status: str
    :param model_name: Name of model to query.
    :type model_name: str
    :param invert_check: whether to invert the check (default False)
    :type invert_check: bool
    :param timeout: the time to wait for the status (or inverse of) (default
        600 seconds).
    :type timeout: int
    :raises: asyncio.TimeoutError if the timeout is exceeded.
    :param interval: The minimum time between calls to get_status
    :type interval: float
    :param refresh: Force a refresh; do not used cached results
    :type refresh: bool
    """
    async def _check_machine_status():
        _status = await async_get_status(model_name=model_name,
                                         interval=interval,
                                         refresh=refresh)
        equals = _status["machines"][machine].agent_status["status"] == status
        return not(equals) if invert_check else equals

    async with run_in_model(model_name):
        await async_block_until(_check_machine_status, timeout=timeout)


block_until_machine_status_is = sync_wrapper(
    async_block_until_machine_status_is)


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


block_until_file_ready = sync_wrapper(async_block_until_file_ready)


async def async_block_until_file_has_contents(application_name, remote_file,
                                              expected_contents,
                                              model_name=None, timeout=2700):
    """Block until the expected_contents are present on all units.

    Block until the given string (expected_contents) is present in the file
    (remote_file) on all units of the given application.

    An example accessing this function via its sync wrapper::

        block_until_file_has_contents(
            'keystone',
            '/etc/apache2/apache2.conf',
            'KeepAlive On',
            model_name='modelname')


    :param application_name: Name of application
    :type application_name: str
    :param remote_file: Remote path of file to transfer
    :type remote_file: str
    :param expected_contents: String to look for in file
    :type expected_contents: str
    :param model_name: Name of model to query.
    :type model_name: str
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


async def async_block_until_file_matches_re(
    application_name,
    remote_file,
    pattern,
    re_flags=re.MULTILINE,
    model_name=None,
    timeout=2700,
):
    """Block until a file matches a pattern.

    Block until the provided regular expression pattern matches the given
    file on all units of the given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param remote_file: Remote path of file to match
    :type remote_file: str
    :param pattern: Regular expression
    :type pattern: str or compiled regex
    :param re_flags: Regular expression flags if the pattern is a string
    :type re_flags: re.RegexFlag (int flag constants from the re module)
    :param timeout: Time to wait for contents to appear in file
    :type timeout: float
    """
    if isinstance(pattern, str):
        pattern = re.compile(pattern, flags=re_flags)

    def f(x):
        return pattern.search(x) is not None

    return await async_block_until_file_ready(
        application_name,
        remote_file,
        f,
        timeout=timeout,
        model_name=model_name
    )


block_until_file_matches_re = sync_wrapper(async_block_until_file_matches_re)


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


async def async_block_until_file_missing_on_machine(
        machine, path, model_name=None, timeout=2700):
    """Block until the file at 'path' is not present for a machine.

    An example accessing this function via its sync wrapper::

        block_until_file_missing_on_machine(
            '0',
            '/some/path/name')


    :param machine: the machine
    :type machine: str
    :param path: the file name to check for.
    :type path: str
    :param model_name: Name of model to query.
    :type model_name: str
    :param timeout: Time to wait for until file is missing on a machine.
    :type timeout: float
    """
    async def _check_for_file(model):
        try:
            output = await async_run_on_machine(
                machine, 'test -e "{}"; echo $?'.format(path),
                model_name)
            contents = output.get('Stdout', "")
            return "1" in contents
        # libjuju throws a generic error for connection failure. So we
        # cannot differentiate between a connectivity issue and a
        # target file not existing error. For now just assume the
        # latter.
        except JujuError:
            pass
        return False

    async with run_in_model(model_name) as model:
        await async_block_until(lambda: _check_for_file(model),
                                timeout=timeout)


block_until_file_missing_on_machine = sync_wrapper(
    async_block_until_file_missing_on_machine)


async def async_block_until_units_on_machine_are_idle(
        machine, model_name=None, timeout=2700):
    """Block until all the units on a machine are idle.

    :param machine: the machine
    :type machine: str
    :param model_name: Name of model to query.
    :type model_name: str
    :param timeout: Time to wait for units on machine to be idle.
    :type timeout: float
    """
    async def _ready():
        _status = await async_get_status()
        apps = set()
        units = []
        statuses = []
        # collect the apps on the machine (and thus the unit's status)
        for app, app_data in _status["applications"].items():
            # we get the subordinates afterwards
            if app_data["subordinate-to"]:
                continue
            for unit, unit_data in app_data["units"].items():
                if unit_data["machine"] == machine:
                    apps.add(app)
                    units.append(unit)
                    statuses.append(
                        unit_data['agent-status']['status'] == 'idle')
        # now collect the subordinates for each of the apps
        for app in apps:
            for u_name, u_bag in _status.applications[app]['units'].items():
                if u_name in units:
                    subordinates = u_bag.get('subordinates', {})
                    statuses.extend([
                        unit['agent-status']['status'] == 'idle'
                        for unit in subordinates.values()])
        # return ready if all the statuses were idle
        return all(statuses)

    async with run_in_model(model_name):
        await async_block_until(_ready, timeout=timeout)


block_until_units_on_machine_are_idle = sync_wrapper(
    async_block_until_units_on_machine_are_idle)


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
            'glance',
            '/etc/glance/glance-api.conf',
            expected_contents,
            model_name='modelname')

    :param application_name: Name of application
    :type application_name: str
    :param remote_file: Remote path of file to transfer
    :type remote_file: str
    :param expected_contents: The key value pairs in their corresponding
                              sections to be looked for in the remote_file
    :type expected_contents: {}
    :param model_name: Name of model to query.
    :type model_name: str
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
            'glance',
            1528294585,
            ['glance-api'],
            model_name='modelname')

    :param application_name: Name of application
    :type application_name: str
    :param mtime: Time in seconds since Epoch to check against
    :type mtime: int
    :param services: Listr of services to check restart time of
    :type services: []
    :param model_name: Name of model to query.
    :type model_name: str
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


async def async_block_until_unit_wl_message_match(
        unit, status_pattern, model_name=None, negate_match=False,
        timeout=2700):
    """Block until the unit has a workload status message that matches pattern.

    :param unit: the unit to check against
    :type unit: str
    :param status_pattern: Regex pattern to check status against.
    :type status_pattern: str
    :param model_name: Name of model to query.
    :type model_name: Union[None, str]
    :param negate_match: Wait until the match is not true; i.e. none match
    :type negate_match: Union[None, bool]
    :param timeout: Time to wait for unit to achieved desired status
    :type timeout: float
    """
    principle_unit = await async_get_principle_unit(
        unit,
        model_name=model_name)

    async def _unit_status():
        model_status = await async_get_status()
        app = unit.split('/')[0]
        if principle_unit:
            principle_app = principle_unit.split('/')[0]
            _unit = model_status.applications[principle_app]['units'][
                principle_unit]['subordinates'][unit]
        else:
            _unit = model_status.applications[app]['units'][unit]
        status = _unit['workload-status']['info']
        if negate_match:
            return not bool(re.match(status_pattern, status))
        else:
            return bool(re.match(status_pattern, status))

    async with run_in_model(model_name):
        await async_block_until(
            _unit_status,
            timeout=timeout)


block_until_unit_wl_message_match = sync_wrapper(
    async_block_until_unit_wl_message_match)


async def async_get_principle_sub_map(model_name=None):
    """
    Get a map of principle units to a list subordinates.

    :param model_name: Name of model to operate on
    :type model_name: str
    :returns: Name of unit
    :rtype: Dict[str, [str]]
    """
    async with run_in_model(model_name):
        model_status = await async_get_status()
        return {
            unit: list(detail['units'][unit].get('subordinates', {}).keys())
            for name, detail in model_status.applications.items()
            for unit in detail.get('units', [])}

get_principle_sub_map = sync_wrapper(
    async_get_principle_sub_map)


async def async_get_principle_unit(unit_name, model_name=None):
    """
    Get principle unit name for subordinate.

    :param unit_name: Name of unit
    :type unit_name: str
    :param model_name: Name of model to operate on
    :type model_name: str
    :returns: Name of unit
    :rtype: Union[str, None]
    """
    sub_map = await async_get_principle_sub_map()
    for principle, subordinates in sub_map.items():
        if unit_name in subordinates:
            return principle

get_principle_unit = sync_wrapper(
    async_get_principle_unit)


async def async_get_relation_id(application_name, remote_application_name,
                                model_name=None,
                                remote_interface_name=None):
    """
    Get relation id of relation from model.

    :param application_name: Name of application on this side of relation
    :type application_name: str
    :param remote_application_name: Name of application on other side of
                                    relation
    :type remote_application_name: str
    :param remote_interface_name: Name of interface on remote end of relation
    :param model_name: Name of model to operate on
    :type model_name: str
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

    :param constraints: Constraints to be applied to model
    :type constraints: dict
    :param model_name: Name of model to operate on
    :type model_name: str

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
    cmd.append('--')
    cmd.append(command)
    logging.info("About to call '{}'".format(cmd))
    return await generic_utils.check_output(cmd)


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
    """Check if the specified unit's subordinates are idle.

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


CloudData = collections.namedtuple(
    'CloudData', [
        'cloud_name',
        'cloud',
        'credential_name',
        'credential'])


async def async_get_cloud_data(credential_name=None, model_name=None):
    """Get connection details and credentials for cloud supporting given model.

    :param credential_name: Name of credential to retrieve.
    :type credential_name: Optional[str]
    :param model_name: Model name to operate on.
    :type model_name: Optional[str]
    :returns: Credential Name, Juju Cloud Credential object
    :rtype: CloudData[str, Cloud, str, CloudCredential]
    :raises: AssertionError
    """
    async with run_in_model(model_name) as model:
        # Get new connection to Controller for model
        controller = await model.get_controller()
        # Get cloud name for controller
        cloud_name = await controller.get_cloud()
        clouds = await controller.clouds()
        cloud_data = clouds['clouds'].get('cloud-{}'.format(cloud_name))
        await controller.disconnect()
        # Retrieve credentials for controller from local disk
        juju_data = juju.client.jujudata.FileJujuData()
        credential = juju_data.load_credential(
            cloud_name, name=credential_name)
        return CloudData(
            cloud_name,
            cloud_data,
            credential[0],
            credential[1])

get_cloud_data = sync_wrapper(async_get_cloud_data)


def add_storage(unit, label, pool, size, model=None):
    """Add storage to a Juju unit.

    :param unit: The unit name (i.e: ceph-osd/0)
    :type unit: str

    :param label: The storage label (i.e: osd-devices)
    :type label: str

    :param pool: The pool on which to allocate the storage (i.e: cinder)
    :type pool: str

    :param size: The size in GB of the storage to attach.
    :type size: int

    :param model: The model name, or None, for the current model.
    :type model: Option[str]

    :returns: The name of the allocated storage.
    :rtype: str
    """
    model = model or get_juju_model()
    rv = subprocess.check_output(['juju', 'add-storage', unit, '-m', model,
                                  '{}={},{}'.format(label, pool,
                                                    str(size) + 'GB')],
                                 stderr=subprocess.STDOUT)
    return rv.decode('UTF-8').replace('added storage ', '').split(' ')[0]


def detach_storage(storage_name, model=None, force=False):
    """Detach previously allocated Juju storage.

    :param storage_name: The name of the allocated storage, as returned by
        a call to 'add_storage'.
    :type storage_name: str

    :param model: The model name, or None, for the current model.
    :type model: Option[str]

    :param force: Whether to forcefully detach the storage.
    :type force: bool
    """
    model = model or get_juju_model()
    cmd = ['juju', 'detach-storage', '-m', model, storage_name]
    if force:
        cmd.append('--force')
    subprocess.check_call(cmd)


def remove_storage(storage_name, model=None, force=False, destroy=True):
    """Remove Juju storage.

    :param storage_name: The name of the previously allocated Juju storage.
    :type storage_name: str

    :param model: The model name, or None, for the current model.
    :type model: Option[str]

    :param force: If False (default), require that the storage be detached
                  before it can be removed.
    :type force: bool

    :param destroy: Whether to destroy the storage.
    :type destroy: bool
    """
    model = model or get_juju_model()
    cmd = ['juju', 'remove-storage', storage_name, '-m', model]
    if force:
        cmd.append('--force')
    if not destroy:
        cmd.append('--no-destroy')
    subprocess.check_call(cmd)
