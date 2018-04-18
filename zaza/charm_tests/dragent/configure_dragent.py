#!/usr/bin/env python3

import os

from zaza.configure import (
    network,
    bgp_speaker,
)
from zaza.utilities import (
    _local_utils,
    openstack_utils,
)

DEFAULT_PEER_APPLICATION_NAME = "quagga"
# Find a default network.yaml in tests/bundles/network.yaml of the charm
DEFAULT_TOPOLOGY_FILE = os.path.join("tests", "bundles", "network.yaml")


def setup(net_topology="pool", net_topology_file="network.yaml"):
    """Setup BGP networking

    :param net_topology: String name of network topology
    :type net_topology: string
    :param net_info: Network configuration dictionary
    :type net_info: dict
    :param keystone_session: Keystone session object for overcloud
    :type keystone_session: keystoneauth1.session.Session object
    :returns: None
    :rtype: None
    """

    _local_utils.setup_logging()

    # Check for the network.yaml configuration
    if (not os.path.exists(net_topology_file) and
            os.path.exists(DEFAULT_TOPOLOGY_FILE)):
        net_topology_file = DEFAULT_TOPOLOGY_FILE

    # Get network configuration from YAML and/or environment variables
    net_info = _local_utils.get_net_info(net_topology,
                                         net_topology_file=net_topology_file)

    # Get keystone session
    keystone_session = openstack_utils.get_overcloud_keystone_session()

    # Confugre the network
    network.setup_sdn(
        net_topology, net_info, keystone_session=keystone_session)
    # Configure BGP
    bgp_speaker.setup_bgp_speaker(
        peer_application_name=DEFAULT_PEER_APPLICATION_NAME,
        keystone_session=keystone_session)
