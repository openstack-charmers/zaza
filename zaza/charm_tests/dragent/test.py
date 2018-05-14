#!/usr/bin/env python3

import argparse
import logging
import sys
import tenacity

from zaza import model
from zaza.charm_lifecycle import utils as lifecycle_utils
from zaza.utilities import (
    cli as cli_utils,
    juju as juju_utils,
    openstack as openstack_utils,
)


def test_bgp_routes(peer_application_name="quagga", keystone_session=None):
    """Test BGP routes

    :param peer_application_name: String name of BGP peer application
    :type peer_application_name: string
    :param keystone_session: Keystone session object for overcloud
    :type keystone_session: keystoneauth1.session.Session object
    :raises: AssertionError if expected BGP routes are not found
    :returns: None
    :rtype: None
    """

    # If a session has not been provided, acquire one
    if not keystone_session:
        keystone_session = openstack_utils.get_overcloud_keystone_session()

    # Get authenticated clients
    neutron_client = openstack_utils.get_neutron_session_client(
        keystone_session)

    # Get the peer unit
    peer_unit = model.get_units(
        lifecycle_utils.get_juju_model(), peer_application_name)[0].entity_id

    # Get expected advertised routes
    private_cidr = neutron_client.list_subnets(
        name="private_subnet")["subnets"][0]["cidr"]
    floating_ip_cidr = "{}/32".format(
        neutron_client.list_floatingips()
        ["floatingips"][0]["floating_ip_address"])

    # This test may run immediately after configuration. It may take time for
    # routes to propogate via BGP. Do a binary backoff.
    @tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, max=60),
                    reraise=True, stop=tenacity.stop_after_attempt(8))
    def _assert_cidr_in_peer_routing_table(peer_unit, cidr):
        logging.debug("Checking for {} on BGP peer {}"
                      .format(cidr, peer_unit))
        # Run show ip route bgp on BGP peer
        routes = juju_utils.remote_run(
            peer_unit, remote_cmd='vtysh -c "show ip route bgp"')
        logging.debug(routes)
        assert cidr in routes, (
            "CIDR, {}, not found in BGP peer's routing table" .format(cidr))

    _assert_cidr_in_peer_routing_table(peer_unit, private_cidr)
    logging.info("Private subnet CIDR, {}, found in routing table"
                 .format(private_cidr))
    _assert_cidr_in_peer_routing_table(peer_unit, floating_ip_cidr)
    logging.info("Floating IP CIDR, {}, found in routing table"
                 .format(floating_ip_cidr))


def run_from_cli():
    """Run test for BGP routes from CLI

    :returns: None
    :rtype: None
    """

    cli_utils.setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--peer-application", "-a",
                        help="BGP Peer application name. Default: quagga",
                        default="quagga")
    options = parser.parse_args()

    peer_application_name = cli_utils.parse_arg(options,
                                                "peer_application")

    test_bgp_routes(peer_application_name)


if __name__ == "__main__":
    sys.exit(run_from_cli())
