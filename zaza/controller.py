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
import tempfile
import time
import yaml
from juju.controller import Controller
import subprocess
from zaza import sync_wrapper


async def async_add_model(model_name, config=None):
    """Add a model to the current controller.

    :param model_name: Name to give the new model.
    :type model_name: str
    :param config: Model configuration.
    :type config: dict
    """
    # Tactical fix until https://github.com/juju/python-libjuju/issues/333
    # is resolved
    subprocess.check_call(['juju', 'list-controllers', '--refresh'])
    model_cmd = ['juju', 'add-model', '--no-switch']
    if config:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as fp:
            fp.write(yaml.dump(config, default_flow_style=False))
            model_cmd.extend(['--config', fp.name, model_name])
            fp.seek(0)
            subprocess.check_call(model_cmd)
    else:
        model_cmd.extend([model_name])
        subprocess.check_call(model_cmd)
    time.sleep(10)

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
