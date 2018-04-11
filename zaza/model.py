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


class RunInModel:
    """Conext manager for executing code inside a libjuju model

       Example of using RunInModel:

           async with RunInModel(model_name) as model:
               output = await some_function(model=model)
    """
    def __init__(self, model_name):
        """Create instance of RunInModel

        :param model_name: Name of model to connect to
        :type model_name: str"""
        self.model_name = model_name

    async def __aenter__(self):
        self.model = Model()
        await self.model.connect_model(self.model_name)
        return self.model

    async def __aexit__(self, exc_type, exc, tb):
        await self.model.disconnect()


def scp_to_unit(model_name, unit_name, source, destination, user='ubuntu',
                proxy=False, scp_opts=''):
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
    async def _scp_to_unit(model_name, unit_name, source, destination, user,
                           proxy, scp_opts):
        async with RunInModel(model_name) as model:
            unit = get_unit_from_name(unit_name, model)
            print(unit)
            await unit.scp_to(source, destination, user=user, proxy=proxy,
                              scp_opts=scp_opts)
    loop.run(_scp_to_unit(model_name, unit_name, source, destination,
                          user=user, proxy=proxy, scp_opts=scp_opts))


def scp_to_all_units(model_name, application_name, source, destination,
                     user='ubuntu', proxy=False, scp_opts=''):
    """Transfer files from to all units of an application

    :param model_name: Name of model unit is in
    :type model_name: str
    :param application_name: Name of application to scp file to
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
    async def _scp_to_all_units(model_name, application_name, source,
                                destination, user, proxy, scp_opts):
        async with RunInModel(model_name) as model:
            for unit in model.applications[application_name].units:
                await unit.scp_to(source, destination, user=user, proxy=proxy,
                                  scp_opts=scp_opts)
    loop.run(_scp_to_all_units(model_name, application_name, source,
                               destination, user=user, proxy=proxy,
                               scp_opts=scp_opts))


def scp_from_unit(model_name, unit_name, source, destination, user='ubuntu',
                  proxy=False, scp_opts=''):
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
    async def _scp_from_unit(model_name, unit_name, source, destination, user,
                             proxy, scp_opts):
        async with RunInModel(model_name) as model:
            unit = get_unit_from_name(unit_name, model)
            await unit.scp_from(source, destination, user=user, proxy=proxy,
                                scp_opts=scp_opts)
    loop.run(_scp_from_unit(model_name, unit_name, source, destination,
             user=user, proxy=proxy, scp_opts=scp_opts))


def run_on_unit(model_name, unit, command):
    """Juju run on unit

    :param model_name: Name of model unit is in
    :type model_name: str
    :param unit: Unit object
    :type unit: object
    :param command: Command to execute
    :type command: str
    """
    async def _run_on_unit(model_name, unit, command):
        async with RunInModel(model_name):
            await unit.run(command)
    loop.run(_run_on_unit(model_name, unit, command))


def get_application(model_name, application_name):
    """Return an application object

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application to retrieve units for
    :type application_name: str

    :returns: Appliction object
    :rtype: object
    """
    async def _get_application(model_name, application_name):
        async with RunInModel(model_name) as model:
            return model.applications[application_name]
    return loop.run(_get_application(model_name, application_name))


def get_units(model_name, application_name):
    """Return all the units of a given application

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application to retrieve units for
    :type application_name: str

    :returns: List of juju units
    :rtype: [juju.unit.Unit, juju.unit.Unit,...]
    """
    async def _get_units(model_name, application_name):
        async with RunInModel(model_name) as model:
            return model.applications[application_name].units
    return loop.run(_get_units(model_name, application_name))


def get_machines(model_name, application_name):
    """Return all the machines of a given application

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application to retrieve units for
    :type application_name: str

    :returns: List of juju machines
    :rtype: [juju.machine.Machine, juju.machine.Machine,...]
    """
    async def _get_machines(model_name, application_name):
        async with RunInModel(model_name) as model:
            machines = []
            for unit in model.applications[application_name].units:
                machines.append(unit.machine)
            return machines
    return loop.run(_get_machines(model_name, application_name))


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
    async def _get_config(model_name, application_name):
        async with RunInModel(model_name) as model:
            return await model.applications[application_name].get_config()
    return loop.run(_get_config(model_name, application_name))


def set_application_config(model_name, application_name, configuration):
    """Set application configuration

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param configuration: Dictionary of configuration setting(s)
    :type configuration: dict
    :returns: None
    :rtype: None
    """
    async def _set_config(model_name, application_name, configuration):
        async with RunInModel(model_name) as model:
            return await (model.applications[application_name]
                          .set_config(configuration))
    return loop.run(_set_config(model_name, application_name, configuration))


def get_status(model_name):
    """Return full status

    :param model_name: Name of model to query.
    :type model_name: str

    :returns: dictionary of juju status
    :rtype: dict
    """
    async def _get_status(model_name):
        async with RunInModel(model_name) as model:
            return await model.get_status()
    return loop.run(_get_status(model_name))


def main():
    # Run the deploy coroutine in an asyncio event loop, using a helper
    # that abstracts loop creation and teardown.
    print("Current applications: {}".format(", ".join(loop.run(deployed()))))


if __name__ == '__main__':
    main()
