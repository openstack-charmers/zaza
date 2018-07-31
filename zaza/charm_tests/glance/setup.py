"""Code for configuring glance."""

import zaza.utilities.openstack as openstack_utils


def basic_setup():
    """Run setup for testing glance.

    Glance setup for testing glance is currently part of glance functional
    tests. Image setup for other tests to use should go here.
    """


def add_cirros_image(glance_client=None):
    """Add a cirros image to the current deployment.

    :param glance: Authenticated glanceclient
    :type glance: glanceclient.Client
    """
    if not glance_client:
        keystone_session = openstack_utils.get_overcloud_keystone_session()
        glance_client = openstack_utils.get_glance_session_client(
            keystone_session)
    image_url = openstack_utils.find_cirros_image(arch='x86_64')
    openstack_utils.create_image(
        glance_client,
        image_url,
        'cirros')


def add_lts_image(glance_client=None):
    """Add an Ubuntu LTS image to the current deployment.

    :param glance: Authenticated glanceclient
    :type glance: glanceclient.Client
    """
    if not glance_client:
        keystone_session = openstack_utils.get_overcloud_keystone_session()
        glance_client = openstack_utils.get_glance_session_client(
            keystone_session)
    image_url = openstack_utils.find_ubuntu_image(
        release='bionic',
        arch='amd64')
    print(image_url)
    openstack_utils.create_image(
        glance_client,
        image_url,
        'bionic')
