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

"""Configure network.

For these network configuration functions there are two distinct sets of
settings. There is the configuration of the overcloud's network, the network
under test, settings which may vary from test to test. Then there is the
configuration of the substrate specific undercloud which may vary from one test
environment to another. All of this information is required to setup a valid
test. For the purposes of using these functions please consider the following:

The overcloud network configuration settings are declared by the test caller.
These are the network configuration settings under test and they may range from
a simple GRE setup, to a DVR configuration, to subnetpools with address scopes.
Each test caller may declare a slightly different set of configuration
settings. Here is a simple GRE example:

EXAMPLE_OVERCLOUD_NETWORK_CONFIG = {
    "network_type": "gre",
    "router_name": "provider-router",
    "private_net_cidr": "192.168.21.0/24",
    "external_net_name": "ext_net",
    "external_subnet_name": "ext_net_subnet",
}

The undercloud network configuration settings are substrate specific to the
environment where the tests are being executed. They primarily focus on the
provider network settings. These settings may be overridden by environment
variables. See the doc string documentation for
zaza.utilities.generic_utils.get_undercloud_env_vars for the environment
variables required to be exported and available to zaza. Here is an example of
undercloud settings:
EXAMPLE_DEFAULT_UNDERCLOUD_NETWORK_CONFIG = {
    "start_floating_ip": "10.5.150.0",
    "end_floating_ip": "10.5.150.254",
    "external_dns": "10.5.0.2",
    "external_net_cidr": "10.5.0.0/16",
    "default_gateway": "10.5.0.1",
}

The network configuration functions take in a dictionary parameter called
network_config and it is a combination of the above including environmental
overrides. The recommended use case is as follows:

As a python module:

    import zaza
    # Build network configuration settings
    network_config = {}
    # Declared overcloud settings for the network under test
    network_config.update(EXAMPLE_OVERCLOUD_NETWORK_CONFIG)
    # Default undercloud settings
    network_config.update(EXAMPLE_DEFAULT_UNDERCLOUD_NETWORK_CONFIG)
    # Environment specific settings
    network_config.update(
        zaza.utilities.generic_utils.get_undercloud_env_vars())

    # Configure the SDN network
    zaza.configure.network.setup_sdn(network_config)


As a script from CLI with a YAML file of configuration:

    ./network toploogy_name -f network.yaml
"""

import argparse
import logging
import sys

from zaza.utilities import (
    cli as cli_utils,
    generic as generic_utils,
    juju as juju_utils,
    openstack as openstack_utils,
)


def setup_sdn(network_config, keystone_session=None):
    """Perform setup for Software Defined Network.

    :param network_config: Network configuration settings dictionary
    :type network_config: dict
    :param keystone_session: Keystone session object for overcloud
    :type keystone_session: keystoneauth1.session.Session object
    :returns: None
    :rtype: None
    """
    # If a session has not been provided, acquire one
    if not keystone_session:
        keystone_session = openstack_utils.get_overcloud_keystone_session()

    # Get authenticated clients
    keystone_client = openstack_utils.get_keystone_session_client(
        keystone_session)
    neutron_client = openstack_utils.get_neutron_session_client(
        keystone_session)

    admin_domain = None
    if openstack_utils.get_keystone_api_version() > 2:
        admin_domain = "admin_domain"
    # Resolve the project name from the overcloud openrc into a project id
    project_id = openstack_utils.get_project_id(
        keystone_client,
        "admin",
        domain_name=admin_domain,
    )
    # Network Setup
    subnetpools = False
    if network_config.get("subnetpool_prefix"):
        subnetpools = True

    logging.info("Configuring overcloud network")
    # Create the external network
    ext_network = openstack_utils.create_external_network(
        neutron_client,
        project_id,
        network_config.get("dvr_enabled", False),
        network_config["external_net_name"])
    openstack_utils.create_external_subnet(
        neutron_client,
        project_id,
        ext_network,
        network_config["default_gateway"],
        network_config["external_net_cidr"],
        network_config["start_floating_ip"],
        network_config["end_floating_ip"],
        network_config["external_subnet_name"])
    provider_router = (
        openstack_utils.create_provider_router(neutron_client, project_id))
    openstack_utils.plug_extnet_into_router(
        neutron_client,
        provider_router,
        ext_network)
    ip_version = network_config.get("ip_version") or 4
    subnetpool = None
    if subnetpools:
        address_scope = openstack_utils.create_address_scope(
            neutron_client,
            project_id,
            network_config.get("address_scope"),
            ip_version=ip_version)
        subnetpool = openstack_utils.create_subnetpool(
            neutron_client,
            project_id,
            network_config.get("subnetpool_name"),
            network_config.get("subnetpool_prefix"),
            address_scope)
    project_network = openstack_utils.create_project_network(
        neutron_client,
        project_id,
        shared=False,
        network_type=network_config["network_type"])
    project_subnet = openstack_utils.create_project_subnet(
        neutron_client,
        project_id,
        project_network,
        network_config.get("private_net_cidr"),
        subnetpool=subnetpool,
        ip_version=ip_version)
    openstack_utils.update_subnet_dns(
        neutron_client,
        project_subnet,
        network_config["external_dns"])
    openstack_utils.plug_subnet_into_router(
        neutron_client,
        network_config["router_name"],
        project_network,
        project_subnet)
    openstack_utils.add_neutron_secgroup_rules(neutron_client, project_id)


def setup_gateway_ext_port(network_config, keystone_session=None):
    """Perform setup external port on Neutron Gateway.

    For OpenStack on OpenStack scenarios.

    :param network_config: Network configuration dictionary
    :type network_config: dict
    :param keystone_session: Keystone session object for undercloud
    :type keystone_session: keystoneauth1.session.Session object
    :returns: None
    :rtype: None
    """
    # If a session has not been provided, acquire one
    if not keystone_session:
        keystone_session = openstack_utils.get_undercloud_keystone_session()

    # Get authenticated clients
    nova_client = openstack_utils.get_nova_session_client(keystone_session)
    neutron_client = openstack_utils.get_neutron_session_client(
        keystone_session)

    # Add an interface to the neutron-gateway units and tell juju to use it
    # as the external port.
    if "net_id" in network_config.keys():
        net_id = network_config["net_id"]
    else:
        net_id = None

    logging.info("Configuring network for OpenStack undercloud/provider")
    openstack_utils.configure_gateway_ext_port(
        nova_client,
        neutron_client,
        dvr_mode=network_config.get("dvr_enabled", False),
        net_id=net_id)


def run_from_cli(**kwargs):
    """Run network configurations from CLI.

    Use a YAML file of network configuration settings to configure the
    overcloud network. YAML file of the form:

    topology_name:
      network_type: gre
      router_name: provider-router
      private_net_cidr: 192.168.21.0/24
      external_dns: 10.5.0.2
      external_net_cidr: 10.5.0.0/16
      external_net_name: ext_net
      external_subnet_name: ext_net_subnet
      default_gateway: 10.5.0.1
      start_floating_ip: 10.5.150.0
      end_floating_ip: 10.5.200.254

    :param kwargs: Allow for override of argparse options
    :returns: None
    :rtype: None
    """
    cli_utils.setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("net_topology",
                        help="network topology type, default is GRE",
                        default="gre", nargs="?")
    parser.add_argument("--ignore_env_vars", "-i",
                        help="do not override using environment variables",
                        action="store_true",
                        default=False)
    parser.add_argument("--net_topology_file", "-f",
                        help="Network topology file location",
                        default="network.yaml")
    parser.add_argument("--cacert", help="Path to CA certificate bundle file",
                        default=None)
    # Handle CLI options
    options = parser.parse_args()
    net_topology = (kwargs.get('net_toplogoy') or
                    cli_utils.parse_arg(options, "net_topology"))
    net_topology_file = (kwargs.get('net_topology_file') or
                         cli_utils.parse_arg(options, "net_topology_file"))
    ignore_env_vars = (kwargs.get('ignore_env_vars') or
                       cli_utils.parse_arg(options, "ignore_env_vars"))
    cacert = (kwargs.get('cacert') or
              cli_utils.parse_arg(options, "cacert"))

    logging.info("Setting up %s network" % (net_topology))
    network_config = generic_utils.get_network_config(
        net_topology, ignore_env_vars, net_topology_file)

    # Handle network for Openstack-on-Openstack scenarios
    if juju_utils.get_provider_type() == "openstack":
        undercloud_ks_sess = openstack_utils.get_undercloud_keystone_session(
            verify=cacert)
        setup_gateway_ext_port(network_config,
                               keystone_session=undercloud_ks_sess)

    overcloud_ks_sess = openstack_utils.get_overcloud_keystone_session(
        verify=cacert)
    setup_sdn(network_config, keystone_session=overcloud_ks_sess)


if __name__ == "__main__":
    sys.exit(run_from_cli())
