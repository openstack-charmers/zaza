import functools

from juju import loop
from juju.model import Model


async def deployed(filter=None):
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


def get_unit_from_name(unit_name, model):
    """Return the units that corresponds to the name in the given model

    :param unit_name: Name of unit to match
    :type unit_name: str
    :param model: Model to perform lookup in
    :type model: juju.model.Model
    :returns: Unit matching given name
    :rtype: juju.unit.Unit or None
    """
    app = unit_name.split('/')[0]
    unit = None
    for u in model.applications[app].units:
        if u.entity_id == unit_name:
            unit = u
            break
    else:
        raise Exception
    return unit


async def run_in_model(model_name, f, add_model_arg=False, awaitable=True):
    """Run the given function in the model matching the model_name

    :param model_name: Name of model to run function in
    :type model_name: str
    :param f: Function to run with given moel in focus
    :type f: functools.partial
    :param add_model_arg: Whether to add kwarg pointing at model to the given
                          function before running it
    :type add_model_arg: boolean
    :param awaitable: Whether f is awaitable
    :type awaitable: boolean
    :returns: Output of f
    :rtype: Unknown, depends on the passed in function
    """
    model = Model()
    await model.connect_model(model_name)
    output = None
    try:
        if add_model_arg:
            f.keywords.update(model=model)
        if awaitable:
            output = await f()
        else:
            output = f()
    finally:
        # Disconnect from the api server and cleanup.
        await model.disconnect()
        return output


def scp_to_unit(unit_name, model_name, source, destination, user='ubuntu',
                proxy=False, scp_opts=''):
    """Transfer files to unit_name in model_name.

    :param unit_name: Name of unit to scp to
    :type unit_name: str
    :param model_name: Name of model unit is in
    :type model_name: str
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
    async def _scp_to_unit(unit_name, source, destination, user, proxy,
                           scp_opts, model):
        unit = get_unit_from_name(unit_name, model)
        await unit.scp_to(source, destination, user=user, proxy=proxy,
                          scp_opts=scp_opts)
    scp_func = functools.partial(
        _scp_to_unit,
        unit_name,
        source,
        destination,
        user=user,
        proxy=proxy,
        scp_opts=scp_opts)
    loop.run(
        run_in_model(model_name, scp_func, add_model_arg=True, awaitable=True))


def scp_to_all_units(application_name, model_name, source, destination,
                     user='ubuntu', proxy=False, scp_opts=''):
    """Transfer files from to all units of an application

    :param application_name: Name of application to scp file to
    :type unit_name: str
    :param model_name: Name of model unit is in
    :type model_name: str
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
    async def _scp_to_all_units(application_name, source, destination, user,
                                proxy, scp_opts, model):
        for unit in model.applications[application_name].units:
            await unit.scp_to(source, destination, user=user, proxy=proxy,
                              scp_opts=scp_opts)
    scp_func = functools.partial(
        _scp_to_all_units,
        application_name,
        source,
        destination,
        user=user,
        proxy=proxy,
        scp_opts=scp_opts)
    loop.run(
        run_in_model(model_name, scp_func, add_model_arg=True, awaitable=True))


def scp_from_unit(unit_name, model_name, source, destination, user='ubuntu',
                  proxy=False, scp_opts=''):
    """Transfer files from to unit_name in model_name.

    :param unit_name: Name of unit to scp from
    :type unit_name: str
    :param model_name: Name of model unit is in
    :type model_name: str
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
    async def _scp_from_unit(unit_name, source, destination, user, proxy,
                             scp_opts, model):
        unit = get_unit_from_name(unit_name, model)
        await unit.scp_from(source, destination, user=user, proxy=proxy,
                            scp_opts=scp_opts)
    scp_func = functools.partial(
        _scp_from_unit,
        unit_name,
        source,
        destination,
        user=user,
        proxy=proxy,
        scp_opts=scp_opts)
    loop.run(
        run_in_model(model_name, scp_func, add_model_arg=True, awaitable=True))


def run_on_unit(unit_name, model_name, command, timeout=None):
    """Juju run on unit

    :param unit_name: Name of unit to match
    :type unit: str
    :param model_name: Name of model unit is in
    :type model_name: str
    :param command: Command to execute
    :type command: str
    :param timeout: DISABLED due to Issue #225
                    https://github.com/juju/python-libjuju/issues/225
    :type timeout: int
    :returns: action.data['results'] {'Code': '', 'Stderr': '', 'Stdout': ''}
    :rtype: dict
    """

    # Disabling timeout due to Issue #225
    # https://github.com/juju/python-libjuju/issues/225
    if timeout:
        timeout = None

    async def _run_on_unit(unit_name, command, model, timeout=None):
        unit = get_unit_from_name(unit_name, model)
        action = await unit.run(command, timeout=timeout)
        if action.data.get('results'):
            return action.data.get('results')
        else:
            return {}
    run_func = functools.partial(
        _run_on_unit,
        unit_name,
        command,
        timeout=timeout)
    return loop.run(
        run_in_model(model_name, run_func, add_model_arg=True, awaitable=True))


def get_application(model_name, application_name):
    """Return an application object

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application to retrieve units for
    :type application_name: str

    :returns: Appliction object
    :rtype: object
    """
    async def _get_application(application_name, model):
        return model.applications[application_name]
    f = functools.partial(_get_application, application_name)
    return loop.run(run_in_model(model_name, f, add_model_arg=True))


def get_units(model_name, application_name):
    """Return all the units of a given application

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application to retrieve units for
    :type application_name: str

    :returns: List of juju units
    :rtype: [juju.unit.Unit, juju.unit.Unit,...]
    """
    async def _get_units(application_name, model):
        return model.applications[application_name].units
    f = functools.partial(_get_units, application_name)
    return loop.run(run_in_model(model_name, f, add_model_arg=True))


def get_machines(model_name, application_name):
    """Return all the machines of a given application

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application to retrieve units for
    :type application_name: str

    :returns: List of juju machines
    :rtype: [juju.machine.Machine, juju.machine.Machine,...]
    """
    async def _get_machines(application_name, model):
        machines = []
        for unit in model.applications[application_name].units:
            machines.append(unit.machine)
        return machines
    f = functools.partial(_get_machines, application_name)
    return loop.run(run_in_model(model_name, f, add_model_arg=True))


def get_first_unit_name(model_name, application_name):
    """Return name of lowest numbered unit of given application

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str

    :returns: Name of lowest numbered unit
    :rtype: str
    """
    return get_units(model_name, application_name)[0].name


def get_app_ips(model_name, application_name):
    """Return public address of all units of an application

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str

    :returns: List of ip addresses
    :rtype: [str, str,...]
    """
    return [u.public_address for u in get_units(model_name, application_name)]


def get_application_config(model_name, application_name):
    """Return application configuration

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str

    :returns: Dictionary of configuration
    :rtype: dict
    """
    async def _get_config(application_name, model):
        return await model.applications[application_name].get_config()
    f = functools.partial(_get_config, application_name)
    return loop.run(run_in_model(model_name, f, add_model_arg=True))


def set_application_config(model_name, application_name, configuration):
    """Set application configuration

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param key: Dictionary of configuration setting(s)
    :type key: dict
    :returns: None
    :rtype: None
    """
    async def _set_config(application_name, model, configuration={}):
        return await (model.applications[application_name]
                      .set_config(configuration))
    f = functools.partial(_set_config, application_name,
                          configuration=configuration)
    return loop.run(run_in_model(model_name, f, add_model_arg=True))


def get_status(model_name):
    """Return full status

    :param model_name: Name of model to query.
    :type model_name: str

    :returns: dictionary of juju status
    :rtype: dict
    """
    async def _get_status(model):
        return await model.get_status()
    f = functools.partial(_get_status)
    return loop.run(run_in_model(model_name, f, add_model_arg=True))


def main():
    # Run the deploy coroutine in an asyncio event loop, using a helper
    # that abstracts loop creation and teardown.
    print("Current applications: {}".format(", ".join(loop.run(deployed()))))


if __name__ == '__main__':
    main()
