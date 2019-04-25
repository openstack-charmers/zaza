#!/usr/bin/env python3

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

"""Module to setup BGP speaker configuration."""

import argparse
import logging
import sys
import neutronclient
from zaza.openstack.utilities import (
    cli as cli_utils,
    openstack as openstack_utils,
    juju as juju_utils,
)


EXT_NET = "ext_net"
PRIVATE_NET = "private"
FIP_TEST = "FIP TEST"


def setup_bgp_speaker(peer_application_name, keystone_session=None):
    """Perform BGP Speaker setup.

    :param peer_application_name: String name of BGP peer application
    :type peer_application_name: string
    :param keystone_session: Keystone session object for overcloud
    :type keystone_session: keystoneauth1.session.Session object
    :returns: None
    :rtype: None
    """
    # Get ASNs from deployment
    dr_relation = juju_utils.get_relation_from_unit(
        'neutron-dynamic-routing',
        peer_application_name,
        'bgpclient')
    peer_asn = dr_relation.get('asn')
    logging.debug('peer ASn: "{}"'.format(peer_asn))
    peer_relation = juju_utils.get_relation_from_unit(
        peer_application_name,
        'neutron-dynamic-routing',
        'bgp-speaker')
    dr_asn = peer_relation.get('asn')
    logging.debug('our ASn: "{}"'.format(dr_asn))

    # If a session has not been provided, acquire one
    if not keystone_session:
        keystone_session = openstack_utils.get_overcloud_keystone_session()

    # Get authenticated clients
    neutron_client = openstack_utils.get_neutron_session_client(
        keystone_session)

    # Create BGP speaker
    logging.info("Setting up BGP speaker")
    bgp_speaker = openstack_utils.create_bgp_speaker(
        neutron_client, local_as=dr_asn)

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
                                               remote_as=peer_asn)
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

    # NOTE(fnordahl): As a workaround for LP: #1784083 remove BGP speaker from
    # dragent and add it back.
    logging.info(
        "Waiting for Neutron agent 'neutron-bgp-dragent' to appear...")
    keystone_session = openstack_utils.get_overcloud_keystone_session()
    neutron_client = openstack_utils.get_neutron_session_client(
        keystone_session)
    agents = openstack_utils.neutron_agent_appears(neutron_client,
                                                   'neutron-bgp-dragent')
    agent_id = None
    for agent in agents.get('agents', []):
        agent_id = agent.get('id', None)
        if agent_id is not None:
            break
    logging.info(
        'Waiting for BGP speaker to appear on agent "{}"...'.format(agent_id))
    bgp_speakers = openstack_utils.neutron_bgp_speaker_appears_on_agent(
        neutron_client, agent_id)
    logging.info(
        "Removing and adding back bgp-speakers to agent (LP: #1784083)...")
    while True:
        try:
            for bgp_speaker in bgp_speakers.get('bgp_speakers', []):
                bgp_speaker_id = bgp_speaker.get('id', None)
                logging.info('removing "{}" from "{}"'
                             ''.format(bgp_speaker_id, agent_id))
                neutron_client.remove_bgp_speaker_from_dragent(
                    agent_id, bgp_speaker_id)
        except neutronclient.common.exceptions.NotFound as e:
            logging.info('Exception: "{}"'.format(e))
            break
    neutron_client.add_bgp_speaker_to_dragent(
        agent_id, {'bgp_speaker_id': bgp_speaker_id})


def run_from_cli():
    """Run BGP Speaker setup from CLI.

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
