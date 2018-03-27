from juju import loop
import subprocess
import yaml

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
    app = unit_name.split('/')[0]
    for u in model.applications[app].units:
        if u.entity_id == unit_name:
            unit = u
            break
    else:
        raise Exception
    return unit


async def _scp_to_unit(unit_name, source_file, target_file):
    model = Model()
    await model.connect_current()
    try:
        unit = get_unit_from_name(unit_name, model)
        #await unit.scp_to(source_file, target_file)
    finally:
        # Disconnect from the api server and cleanup.
        await model.disconnect()


async def _get_first_unit(app_name):
    model = Model()
    await model.connect_current()
    try:
        unit = model.applications[app_name].units[0]
    finally:
        # Disconnect from the api server and cleanup.
        await model.disconnect()
    return unit


def scp_from_unit(unit_name, source_file, target_file):
    cmd = ['juju', 'scp', '{}:{}'.format(unit_name, source_file), target_file]
    subprocess.check_call(cmd)


def scp_to_unit(unit_name, source_file, target_file):
    cmd = ['juju', 'scp', source_file, '{}:{}'.format(unit_name, target_file)]
    subprocess.check_call(cmd)


def get_status():
    status = subprocess.check_output(['juju', 'status', '--format', 'yaml'])
    return yaml.load(status)


def get_first_unit(app_name):
    status = get_status()
    return sorted(status['applications'][app_name]['units'].keys())[0]


def get_app_ips(app_name):
    status = get_status()
    addresses = []
    for unit in status['applications'][app_name]['units'].values():
        addresses.append(unit['public-address'])
    return addresses


def main():
    # Run the deploy coroutine in an asyncio event loop, using a helper
    # that abstracts loop creation and teardown.
    print("Current applications: {}".format(", ".join(loop.run(deployed()))))


if __name__ == '__main__':
    main()
