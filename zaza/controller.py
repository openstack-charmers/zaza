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

import json
import logging
import subprocess
import time

import jubilant

import zaza.utilities.exceptions


def add_model(model_name, config=None, cloud_name=None,
              credential_name=None, region=None):
    """Add a model to the current controller.

    :param model_name: Name to give the new model.
    :type model_name: str
    :param config: Model configuration.
    :type config: Optional[dict]
    :param cloud_name: Name of the cloud (or cloud/region) to use.
    :type cloud_name: Optional[str]
    :param credential_name: Name of the credential to use.
    :type credential_name: Optional[str]
    :param region: Region in which to create the model.
    :type region: Optional[str]
    """
    cloud = cloud_name
    if cloud is not None and region is not None:
        cloud = '{}/{}'.format(cloud_name, region)
    elif region is not None:
        cloud = region

    juju = jubilant.Juju()
    logging.debug("Adding model {}".format(model_name))
    juju.add_model(
        model_name,
        cloud,
        config=config,
        credential=credential_name,
    )


def destroy_model(model_name):
    """Remove a model from the current controller.

    :param model_name: Name of model to remove.
    :type model_name: str
    :raises: zaza.utilities.exceptions.DestroyModelFailed
    """
    juju = jubilant.Juju()
    logging.info("Destroying model {}".format(model_name))
    juju.destroy_model(model_name, destroy_storage=True, force=True,
                       timeout=600)

    # Wait for the model to disappear from the list.
    for attempt in range(1, 21):
        logging.info(
            "Waiting for model to be fully destroyed: attempt: {}"
            .format(attempt))
        remaining = list_models()
        if model_name not in remaining:
            break
        time.sleep(10)
    else:
        raise zaza.utilities.exceptions.DestroyModelFailed(
            "Destroying model {} failed.".format(model_name))

    logging.info("Model {} destroyed.".format(model_name))


def cloud(name=None):
    """Return information about a cloud.

    :param name: Cloud name.  If not specified, the cloud where the
                 controller lives is returned.
    :type name: Optional[str]
    :returns: Parsed cloud information dict.
    :rtype: dict
    """
    juju = jubilant.Juju()
    args = ['clouds', '--format', 'json']
    if name:
        args.append(name)
    stdout = juju.cli(*args, include_model=False)
    return json.loads(stdout)


def get_cloud_type(name=None):
    """Return type of cloud.

    :param name: Cloud name.  If not specified, the cloud where the
                 controller lives is returned.
    :type name: Optional[str]
    :returns: Type of cloud.
    :rtype: str
    """
    clouds = cloud(name=name)
    # juju clouds --format json returns a dict of cloud_name -> cloud_info
    for _cloud_info in clouds.values():
        return _cloud_info.get('type', '')
    return ''


def get_cloud():
    """Return the name of the current cloud.

    :returns: Name of the cloud the current controller is on.
    :rtype: str
    """
    juju = jubilant.Juju()
    stdout = juju.cli('show-controller', '--format', 'json',
                      include_model=False)
    data = json.loads(stdout)
    # data is a dict of controller_name -> controller_info
    for info in data.values():
        return info.get('details', {}).get('cloud', '')
    return ''


def list_models():
    """Return a list of the available models.

    :returns: List of model names.
    :rtype: list[str]
    """
    juju = jubilant.Juju()
    stdout = juju.cli('models', '--format', 'json', include_model=False)
    data = json.loads(stdout)
    return [m['name'].split('/')[-1] for m in data.get('models', [])]


def go_list_models():
    """Execute juju models to refresh the local cache.

    NOTE: Executing the juju models command updates the local cache of models.
    Python-juju currently does not update the local cache on add model.
    https://github.com/juju/python-libjuju/issues/267

    :returns: None
    :rtype: None
    """
    cmd = ["juju", "models"]
    subprocess.check_call(cmd)
