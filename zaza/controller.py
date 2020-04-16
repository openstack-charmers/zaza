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

"""Module for interacting with a juju controller."""

import logging
from juju.controller import Controller
import subprocess
from zaza import sync_wrapper


async def async_add_model(model_name, config=None, region=None):
    """Add a model to the current controller.

    :param model_name: Name to give the new model.
    :type model_name: str
    :param config: Model configuration.
    :type config: dict
    :param region: Region in which to create the model.
    :type region: str
    """
    controller = Controller()
    await controller.connect()
    logging.debug("Adding model {}".format(model_name))
    model = await controller.add_model(
        model_name, config=config, region=region)
    # issue/135 It is necessary to disconnect the model here or async spews
    # tracebacks even during a successful run.
    await model.disconnect()
    await controller.disconnect()

add_model = sync_wrapper(async_add_model)


async def async_destroy_model(model_name):
    """Remove a model from the current controller.

    :param model_name: Name of model to remove
    :type model_name: str
    """
    controller = Controller()
    await controller.connect()
    logging.debug("Destroying model {}".format(model_name))
    await controller.destroy_model(model_name)
    await controller.disconnect()

destroy_model = sync_wrapper(async_destroy_model)


async def async_cloud(name=None):
    """Return information about cloud.

    :param name: Cloud name. If not specified, the cloud where
                 the controller lives on is returned.
    :type name: Optional[str]
    :returns: Information on all clouds in the controller.
    :rtype: CloudResult
    """
    controller = Controller()
    await controller.connect()
    cloud = await controller.cloud(name=name)
    await controller.disconnect()
    return cloud

cloud = sync_wrapper(async_cloud)


def get_cloud_type(name=None):
    """Return type of cloud.

    :param name: Cloud name. If not specified, the cloud where
                 the controller lives on is returned.
    :type name: Optional[str]
    :returns: Type of cloud
    :rtype: str
    """
    _cloud = cloud(name=name)
    return _cloud.cloud.type_


async def async_get_cloud():
    """Return the name of the current cloud.

    :returns: Name of cloud
    :rtype: str
    """
    controller = Controller()
    await controller.connect()
    cloud = await controller.get_cloud()
    await controller.disconnect()
    return cloud

get_cloud = sync_wrapper(async_get_cloud)


async def async_list_models():
    """Return a list of tha available clouds.

    :returns: List of clouds
    :rtype: list
    """
    controller = Controller()
    await controller.connect()
    models = await controller.list_models()
    await controller.disconnect()
    return models

list_models = sync_wrapper(async_list_models)


def go_list_models():
    """Execute juju models.

    NOTE: Excuting the juju models command updates the local cache of models.
    Python-juju currently does not update the local cache on add model.
    https://github.com/juju/python-libjuju/issues/267

    :returns: None
    :rtype: None
    """
    cmd = ["juju", "models"]
    subprocess.check_call(cmd)
