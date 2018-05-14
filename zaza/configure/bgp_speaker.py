#!/usr/bin/env python3

import argparse
import logging
import sys
from zaza.utilities import (
    cli as cli_utils,
    openstack as openstack_utils,
)


EXT_NET = "ext_net"
PRIVATE_NET = "private"
FIP_TEST = "FIP TEST"


def setup_bgp_speaker(peer_application_name, keystone_session=None):
    """Setup BGP Speaker

    :param peer_application_name: String name of BGP peer application
    :type peer_application_name: string
    :param keystone_session: Keystone session object for overcloud
    :type keystone_session: keystoneauth1.session.Session object
    :returns: None
    :rtype: None
    """

    # If a session has not been provided, acquire one
    if not keystone_session:
        keystone_session = openstack_utils.get_overcloud_keystone_session()

    # Get authenticated clients
    neutron_client = openstack_utils.get_neutron_session_client(
        keystone_session)

    # Create BGP speaker
    logging.info("Setting up BGP speaker")
    bgp_speaker = openstack_utils.create_bgp_speaker(
        neutron_client, local_as=12345)

    # Add networks to bgp speaker
    logging.info("Advertising BGP routes")
    openstack_utils.add_network_to_bgp_speaker(
        neutron_client, bgp_speaker, EXT_NET)
    openstack_utils.add_network_to_bgp_speaker(
        neutron_client, bgp_speaker, PRIVATE_NET)
    logging.debug("Advertised routes: {}"
                  .format(
                      neutron_client.list_route_advertised_from_bgp_speaker(
                          bgp_speaker["id"])))

    # Create peer
    logging.info("Setting up BGP peer")
    bgp_peer = openstack_utils.create_bgp_peer(neutron_client,
                                               peer_application_name,
                                               remote_as=10000)
    # Add peer to bgp speaker
    logging.info("Adding BGP peer to BGP speaker")
    openstack_utils.add_peer_to_bgp_speaker(
        neutron_client, bgp_speaker, bgp_peer)

    # Create Floating IP to advertise
    logging.info("Creating floating IP to advertise")
    port = openstack_utils.create_port(neutron_client, FIP_TEST, PRIVATE_NET)
    floating_ip = openstack_utils.create_floating_ip(neutron_client, EXT_NET,
                                                     port=port)
    logging.info(
        "Advertised floating IP: {}".format(
            floating_ip["floating_ip_address"]))


def run_from_cli():
    """Run BGP Speaker setup from CLI

    :returns: None
    :rtype: None
    """

    cli_utils.setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--peer-application", "-a",
                        help="BGP peer application name. Default: quagga",
                        default="quagga")

    options = parser.parse_args()
    peer_application_name = cli_utils.parse_arg(options,
                                                "peer_application")

    setup_bgp_speaker(peer_application_name)


if __name__ == "__main__":
    sys.exit(run_from_cli())
