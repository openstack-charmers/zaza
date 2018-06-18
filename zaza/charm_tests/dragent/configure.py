#!/usr/bin/env python3
"""Setup for BGP deployments."""

from zaza.configure import (
    network,
    bgp_speaker,
)
from zaza.utilities import (
    cli as cli_utils,
    generic as generic_utils,
    openstack as openstack_utils,
)

DEFAULT_PEER_APPLICATION_NAME = "quagga"

# The overcloud network configuration settings are declared.
# These are the network configuration settings under test.
OVERCLOUD_NETWORK_CONFIG = {
    "network_type": "gre",
    "router_name": "provider-router",
    "ip_version": "4",
    "address_scope": "public",
    "external_net_name": "ext_net",
    "external_subnet_name": "ext_net_subnet",
    "prefix_len": "24",
    "subnetpool_name": "pooled_subnets",
    "subnetpool_prefix": "192.168.0.0/16",
}

# The undercloud network configuration settings are substrate specific to
# the environment where the tests are being executed. These settings may be
# overridden by environment variables. See the doc string documentation for
# zaza.utilities.generic_utils.get_undercloud_env_vars for the environment
# variables required to be exported and available to zaza.
# These are default settings provided as an example.
DEFAULT_UNDERCLOUD_NETWORK_CONFIG = {
    "start_floating_ip": "10.5.150.0",
    "end_floating_ip": "10.5.150.254",
    "external_dns": "10.5.0.2",
    "external_net_cidr": "10.5.0.0/16",
    "default_gateway": "10.5.0.1",
}


def setup():
    """Run setup for BGP networking.

    Configure the following:
        The overcloud network using subnet pools
        The overcloud BGP speaker
        The BGP peer
        Advertising of the FIPs via BGP
        Advertising of the project network(s) via BGP

    :returns: None
    :rtype: None
    """
    cli_utils.setup_logging()

    # Get network configuration settings
    network_config = {}
    # Declared overcloud settings
    network_config.update(OVERCLOUD_NETWORK_CONFIG)
    # Default undercloud settings
    network_config.update(DEFAULT_UNDERCLOUD_NETWORK_CONFIG)
    # Environment specific settings
    network_config.update(generic_utils.get_undercloud_env_vars())

    # Get keystone session
    keystone_session = openstack_utils.get_overcloud_keystone_session()

    # Confugre the overcloud network
    network.setup_sdn(network_config, keystone_session=keystone_session)
    # Configure BGP
    bgp_speaker.setup_bgp_speaker(
        peer_application_name=DEFAULT_PEER_APPLICATION_NAME,
        keystone_session=keystone_session)
