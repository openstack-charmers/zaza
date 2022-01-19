#!/usr/bin/env python3

from juju.model import Model
import asyncio

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
    print("{} Address: get_public_address() {}".format(unit.name, await unit.get_public_address()))
    print("{} Address: .public_address {}".format(unit.name, unit.public_address))
    print("\n")
    await model.disconnect()


def run_it(step):
    loop = asyncio.get_event_loop()
    task = loop.create_task(step)
    loop.run_until_complete(asyncio.wait([task], loop=loop))
    result = task.result()
    return result


def get_all_units():
    units = run_it(get_units())
    print("units", units)
    for unit in units:
        run_it(get_address(unit))


get_all_units()
asyncio.get_event_loop().close()
