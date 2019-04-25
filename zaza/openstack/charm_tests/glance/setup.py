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

"""Code for configuring glance."""

import logging
import zaza.openstack.utilities.openstack as openstack_utils

CIRROS_IMAGE_NAME = "cirros"
LTS_RELEASE = "bionic"
LTS_IMAGE_NAME = "bionic"


def basic_setup():
    """Run setup for testing glance.

    Glance setup for testing glance is currently part of glance functional
    tests. Image setup for other tests to use should go here.
    """


def add_image(image_url, glance_client=None, image_name=None, tags=[]):
    """Retrieve image from ``image_url`` and add it to glance.

    :param image_url: Retrievable URL with image data
    :type image_url: str
    :param glance: Authenticated glanceclient
    :type glance: glanceclient.Client
    :param image_name: Label for the image in glance
    :type image_name: str
    :param tags: List of tags to add to image
    :type tags: list of str
    """
    if not glance_client:
        keystone_session = openstack_utils.get_overcloud_keystone_session()
        glance_client = openstack_utils.get_glance_session_client(
            keystone_session)
    if image_name:
        image = openstack_utils.get_images_by_name(
            glance_client, image_name)

    if image:
        logging.warning('Using existing glance image "{}" ({})'
                        .format(image_name, image[0].id))
    else:
        logging.info('Downloading image {}'.format(image_name or image_url))
        openstack_utils.create_image(
            glance_client,
            image_url,
            image_name,
            tags=tags)


def add_cirros_image(glance_client=None, image_name=None):
    """Add a cirros image to the current deployment.

    :param glance: Authenticated glanceclient
    :type glance: glanceclient.Client
    :param image_name: Label for the image in glance
    :type image_name: str
    """
    image_name = image_name or CIRROS_IMAGE_NAME
    image_url = openstack_utils.find_cirros_image(arch='x86_64')
    add_image(image_url,
              glance_client=glance_client,
              image_name=image_name)


def add_lts_image(glance_client=None, image_name=None, release=None):
    """Add an Ubuntu LTS image to the current deployment.

    :param glance: Authenticated glanceclient
    :type glance: glanceclient.Client
    :param image_name: Label for the image in glance
    :type image_name: str
    :param release: Name of ubuntu release.
    :type release: str
    """
    image_name = image_name or LTS_IMAGE_NAME
    release = release or LTS_RELEASE
    image_url = openstack_utils.find_ubuntu_image(
        release=release,
        arch='amd64')
    add_image(image_url,
              glance_client=glance_client,
              image_name=image_name)
