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
    """Transfer files from to unit_name in model_name.

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


def main():
    # Run the deploy coroutine in an asyncio event loop, using a helper
    # that abstracts loop creation and teardown.
    print("Current applications: {}".format(", ".join(loop.run(deployed()))))


if __name__ == '__main__':
    main()
