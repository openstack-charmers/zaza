"""Code for configureing nova."""

import zaza.utilities.openstack as openstack_utils
from zaza.utilities import (
    cli as cli_utils,
)
import zaza.charm_tests.nova.utils as nova_utils


def create_flavors(nova_client=None):
    """Create basic flavors.

    :param nova_client: Authenticated nova client
    :type nova_client: novaclient.v2.client.Client
    """
    if not nova_client:
        keystone_session = openstack_utils.get_overcloud_keystone_session()
        nova_client = openstack_utils.get_nova_session_client(
            keystone_session)
    cli_utils.setup_logging()
    names = [flavor.name for flavor in nova_client.flavors.list()]
    for flavor in nova_utils.FLAVORS.keys():
        if flavor not in names:
            nova_client.flavors.create(
                name=flavor,
                ram=nova_utils.FLAVORS[flavor]['ram'],
                vcpus=nova_utils.FLAVORS[flavor]['vcpus'],
                disk=nova_utils.FLAVORS[flavor]['disk'],
                flavorid=nova_utils.FLAVORS[flavor]['flavorid'])


def manage_ssh_key(nova_client=None):
    """Create basic flavors.

    :param nova_client: Authenticated nova client
    :type nova_client: novaclient.v2.client.Client
    """
    if not nova_client:
        keystone_session = openstack_utils.get_overcloud_keystone_session()
        nova_client = openstack_utils.get_nova_session_client(
            keystone_session)
    cli_utils.setup_logging()
    if not openstack_utils.valid_key_exists(nova_client,
                                            nova_utils.KEYPAIR_NAME):
        key = openstack_utils.create_ssh_key(
            nova_client,
            nova_utils.KEYPAIR_NAME,
            replace=True)
        openstack_utils.write_private_key(
            nova_utils.KEYPAIR_NAME,
            key.private_key)
