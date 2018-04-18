#!/usr/bin/env python3

import argparse
import logging
import sys

from zaza.utilities import _local_utils
from zaza.utilities import openstack_utils


def setup_sdn(net_topology, net_info, keystone_session=None):
    """Setup Software Defined Network

    :param net_topology: String name of network topology
    :type net_topology: string
    :param net_info: Network configuration dictionary
    :type net_info: dict
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

    # Resolve the project name from the overcloud opentackrc into a project id
    project_id = openstack_utils.get_project_id(
        keystone_client,
        "admin",
    )
    # Network Setup
    subnetpools = False
    if net_info.get("subnetpool_prefix"):
        subnetpools = True

    logging.info("Configuring overcloud network")
    # Create the external network
    ext_network = openstack_utils.create_external_network(
        neutron_client,
        project_id,
        net_info.get("dvr_enabled", False),
        net_info["external_net_name"])
    openstack_utils.create_external_subnet(
        neutron_client,
        project_id,
        ext_network,
        net_info["default_gateway"],
        net_info["external_net_cidr"],
        net_info["start_floating_ip"],
        net_info["end_floating_ip"],
        net_info["external_subnet_name"])
    # Should this be --enable_snat = False
    provider_router = (
        openstack_utils.create_provider_router(neutron_client, project_id))
    openstack_utils.plug_extnet_into_router(
        neutron_client,
        provider_router,
        ext_network)
    ip_version = net_info.get("ip_version") or 4
    subnetpool = None
    if subnetpools:
        address_scope = openstack_utils.create_address_scope(
            neutron_client,
            project_id,
            net_info.get("address_scope"),
            ip_version=ip_version)
        subnetpool = openstack_utils.create_subnetpool(
            neutron_client,
            project_id,
            net_info.get("subnetpool_name"),
            net_info.get("subnetpool_prefix"),
            address_scope)
    project_network = openstack_utils.create_project_network(
        neutron_client,
        project_id,
        shared=False,
        network_type=net_info["network_type"])
    project_subnet = openstack_utils.create_project_subnet(
        neutron_client,
        project_id,
        project_network,
        net_info.get("private_net_cidr"),
        subnetpool=subnetpool,
        ip_version=ip_version)
    openstack_utils.update_subnet_dns(
        neutron_client,
        project_subnet,
        net_info["external_dns"])
    openstack_utils.plug_subnet_into_router(
        neutron_client,
        net_info["router_name"],
        project_network,
        project_subnet)
    openstack_utils.add_neutron_secgroup_rules(neutron_client, project_id)


def setup_gateway_ext_port(net_info, keystone_session=None):
    """Setup external port on Neutron Gateway.
    For OpenStack on OpenStack scenarios

    :param net_info: Network configuration dictionary
    :type net_info: dict
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
    if "net_id" in net_info.keys():
        net_id = net_info["net_id"]
    else:
        net_id = None

    logging.info("Configuring network for OpenStack undercloud/provider")
    openstack_utils.configure_gateway_ext_port(
        nova_client,
        neutron_client,
        dvr_mode=net_info.get("dvr_enabled", False),
        net_id=net_id)


def run_from_cli():
    """Run network configurations from CLI

    :returns: None
    :rtype: None
    """

    _local_utils.setup_logging()
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
    # Handle CLI options
    options = parser.parse_args()
    net_topology = _local_utils.parse_arg(options, "net_topology")
    net_topology_file = _local_utils.parse_arg(options, "net_topology_file")
    ignore_env_vars = _local_utils.parse_arg(options, "ignore_env_vars")

    logging.info("Setting up %s network" % (net_topology))
    net_info = _local_utils.get_net_info(
        net_topology, ignore_env_vars, net_topology_file)

    # Handle network for Openstack-on-Openstack scenarios
    if _local_utils.get_provider_type() == "openstack":
        setup_gateway_ext_port(net_info)

    setup_sdn(net_topology, net_info)


if __name__ == "__main__":
    sys.exit(run_from_cli())
