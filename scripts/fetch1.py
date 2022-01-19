#!/usr/bin/env python3

from juju.model import Model
import asyncio
import sys

# set to use something other than the current model
MODEL=None


async def get_units():
    model = Model()
    if MODEL is None:
        await model.connect()
    else:
        await model.connect_model(MODEL)
    units = sorted(model.applications['ubuntu'].units, key=lambda u: u.name)
    await model.disconnect()
    return units


async def get_address(unit):
    model = Model()
    await model.connect_model(MODEL)
    print("{} Address: .public_address {}".format(unit.name, unit.public_address))
    while True:
        try:
            print("{} Address: get_public_address() {}".format(unit.name, await unit.get_public_address()))
            break
        except Exception as e:
            print("Exception was: %s", e)
            await asyncio.sleep(.25)
            await ensure_model_connected(model)
    print("{} Address: .public_address {}".format(unit.name, unit.public_address))
    print("\n")
    await model.disconnect()


def run_it(step):
    loop = asyncio.get_event_loop()
    task = loop.create_task(step)
    loop.run_until_complete(asyncio.wait([task], loop=loop))
    result = task.result()
    return result


async def get_unit(n):
    units = await get_units()
    print("units", units)
    await get_address(units[n])


def is_model_disconnected(model):
    """Return True if the model is disconnected.

    :param model: the model to check
    :type model: :class:'juju.Model'
    :returns: True if disconnected
    :rtype: bool
    """
    print("is_model_disconnected?: %s, %s", model.is_connected(), model.connection().is_open)
    return not (model.is_connected() and model.connection().is_open)


async def ensure_model_connected(model):
    """Ensure that the model is connected.

    If model is disconnected then reconnect it.

    :param model: the model to check
    :type model: :class:'juju.Model'
    """
    if is_model_disconnected(model):
        model_name = model.info.name
        print(
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
        print("Attempting to reconnect model %s", model_name)
        await model.connect_model(model_name)


if __name__ == '__main__':
    unit_num = 0
    if len(sys.argv) > 1:
        unit_num = int(sys.argv[1])

    run_it(get_unit(unit_num))
    asyncio.get_event_loop().close()

