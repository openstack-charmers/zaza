import logging
from juju.controller import Controller
from zaza import sync_wrapper


async def async_add_model(model_name):
    controller = Controller()
    await controller.connect()
    logging.debug("Adding model {}".format(model_name))
    model = await controller.add_model(model_name)
    await model.connect()
    model_name = model.info.name
    await model.disconnect()
    await controller.disconnect()
    return model_name

add_model = sync_wrapper(async_add_model)


async def async_destroy_model(model_name):
    controller = Controller()
    await controller.connect()
    logging.debug("Destroying model {}".format(model_name))
    await controller.destroy_model(model_name)
    await controller.disconnect()

destroy_model = sync_wrapper(async_destroy_model)


async def async_get_cloud():
    controller = Controller()
    await controller.connect()
    cloud = await controller.get_cloud()
    await controller.disconnect()
    return cloud

get_cloud = sync_wrapper(async_get_cloud)


async def async_list_models():
    controller = Controller()
    await controller.connect()
    models = await controller.list_models()
    await controller.disconnect()
    return models

list_models = sync_wrapper(async_list_models)
