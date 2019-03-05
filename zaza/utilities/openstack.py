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

"""Module for interacting with OpenStack.

This module contains a number of functions for interacting with Openstack.
"""
from .os_versions import (
    OPENSTACK_CODENAMES,
    SWIFT_CODENAMES,
    PACKAGE_CODENAMES,
    OPENSTACK_RELEASES_PAIRS,
)

from openstack import connection

from cinderclient import client as cinderclient
from glanceclient import Client as GlanceClient

from keystoneclient.v2_0 import client as keystoneclient_v2
from keystoneclient.v3 import client as keystoneclient_v3
from keystoneauth1 import session
from keystoneauth1.identity import (
    v3,
    v2,
)
import zaza.utilities.cert as cert
from novaclient import client as novaclient_client
from neutronclient.v2_0 import client as neutronclient
from neutronclient.common import exceptions as neutronexceptions
from octaviaclient.api.v2 import octavia as octaviaclient
from swiftclient import client as swiftclient

import io
import juju_wait
import logging
import os
import paramiko
import re
import six
import subprocess
import sys
import tempfile
import tenacity
import urllib

from zaza import model
from zaza.utilities import (
    exceptions,
    generic as generic_utils,
    juju as juju_utils,
)

CIRROS_RELEASE_URL = 'http://download.cirros-cloud.net/version/released'
CIRROS_IMAGE_URL = 'http://download.cirros-cloud.net'
UBUNTU_IMAGE_URLS = {
    'bionic': ('http://cloud-images.ubuntu.com/{release}/current/'
               '{release}-server-cloudimg-{arch}.img')
}

CHARM_TYPES = {
    'neutron': {
        'pkg': 'neutron-common',
        'origin_setting': 'openstack-origin'
    },
    'nova': {
        'pkg': 'nova-common',
        'origin_setting': 'openstack-origin'
    },
    'glance': {
        'pkg': 'glance-common',
        'origin_setting': 'openstack-origin'
    },
    'cinder': {
        'pkg': 'cinder-common',
        'origin_setting': 'openstack-origin'
    },
    'keystone': {
        'pkg': 'keystone',
        'origin_setting': 'openstack-origin'
    },
    'openstack-dashboard': {
        'pkg': 'openstack-dashboard',
        'origin_setting': 'openstack-origin'
    },
    'ceilometer': {
        'pkg': 'ceilometer-common',
        'origin_setting': 'openstack-origin'
    },
}
UPGRADE_SERVICES = [
    {'name': 'keystone', 'type': CHARM_TYPES['keystone']},
    {'name': 'nova-cloud-controller', 'type': CHARM_TYPES['nova']},
    {'name': 'nova-compute', 'type': CHARM_TYPES['nova']},
    {'name': 'neutron-api', 'type': CHARM_TYPES['neutron']},
    {'name': 'neutron-gateway', 'type': CHARM_TYPES['neutron']},
    {'name': 'glance', 'type': CHARM_TYPES['glance']},
    {'name': 'cinder', 'type': CHARM_TYPES['cinder']},
    {'name': 'openstack-dashboard',
     'type': CHARM_TYPES['openstack-dashboard']},
    {'name': 'ceilometer', 'type': CHARM_TYPES['ceilometer']},
]


WORKLOAD_STATUS_EXCEPTIONS = {
    'vault': {
        'workload-status': 'blocked',
        'workload-status-message': 'Vault needs to be initialized'},
    'easyrsa': {
        'workload-status-message': 'Certificate Authority connected.'},
    'etcd': {
        'workload-status-message': 'Healthy'},
    'memcached': {
        'workload-status': 'unknown',
        'workload-status-message': ''},
    'mongodb': {
        'workload-status': 'unknown',
        'workload-status-message': ''},
    'postgresql': {
        'workload-status-message': 'Live'}}


# Openstack Client helpers
def get_ks_creds(cloud_creds, scope='PROJECT'):
    """Return the credentials for authenticating against keystone.

    :param cloud_creds: Openstack RC environment credentials
    :type cloud_creds: dict
    :param scope: Authentication scope: PROJECT or DOMAIN
    :type scope: string
    :returns: Credentials dictionary
    :rtype: dict
    """
    if cloud_creds.get('API_VERSION', 2) == 2:
        auth = {
            'username': cloud_creds['OS_USERNAME'],
            'password': cloud_creds['OS_PASSWORD'],
            'auth_url': cloud_creds['OS_AUTH_URL'],
            'tenant_name': (cloud_creds.get('OS_PROJECT_NAME') or
                            cloud_creds['OS_TENANT_NAME']),
        }
    else:
        if scope == 'DOMAIN':
            auth = {
                'username': cloud_creds['OS_USERNAME'],
                'password': cloud_creds['OS_PASSWORD'],
                'auth_url': cloud_creds['OS_AUTH_URL'],
                'user_domain_name': cloud_creds['OS_USER_DOMAIN_NAME'],
                'domain_name': cloud_creds['OS_DOMAIN_NAME'],
            }
        else:
            auth = {
                'username': cloud_creds['OS_USERNAME'],
                'password': cloud_creds['OS_PASSWORD'],
                'auth_url': cloud_creds['OS_AUTH_URL'],
                'user_domain_name': cloud_creds['OS_USER_DOMAIN_NAME'],
                'project_domain_name': cloud_creds['OS_PROJECT_DOMAIN_NAME'],
                'project_name': cloud_creds['OS_PROJECT_NAME'],
            }
    return auth


def get_glance_session_client(session):
    """Return glanceclient authenticated by keystone session.

    :param session: Keystone session object
    :type session: keystoneauth1.session.Session object
    :returns: Authenticated glanceclient
    :rtype: glanceclient.Client
    """
    return GlanceClient('2', session=session)


def get_nova_session_client(session):
    """Return novaclient authenticated by keystone session.

    :param session: Keystone session object
    :type session: keystoneauth1.session.Session object
    :returns: Authenticated novaclient
    :rtype: novaclient.Client object
    """
    return novaclient_client.Client(2, session=session)


def get_neutron_session_client(session):
    """Return neutronclient authenticated by keystone session.

    :param session: Keystone session object
    :type session: keystoneauth1.session.Session object
    :returns: Authenticated neutronclient
    :rtype: neutronclient.Client object
    """
    return neutronclient.Client(session=session)


def get_swift_session_client(session):
    """Return swiftclient authenticated by keystone session.

    :param session: Keystone session object
    :type session: keystoneauth1.session.Session object
    :returns: Authenticated swiftclient
    :rtype: swiftclient.Client object
    """
    return swiftclient.Connection(session=session)


def get_octavia_session_client(session, service_type='load-balancer',
                               interface='internal'):
    """Return octavia client authenticated by keystone session.

    :param session: Keystone session object
    :type session: keystoneauth1.session.Session object
    :param service_type: Service type to look for in catalog
    :type service_type: str
    :param interface: Interface to look for in catalog
    :type interface: str
    :returns: Authenticated octaviaclient
    :rtype: octaviaclient.OctaviaAPI object
    """
    keystone_client = get_keystone_session_client(session)
    lbaas_service = keystone_client.services.list(type=service_type)
    for service in lbaas_service:
        lbaas_endpoint = keystone_client.endpoints.list(service=service,
                                                        interface='internal')
        for endpoint in lbaas_endpoint:
            break
    return octaviaclient.OctaviaAPI(session=session,
                                    service_type=service_type,
                                    endpoint=endpoint.url)


def get_cinder_session_client(session, version=2):
    """Return cinderclient authenticated by keystone session.

    :param session: Keystone session object
    :type session: keystoneauth1.session.Session object
    :param version: Cinder API version
    :type version: int
    :returns: Authenticated cinderclient
    :rtype: cinderclient.Client object
    """
    return cinderclient.Client(session=session, version=version)


def get_masakari_session_client(session, interface='internal',
                                region_name='RegionOne'):
    """Return masakari client authenticated by keystone session.

    :param session: Keystone session object
    :type session: keystoneauth1.session.Session object
    :param interface: Interface to look for in catalog
    :type interface: str
    :param region_name: Region name to use in catalogue lookup
    :type region_name: str
    :returns: Authenticated masakari client
    :rtype: openstack.instance_ha.v1._proxy.Proxy
    """
    conn = connection.Connection(session=session,
                                 interface=interface,
                                 region_name=region_name)
    return conn.instance_ha


def get_keystone_scope():
    """Return Keystone scope based on OpenStack release of the overcloud.

    :returns: String keystone scope
    :rtype: string
    """
    os_version = get_current_os_versions("keystone")["keystone"]
    # Keystone policy.json shipped the charm with liberty requires a domain
    # scoped token. Bug #1649106
    if os_version == "liberty":
        scope = "DOMAIN"
    else:
        scope = "PROJECT"
    return scope


def get_keystone_session(opentackrc_creds, scope='PROJECT', verify=None):
    """Return keystone session.

    :param openrc_creds: Openstack RC credentials
    :type openrc_creds: dict
    :param verify: Control TLS certificate verification behaviour
    :type verify: any (True  - use system certs,
                       False - do not verify,
                       None  - defer to requests library to find certs,
                       str   - path to a CA cert bundle)
    :param scope: Authentication scope: PROJECT or DOMAIN
    :type scope: string
    :returns: Keystone session object
    :rtype: keystoneauth1.session.Session object
    """
    keystone_creds = get_ks_creds(opentackrc_creds, scope=scope)
    if opentackrc_creds.get('API_VERSION', 2) == 2:
        auth = v2.Password(**keystone_creds)
    else:
        auth = v3.Password(**keystone_creds)
    return session.Session(auth=auth, verify=verify)


def get_overcloud_keystone_session(verify=None):
    """Return Over cloud keystone session.

    :param verify: Control TLS certificate verification behaviour
    :type verify: any
    :returns keystone_session: keystoneauth1.session.Session object
    :rtype: keystoneauth1.session.Session
    """
    return get_keystone_session(get_overcloud_auth(),
                                scope=get_keystone_scope(),
                                verify=verify)


def get_undercloud_keystone_session(verify=None):
    """Return Under cloud keystone session.

    :param verify: Control TLS certificate verification behaviour
    :type verify: any
    :returns keystone_session: keystoneauth1.session.Session object
    :rtype: keystoneauth1.session.Session
    """
    return get_keystone_session(get_undercloud_auth(),
                                verify=verify)


def get_keystone_session_client(session, client_api_version=3):
    """Return keystoneclient authenticated by keystone session.

    :param session: Keystone session object
    :type session: keystoneauth1.session.Session object
    :param client_api_version: Whether you want a v2 or v3 Keystone Client
    :type client_api_version: int
    :returns: Authenticated keystoneclient
    :rtype: keystoneclient.v3.Client object
    """
    if client_api_version == 2:
        return keystoneclient_v2.Client(session=session)
    else:
        return keystoneclient_v3.Client(session=session)


def get_keystone_client(opentackrc_creds, verify=None):
    """Return authenticated keystoneclient and set auth_ref for service_catalog.

    :param openrc_creds: Openstack RC credentials
    :type openrc_creds: dict
    :param verify: Control TLS certificate verification behaviour
    :type verify: any
    :returns: Authenticated keystoneclient
    :rtype: keystoneclient.v3.Client object
    """
    session = get_keystone_session(opentackrc_creds, verify=verify)
    client = get_keystone_session_client(session)
    keystone_creds = get_ks_creds(opentackrc_creds)
    if opentackrc_creds.get('API_VERSION', 2) == 2:
        auth = v2.Password(**keystone_creds)
    else:
        auth = v3.Password(**keystone_creds)
    # This populates the client.service_catalog
    client.auth_ref = auth.get_access(session)
    return client


def get_project_id(ks_client, project_name, api_version=2, domain_name=None):
    """Return project ID.

    :param ks_client: Authenticated keystoneclient
    :type ks_client: keystoneclient.v3.Client object
    :param project_name: Name of the project
    :type project_name: string
    :param api_version: API version number
    :type api_version: int
    :param domain_name: Name of the domain
    :type domain_name: string or None
    :returns: Project ID
    :rtype: string or None
    """
    domain_id = None
    if domain_name:
        domain_id = ks_client.domains.list(name=domain_name)[0].id
    all_projects = ks_client.projects.list(domain=domain_id)
    for p in all_projects:
        if p._info['name'] == project_name:
            return p._info['id']
    return None


# Neutron Helpers
def get_gateway_uuids():
    """Return machine uuids for neutron-gateway(s).

    :returns: List of uuids
    :rtype: list
    """
    return juju_utils.get_machine_uuids_for_application('neutron-gateway')


def get_ovs_uuids():
    """Return machine uuids for neutron-openvswitch(s).

    :returns: List of uuids
    :rtype: list
    """
    return (juju_utils
            .get_machine_uuids_for_application('neutron-openvswitch'))


BRIDGE_MAPPINGS = 'bridge-mappings'
NEW_STYLE_NETWORKING = 'physnet1:br-ex'


def deprecated_external_networking(dvr_mode=False):
    """Determine whether deprecated external network mode is in use.

    :param dvr_mode: Using DVR mode or not
    :type dvr_mode: boolean
    :returns: True or False
    :rtype: boolean
    """
    bridge_mappings = None
    if dvr_mode:
        bridge_mappings = get_application_config_option('neutron-openvswitch',
                                                        BRIDGE_MAPPINGS)
    else:
        bridge_mappings = get_application_config_option('neutron-gateway',
                                                        BRIDGE_MAPPINGS)

    if bridge_mappings == NEW_STYLE_NETWORKING:
        return False
    return True


def get_net_uuid(neutron_client, net_name):
    """Determine whether deprecated external network mode is in use.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param net_name: Network name
    :type net_name: string
    :returns: Network ID
    :rtype: string
    """
    network = neutron_client.list_networks(name=net_name)['networks'][0]
    return network['id']


def get_admin_net(neutron_client):
    """Return admin netowrk.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :returns: Admin network object
    :rtype: dict
    """
    for net in neutron_client.list_networks()['networks']:
        if net['name'].endswith('_admin_net'):
            return net


def configure_gateway_ext_port(novaclient, neutronclient,
                               dvr_mode=None, net_id=None):
    """Configure the neturong-gateway external port.

    :param novaclient: Authenticated novaclient
    :type novaclient: novaclient.Client object
    :param neutronclient: Authenticated neutronclient
    :type neutronclient: neutronclient.Client object
    :param dvr_mode: Using DVR mode or not
    :type dvr_mode: boolean
    :param net_id: Network ID
    :type net_id: string
    """
    if dvr_mode:
        uuids = get_ovs_uuids()
    else:
        uuids = get_gateway_uuids()

    deprecated_extnet_mode = deprecated_external_networking(dvr_mode)

    config_key = 'data-port'
    if deprecated_extnet_mode:
        config_key = 'ext-port'

    if not net_id:
        net_id = get_admin_net(neutronclient)['id']

    for uuid in uuids:
        server = novaclient.servers.get(uuid)
        ext_port_name = "{}_ext-port".format(server.name)
        for port in neutronclient.list_ports(device_id=server.id)['ports']:
            if port['name'] == ext_port_name:
                logging.warning('Neutron Gateway already has additional port')
                break
        else:
            logging.info('Attaching additional port to instance, '
                         'connected to net id: {}'.format(net_id))
            body_value = {
                "port": {
                    "admin_state_up": True,
                    "name": ext_port_name,
                    "network_id": net_id,
                    "port_security_enabled": False,
                }
            }
            port = neutronclient.create_port(body=body_value)
            server.interface_attach(port_id=port['port']['id'],
                                    net_id=None, fixed_ip=None)
    ext_br_macs = []
    for port in neutronclient.list_ports(network_id=net_id)['ports']:
        if 'ext-port' in port['name']:
            if deprecated_extnet_mode:
                ext_br_macs.append(port['mac_address'])
            else:
                ext_br_macs.append('br-ex:{}'.format(port['mac_address']))
    ext_br_macs.sort()
    ext_br_macs_str = ' '.join(ext_br_macs)
    if dvr_mode:
        application_name = 'neutron-openvswitch'
    else:
        application_name = 'neutron-gateway'

    if ext_br_macs:
        logging.info('Setting {} on {} external port to {}'.format(
            config_key, application_name, ext_br_macs_str))
        current_data_port = get_application_config_option(application_name,
                                                          config_key)
        if current_data_port == ext_br_macs_str:
            logging.info('Config already set to value')
            return
        model.set_application_config(
            application_name,
            configuration={config_key: ext_br_macs_str})
        juju_wait.wait(wait_for_workload=True)


def create_project_network(neutron_client, project_id, net_name='private',
                           shared=False, network_type='gre', domain=None):
    """Create the project network.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param project_id: Project ID
    :type project_id: string
    :param net_name: Network name
    :type net_name: string
    :param shared: The network should be shared between projects
    :type shared: boolean
    :param net_type: Network type: GRE, VXLAN, local, VLAN
    :type net_type: string
    :param domain_name: Name of the domain
    :type domain_name: string or None
    :returns: Network object
    :rtype: dict
    """
    networks = neutron_client.list_networks(name=net_name)
    if len(networks['networks']) == 0:
        logging.info('Creating network: %s',
                     net_name)
        network_msg = {
            'network': {
                'name': net_name,
                'shared': shared,
                'tenant_id': project_id,
            }
        }
        if network_type == 'vxlan':
            network_msg['network']['provider:segmentation_id'] = 1233
            network_msg['network']['provider:network_type'] = network_type
        network = neutron_client.create_network(network_msg)['network']
    else:
        logging.warning('Network %s already exists.', net_name)
        network = networks['networks'][0]
    return network


def create_external_network(neutron_client, project_id, dvr_mode,
                            net_name='ext_net'):
    """Create the external network.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param project_id: Project ID
    :type project_id: string
    :param dvr_mode: Using DVR mode or not
    :type dvr_mode: boolean
    :param net_name: Network name
    :type net_name: string
    :returns: Network object
    :rtype: dict
    """
    networks = neutron_client.list_networks(name=net_name)
    if len(networks['networks']) == 0:
        logging.info('Configuring external network')
        network_msg = {
            'name': net_name,
            'router:external': True,
            'tenant_id': project_id,
            'provider:physical_network': 'physnet1',
            'provider:network_type': 'flat',
        }

        logging.info('Creating new external network definition: %s',
                     net_name)
        network = neutron_client.create_network(
            {'network': network_msg})['network']
        logging.info('New external network created: %s', network['id'])
    else:
        logging.warning('Network %s already exists.', net_name)
        network = networks['networks'][0]
    return network


def create_project_subnet(neutron_client, project_id, network, cidr, dhcp=True,
                          subnet_name='private_subnet', domain=None,
                          subnetpool=None, ip_version=4, prefix_len=24):
    """Create the project subnet.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param project_id: Project ID
    :type project_id: string
    :param network: Network object
    :type network: dict
    :param cidr: Network CIDR
    :type cidr: string
    :param dhcp: Run DHCP on this subnet
    :type dhcp: boolean
    :param subnet_name: Subnet name
    :type subnet_name: string
    :param domain_name: Name of the domain
    :type domain_name: string or None
    :param subnet_pool: Subnetpool object
    :type subnet_pool: dict or None
    :param ip_version: IP version: 4 or 6
    :type ip_version: int
    :param prefix_len: Prefix lenghths of subnets derived from subnet pools
    :type prefix_len: int
    :returns: Subnet object
    :rtype: dict
    """
    # Create subnet
    subnets = neutron_client.list_subnets(name=subnet_name)
    if len(subnets['subnets']) == 0:
        logging.info('Creating subnet')
        subnet_msg = {
            'subnet': {
                'name': subnet_name,
                'network_id': network['id'],
                'enable_dhcp': dhcp,
                'ip_version': ip_version,
                'tenant_id': project_id
            }
        }
        if subnetpool:
            subnet_msg['subnet']['subnetpool_id'] = subnetpool['id']
            subnet_msg['subnet']['prefixlen'] = prefix_len
        else:
            subnet_msg['subnet']['cidr'] = cidr
        subnet = neutron_client.create_subnet(subnet_msg)['subnet']
    else:
        logging.warning('Subnet %s already exists.', subnet_name)
        subnet = subnets['subnets'][0]
    return subnet


def create_external_subnet(neutron_client, project_id, network,
                           default_gateway=None, cidr=None,
                           start_floating_ip=None, end_floating_ip=None,
                           subnet_name='ext_net_subnet'):
    """Create the external subnet.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param project_id: Project ID
    :type project_id: string
    :param network: Network object
    :type network: dict
    :param default_gateway: Deafault gateway IP address
    :type default_gateway: string
    :param cidr: Network CIDR
    :type cidr: string
    :param start_floating_ip: Start of floating IP range: IP address
    :type start_floating_ip: string or None
    :param end_floating_ip: End of floating IP range: IP address
    :type end_floating_ip: string or None
    :param subnet_name: Subnet name
    :type subnet_name: string
    :returns: Subnet object
    :rtype: dict
    """
    subnets = neutron_client.list_subnets(name=subnet_name)
    if len(subnets['subnets']) == 0:
        subnet_msg = {
            'name': subnet_name,
            'network_id': network['id'],
            'enable_dhcp': False,
            'ip_version': 4,
            'tenant_id': project_id
        }

        if default_gateway:
            subnet_msg['gateway_ip'] = default_gateway
        if cidr:
            subnet_msg['cidr'] = cidr
        if (start_floating_ip and end_floating_ip):
            allocation_pool = {
                'start': start_floating_ip,
                'end': end_floating_ip,
            }
            subnet_msg['allocation_pools'] = [allocation_pool]

        logging.info('Creating new subnet')
        subnet = neutron_client.create_subnet({'subnet': subnet_msg})['subnet']
        logging.info('New subnet created: %s', subnet['id'])
    else:
        logging.warning('Subnet %s already exists.', subnet_name)
        subnet = subnets['subnets'][0]
    return subnet


def update_subnet_dns(neutron_client, subnet, dns_servers):
    """Update subnet DNS servers.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param subnet: Subnet object
    :type subnet: dict
    :param dns_servers: Comma separted list of IP addresses
    :type project_id: string
    """
    msg = {
        'subnet': {
            'dns_nameservers': dns_servers.split(',')
        }
    }
    logging.info('Updating dns_nameservers (%s) for subnet',
                 dns_servers)
    neutron_client.update_subnet(subnet['id'], msg)


def create_provider_router(neutron_client, project_id):
    """Create the provider router.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param project_id: Project ID
    :type project_id: string
    :returns: Router object
    :rtype: dict
    """
    routers = neutron_client.list_routers(name='provider-router')
    if len(routers['routers']) == 0:
        logging.info('Creating provider router for external network access')
        router_info = {
            'router': {
                'name': 'provider-router',
                'tenant_id': project_id
            }
        }
        router = neutron_client.create_router(router_info)['router']
        logging.info('New router created: %s', (router['id']))
    else:
        logging.warning('Router provider-router already exists.')
        router = routers['routers'][0]
    return router


def plug_extnet_into_router(neutron_client, router, network):
    """Add external interface to virtual router.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param router: Router object
    :type router: dict
    :param network: Network object
    :type network: dict
    """
    ports = neutron_client.list_ports(device_owner='network:router_gateway',
                                      network_id=network['id'])
    if len(ports['ports']) == 0:
        logging.info('Plugging router into ext_net')
        router = neutron_client.add_gateway_router(
            router=router['id'],
            body={'network_id': network['id']})
        logging.info('Router connected')
    else:
        logging.warning('Router already connected')


def plug_subnet_into_router(neutron_client, router, network, subnet):
    """Add subnet interface to virtual router.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param router: Router object
    :type router: dict
    :param network: Network object
    :type network: dict
    :param subnet: Subnet object
    :type subnet: dict
    """
    routers = neutron_client.list_routers(name=router)
    if len(routers['routers']) == 0:
        logging.error('Unable to locate provider router %s', router)
        sys.exit(1)
    else:
        # Check to see if subnet already plugged into router
        ports = neutron_client.list_ports(
            device_owner='network:router_interface',
            network_id=network['id'])
        if len(ports['ports']) == 0:
            logging.info('Adding interface from subnet to %s' % (router))
            router = routers['routers'][0]
            neutron_client.add_interface_router(router['id'],
                                                {'subnet_id': subnet['id']})
        else:
            logging.warning('Router already connected to subnet')


def create_address_scope(neutron_client, project_id, name, ip_version=4):
    """Create address scope.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param project_id: Project ID
    :type project_id: string
    :param name: Address scope name
    :type name: string
    :param ip_version: IP version: 4 or 6
    :type ip_version: int
    :returns: Address scope object
    :rtype: dict
    """
    address_scopes = neutron_client.list_address_scopes(name=name)
    if len(address_scopes['address_scopes']) == 0:
        logging.info('Creating {} address scope'.format(name))
        address_scope_info = {
            'address_scope': {
                'name': name,
                'shared': True,
                'ip_version': ip_version,
                'tenant_id': project_id,
            }
        }
        address_scope = neutron_client.create_address_scope(
            address_scope_info)['address_scope']
        logging.info('New address scope created: %s', (address_scope['id']))
    else:
        logging.warning('Address scope {} already exists.'.format(name))
        address_scope = address_scopes['address_scopes'][0]
    return address_scope


def create_subnetpool(neutron_client, project_id, name, subnetpool_prefix,
                      address_scope, shared=True):
    """Create subnet pool.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param project_id: Project ID
    :type project_id: string
    :param name: Subnet pool name
    :type name: string
    :param subnetpool_prefix: CIDR network
    :type subnetpool_prefix: string
    :param address_scope: Address scope object
    :type address_scope: dict
    :param shared: The subnet pool should be shared between projects
    :type shared: boolean
    :returns: Subnetpool object
    :rtype: dict
    """
    subnetpools = neutron_client.list_subnetpools(name=name)
    if len(subnetpools['subnetpools']) == 0:
        logging.info('Creating subnetpool: %s',
                     name)
        subnetpool_msg = {
            'subnetpool': {
                'name': name,
                'shared': shared,
                'tenant_id': project_id,
                'prefixes': [subnetpool_prefix],
                'address_scope_id': address_scope['id'],
            }
        }
        subnetpool = neutron_client.create_subnetpool(
            subnetpool_msg)['subnetpool']
    else:
        logging.warning('Network %s already exists.', name)
        subnetpool = subnetpools['subnetpools'][0]
    return subnetpool


def create_bgp_speaker(neutron_client, local_as=12345, ip_version=4,
                       name='bgp-speaker'):
    """Create BGP speaker.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param local_as: Autonomous system number of the OpenStack cloud
    :type local_as: int
    :param remote_as: Autonomous system number of the BGP peer
    :type local_as: int
    :param name: BGP speaker name
    :type name: string
    :returns: BGP speaker object
    :rtype: dict
    """
    bgp_speakers = neutron_client.list_bgp_speakers(name=name)
    if len(bgp_speakers['bgp_speakers']) == 0:
        logging.info('Creating BGP Speaker')
        bgp_speaker_msg = {
            'bgp_speaker': {
                'name': name,
                'local_as': local_as,
                'ip_version': ip_version,
            }
        }
        bgp_speaker = neutron_client.create_bgp_speaker(
            bgp_speaker_msg)['bgp_speaker']
    else:
        logging.warning('BGP Speaker %s already exists.', name)
        bgp_speaker = bgp_speakers['bgp_speakers'][0]
    return bgp_speaker


def add_network_to_bgp_speaker(neutron_client, bgp_speaker, network_name):
    """Advertise network on BGP Speaker.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param bpg_speaker: BGP speaker object
    :type bgp_speaker: dict
    :param network_name: Name of network to advertise
    :type network_name: string
    """
    network_id = get_net_uuid(neutron_client, network_name)
    # There is no direct way to determine which networks have already
    # been advertised. For example list_route_advertised_from_bgp_speaker shows
    # ext_net as FIP /32s.
    # Handle the expected exception if the route is already advertised
    try:
        logging.info('Advertising {} network on BGP Speaker {}'
                     .format(network_name, bgp_speaker['name']))
        neutron_client.add_network_to_bgp_speaker(bgp_speaker['id'],
                                                  {'network_id': network_id})
    except neutronexceptions.InternalServerError:
        logging.warning('{} network already advertised.'.format(network_name))


def create_bgp_peer(neutron_client, peer_application_name='quagga',
                    remote_as=10000, auth_type='none'):
    """Create BGP peer.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param peer_application_name: Application name of the BGP peer
    :type peer_application_name: string
    :param remote_as: Autonomous system number of the BGP peer
    :type local_as: int
    :param auth_type: BGP authentication type
    :type auth_type: string or None
    :returns: BGP peer object
    :rtype: dict
    """
    peer_unit = model.get_units(peer_application_name)[0]
    peer_ip = peer_unit.public_address
    bgp_peers = neutron_client.list_bgp_peers(name=peer_application_name)
    if len(bgp_peers['bgp_peers']) == 0:
        logging.info('Creating BGP Peer')
        bgp_peer_msg = {
            'bgp_peer': {
                'name': peer_application_name,
                'peer_ip': peer_ip,
                'remote_as': remote_as,
                'auth_type': auth_type,
            }
        }
        bgp_peer = neutron_client.create_bgp_peer(bgp_peer_msg)['bgp_peer']
    else:
        logging.warning('BGP Peer %s already exists.', peer_ip)
        bgp_peer = bgp_peers['bgp_peers'][0]
    return bgp_peer


def add_peer_to_bgp_speaker(neutron_client, bgp_speaker, bgp_peer):
    """Add BGP peer relationship to BGP speaker.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param bpg_speaker: BGP speaker object
    :type bgp_speaker: dict
    :param bpg_peer: BGP peer object
    :type bgp_peer: dict
    """
    # Handle the expected exception if the peer is already on the
    # speaker
    try:
        logging.info('Adding peer {} on BGP Speaker {}'
                     .format(bgp_peer['name'], bgp_speaker['name']))
        neutron_client.add_peer_to_bgp_speaker(bgp_speaker['id'],
                                               {'bgp_peer_id': bgp_peer['id']})
    except neutronexceptions.Conflict:
        logging.warning('{} peer already on BGP speaker.'
                        .format(bgp_peer['name']))


def add_neutron_secgroup_rules(neutron_client, project_id):
    """Add neutron security group rules.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param project_id: Project ID
    :type project_id: string
    """
    secgroup = None
    for group in neutron_client.list_security_groups().get('security_groups'):
        if (group.get('name') == 'default' and
            (group.get('project_id') == project_id or
                (group.get('tenant_id') == project_id))):
            secgroup = group
    if not secgroup:
        raise Exception("Failed to find default security group")
    # Using presence of a 22 rule to indicate whether secgroup rules
    # have been added
    port_rules = [rule['port_range_min'] for rule in
                  secgroup.get('security_group_rules')]
    protocol_rules = [rule['protocol'] for rule in
                      secgroup.get('security_group_rules')]
    if 22 in port_rules:
        logging.warn('Security group rules for ssh already added')
    else:
        logging.info('Adding ssh security group rule')
        neutron_client.create_security_group_rule(
            {'security_group_rule':
                {'security_group_id': secgroup.get('id'),
                 'protocol': 'tcp',
                 'port_range_min': 22,
                 'port_range_max': 22,
                 'direction': 'ingress',
                 }
             })

    if 'icmp' in protocol_rules:
        logging.warn('Security group rules for ping already added')
    else:
        logging.info('Adding ping security group rule')
        neutron_client.create_security_group_rule(
            {'security_group_rule':
                {'security_group_id': secgroup.get('id'),
                 'protocol': 'icmp',
                 'direction': 'ingress',
                 }
             })


def create_port(neutron_client, name, network_name):
    """Create port on network.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param name: Port name
    :type name: string
    :param network_name: Network name the port is on
    :type network_name: string
    :returns: Port object
    :rtype: dict
    """
    ports = neutron_client.list_ports(name=name)
    if len(ports['ports']) == 0:
        logging.info('Creating port: {}'.format(name))
        network_id = get_net_uuid(neutron_client, network_name)
        port_msg = {
            'port': {
                'name': name,
                'network_id': network_id,
            }
        }
        port = neutron_client.create_port(port_msg)['port']
    else:
        logging.debug('Port {} already exists.'.format(name))
        port = ports['ports'][0]

    return port


def create_floating_ip(neutron_client, network_name, port=None):
    """Create floating IP on network and optionally associate to a port.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param network_name: Name of external netowrk for FIPs
    :type network_name: string
    :param port: Port object
    :type port: dict
    :returns: Floating IP object
    :rtype: dict
    """
    floatingips = neutron_client.list_floatingips()
    if len(floatingips['floatingips']) > 0:
        if port:
            for floatingip in floatingips['floatingips']:
                if floatingip.get('port_id') == port['id']:
                    logging.debug('Floating IP with port, {}, already'
                                  'exists.'.format(port['name']))
                    return floatingip
        logging.warning('A floating IP already exists but ports do not match '
                        'Potentially creating more than one.')

    logging.info('Creating floatingip')
    network_id = get_net_uuid(neutron_client, network_name)
    floatingip_msg = {
        'floatingip': {
            'floating_network_id': network_id,
        }
    }
    if port:
        floatingip_msg['floatingip']['port_id'] = port['id']
    floatingip = neutron_client.create_floatingip(
        floatingip_msg)['floatingip']
    return floatingip


# Codename and package versions
def get_swift_codename(version):
    """Determine OpenStack codename that corresponds to swift version.

    :param version: Version of Swift
    :type version: string
    :returns: Codename for swift
    :rtype: string
    """
    codenames = [k for k, v in six.iteritems(SWIFT_CODENAMES) if version in v]
    return codenames[0]


def get_os_code_info(package, pkg_version):
    """Determine OpenStack codename that corresponds to package version.

    :param package: Package name
    :type package: string
    :param pkg_version: Package version
    :type pkg_version: string
    :returns: Codename for package
    :rtype: string
    """
    # {'code_num': entry, 'code_name': OPENSTACK_CODENAMES[entry]}
    # Remove epoch if it exists
    if ':' in pkg_version:
        pkg_version = pkg_version.split(':')[1:][0]
    if 'swift' in package:
        # Fully x.y.z match for swift versions
        match = re.match('^(\d+)\.(\d+)\.(\d+)', pkg_version)
    else:
        # x.y match only for 20XX.X
        # and ignore patch level for other packages
        match = re.match('^(\d+)\.(\d+)', pkg_version)

    if match:
        vers = match.group(0)
    # Generate a major version number for newer semantic
    # versions of openstack projects
    major_vers = vers.split('.')[0]
    if (package in PACKAGE_CODENAMES and
            major_vers in PACKAGE_CODENAMES[package]):
        return PACKAGE_CODENAMES[package][major_vers]
    else:
        # < Liberty co-ordinated project versions
        if 'swift' in package:
            return get_swift_codename(vers)
        else:
            return OPENSTACK_CODENAMES[vers]


def get_current_os_versions(deployed_applications):
    """Determine OpenStack codename of deployed applications.

    :param deployed_applications: List of deployed applications
    :type deployed_applications: list
    :returns: List of aplication to codenames dictionaries
    :rtype: list
    """
    versions = {}
    for application in UPGRADE_SERVICES:
        if application['name'] not in deployed_applications:
            continue

        version = generic_utils.get_pkg_version(application['name'],
                                                application['type']['pkg'])
        versions[application['name']] = (
            get_os_code_info(application['type']['pkg'], version))
    return versions


def get_application_config_keys(application):
    """Return application configuration keys.

    :param application: Name of application
    :type application: string
    :returns: List of aplication configuration keys
    :rtype: list
    """
    application_config = model.get_application_config(application)
    return list(application_config.keys())


def get_current_os_release_pair(application='keystone'):
    """Return OpenStack Release pair name.

    :param application: Name of application
    :type application: string
    :returns: Name of the OpenStack release pair
    :rtype: str
    :raises: exceptions.ApplicationNotFound
    :raises: exceptions.SeriesNotFound
    :raises: exceptions.OSVersionNotFound
    """
    machines = juju_utils.get_machines_for_application(application)
    if len(machines) >= 1:
        machine = machines[0]
    else:
        raise exceptions.ApplicationNotFound(application)

    series = juju_utils.get_machine_series(machine)
    if not series:
        raise exceptions.SeriesNotFound()

    os_version = get_current_os_versions([application]).get(application)
    if not os_version:
        raise exceptions.OSVersionNotFound()

    return '{}_{}'.format(series, os_version)


def get_os_release(release_pair=None):
    """Return index of release in OPENSTACK_RELEASES_PAIRS.

    :returns: Index of the release
    :rtype: int
    :raises: exceptions.ReleasePairNotFound
    """
    if release_pair is None:
        release_pair = get_current_os_release_pair()
    try:
        index = OPENSTACK_RELEASES_PAIRS.index(release_pair)
    except ValueError:
        msg = 'Release pair: {} not found in {}'.format(
            release_pair,
            OPENSTACK_RELEASES_PAIRS
        )
        raise exceptions.ReleasePairNotFound(msg)
    return index


def get_application_config_option(application, option):
    """Return application configuration.

    :param application: Name of application
    :type application: string
    :param option: Specific configuration option
    :type option: string
    :returns: Value of configuration option
    :rtype: Configuration option value type
    """
    application_config = model.get_application_config(application)
    try:
        return application_config.get(option).get('value')
    except AttributeError:
        return None


def get_undercloud_auth():
    """Get undercloud OpenStack authentication settings from environment.

    :returns: Dictionary of authentication settings
    :rtype: dict
    """
    os_auth_url = os.environ.get('OS_AUTH_URL')
    if os_auth_url:
        api_version = os_auth_url.split('/')[-1].replace('v', '')
    else:
        logging.error('Missing OS authentication setting: OS_AUTH_URL')
        raise exceptions.MissingOSAthenticationException(
            'One or more OpenStack authetication variables could '
            'be found in the environment. Please export the OS_* '
            'settings into the environment.')

    logging.info('AUTH_URL: {}, api_ver: {}'.format(os_auth_url, api_version))

    if api_version == '2.0':
        # V2
        logging.info('Using keystone API V2 for undercloud auth')
        auth_settings = {
            'OS_AUTH_URL': os.environ.get('OS_AUTH_URL'),
            'OS_TENANT_NAME': os.environ.get('OS_TENANT_NAME'),
            'OS_USERNAME': os.environ.get('OS_USERNAME'),
            'OS_PASSWORD': os.environ.get('OS_PASSWORD'),
            'OS_REGION_NAME': os.environ.get('OS_REGION_NAME'),
            'API_VERSION': 2,
        }
    elif api_version >= '3':
        # V3 or later
        logging.info('Using keystone API V3 (or later) for undercloud auth')
        domain = os.environ.get('OS_DOMAIN_NAME')
        auth_settings = {
            'OS_AUTH_URL': os.environ.get('OS_AUTH_URL'),
            'OS_USERNAME': os.environ.get('OS_USERNAME'),
            'OS_PASSWORD': os.environ.get('OS_PASSWORD'),
            'OS_REGION_NAME': os.environ.get('OS_REGION_NAME'),
            'API_VERSION': 3,
        }
        if domain:
            auth_settings['OS_DOMAIN_NAME': 'admin_domain'] = domain
        else:
            auth_settings['OS_USER_DOMAIN_NAME'] = (
                os.environ.get('OS_USER_DOMAIN_NAME'))
            auth_settings['OS_PROJECT_NAME'] = (
                os.environ.get('OS_PROJECT_NAME'))
            auth_settings['OS_PROJECT_DOMAIN_NAME'] = (
                os.environ.get('OS_PROJECT_DOMAIN_NAME'))
            os_project_id = os.environ.get('OS_PROJECT_ID')
            if os_project_id is not None:
                auth_settings['OS_PROJECT_ID'] = os_project_id

    # Validate settings
    for key, settings in list(auth_settings.items()):
        if settings is None:
            logging.error('Missing OS authentication setting: {}'
                          ''.format(key))
            raise exceptions.MissingOSAthenticationException(
                'One or more OpenStack authetication variables could '
                'be found in the environment. Please export the OS_* '
                'settings into the environment.')

    return auth_settings


# Openstack Client helpers
def get_keystone_ip():
    """Return the IP address to use when communicating with keystone api.

    :returns: IP address
    :rtype: str
    """
    if get_application_config_option('keystone', 'vip'):
        return get_application_config_option('keystone', 'vip')
    unit = model.get_units('keystone')[0]
    return unit.public_address


def get_keystone_api_version():
    """Return the keystone api version.

    :returns: Keystone's api version
    :rtype: int
    """
    os_version = get_current_os_versions('keystone')['keystone']
    api_version = get_application_config_option('keystone',
                                                'preferred-api-version')
    if os_version >= 'queens':
        api_version = 3
    elif api_version is None:
        api_version = 2

    return int(api_version)


def get_overcloud_auth(address=None):
    """Get overcloud OpenStack authentication from the environment.

    :returns: Dictionary of authentication settings
    :rtype: dict
    """
    tls_rid = model.get_relation_id('keystone', 'vault',
                                    remote_interface_name='certificates')
    ssl_config = get_application_config_option('keystone', 'ssl_cert')
    if tls_rid or ssl_config:
        transport = 'https'
        port = 35357
    else:
        transport = 'http'
        port = 5000

    if not address:
        address = get_keystone_ip()

    password = juju_utils.leader_get('keystone', 'admin_passwd')

    if get_keystone_api_version() == 2:
        # V2 Explicitly, or None when charm does not possess the config key
        logging.info('Using keystone API V2 for overcloud auth')
        auth_settings = {
            'OS_AUTH_URL': '%s://%s:%i/v2.0' % (transport, address, port),
            'OS_TENANT_NAME': 'admin',
            'OS_USERNAME': 'admin',
            'OS_PASSWORD': password,
            'OS_REGION_NAME': 'RegionOne',
            'API_VERSION': 2,
        }
    else:
        # V3 or later
        logging.info('Using keystone API V3 (or later) for overcloud auth')
        auth_settings = {
            'OS_AUTH_URL': '%s://%s:%i/v3' % (transport, address, port),
            'OS_USERNAME': 'admin',
            'OS_PASSWORD': password,
            'OS_REGION_NAME': 'RegionOne',
            'OS_DOMAIN_NAME': 'admin_domain',
            'OS_USER_DOMAIN_NAME': 'admin_domain',
            'OS_PROJECT_NAME': 'admin',
            'OS_PROJECT_DOMAIN_NAME': 'admin_domain',
            'API_VERSION': 3,
        }
    return auth_settings


def get_urllib_opener():
    """Create a urllib opener taking into account proxy settings.

    Using urllib.request.urlopen will automatically handle proxies so none
    of this function is needed except we are currently specifying proxies
    via AMULET_HTTP_PROXY rather than http_proxy so a ProxyHandler is needed
    explicitly stating the proxies.

    :returns: An opener which opens URLs via BaseHandlers chained together
    :rtype: urllib.request.OpenerDirector
    """
    http_proxy = os.getenv('AMULET_HTTP_PROXY')
    logging.debug('AMULET_HTTP_PROXY: {}'.format(http_proxy))

    if http_proxy:
        handler = urllib.request.ProxyHandler({'http': http_proxy})
    else:
        handler = urllib.request.HTTPHandler()
    return urllib.request.build_opener(handler)


def get_images_by_name(glance, image_name):
    """Get all glance image objects with the given name.

    :param glance: Authenticated glanceclient
    :type glance: glanceclient.Client
    :param image_name: Name of image
    :type image_name: str

    :returns: List of glance images
    :rtype: [glanceclient.v2.image, ...]
    """
    return [i for i in glance.images.list() if image_name == i.name]


def find_cirros_image(arch):
    """Return the url for the latest cirros image for the given architecture.

    :param arch: aarch64, arm, i386, amd64, x86_64 etc
    :type arch: str
    :returns: URL for latest cirros image
    :rtype: str
    """
    opener = get_urllib_opener()
    f = opener.open(CIRROS_RELEASE_URL)
    version = f.read().strip().decode()
    cirros_img = 'cirros-{}-{}-disk.img'.format(version, arch)
    return '{}/{}/{}'.format(CIRROS_IMAGE_URL, version, cirros_img)


def find_ubuntu_image(release, arch):
    """Return url for image."""
    return UBUNTU_IMAGE_URLS[release].format(release=release, arch=arch)


def download_image(image_url, target_file):
    """Download the image from the given url to the specified file.

    :param image_url: URL to download image from
    :type image_url: str
    :param target_file: Local file to savee image to
    :type target_file: str
    """
    opener = get_urllib_opener()
    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(image_url, target_file)


@tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, max=60),
                reraise=True, stop=tenacity.stop_after_attempt(8))
def resource_reaches_status(resource, resource_id,
                            expected_status='available',
                            msg='resource'):
    """Wait for an openstack resources status to reach an expected status.

       Wait for an openstack resources status to reach an expected status
       within a specified time. Useful to confirm that nova instances, cinder
       vols, snapshots, glance images, heat stacks and other resources
       eventually reach the expected status.

    :param resource: pointer to os resource type, ex: heat_client.stacks
    :type resource: str
    :param resource_id: unique id for the openstack resource
    :type resource_id: str
    :param expected_status: status to expect resource to reach
    :type expected_status: str
    :param msg: text to identify purpose in logging
    :type msy: str
    :raises: AssertionError
    """
    resource_status = resource.get(resource_id).status
    logging.info(resource_status)
    assert resource_status == expected_status, (
        "Resource in {} state, waiting for {}" .format(resource_status,
                                                       expected_status,))


@tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, max=60),
                reraise=True, stop=tenacity.stop_after_attempt(2))
def resource_removed(resource, resource_id, msg="resource"):
    """Wait for an openstack resource to no longer be present.

    :param resource: pointer to os resource type, ex: heat_client.stacks
    :type resource: str
    :param resource_id: unique id for the openstack resource
    :type resource_id: str
    :param msg: text to identify purpose in logging
    :type msy: str
    :raises: AssertionError
    """
    matching = [r for r in resource.list() if r.id == resource_id]
    logging.debug("Resource {} still present".format(resource_id))
    assert len(matching) == 0, "Resource {} still present".format(resource_id)


def delete_resource(resource, resource_id, msg="resource"):
    """Delete an openstack resource.

    Delete an openstack resource, such as one instance, keypair,
    image, volume, stack, etc., and confirm deletion within max wait time.

    :param resource: pointer to os resource type, ex:glance_client.images
    :type resource: str
    :param resource_id: unique name or id for the openstack resource
    :type resource_id: str
    :param msg: text to identify purpose in logging
    :type msg: str
    """
    logging.debug('Deleting OpenStack resource '
                  '{} ({})'.format(resource_id, msg))
    resource.delete(resource_id)
    resource_removed(resource, resource_id, msg)


def delete_image(glance, img_id):
    """Delete the given image from glance.

    :param glance: Authenticated glanceclient
    :type glance: glanceclient.Client
    :param img_id: unique name or id for the openstack resource
    :type img_id: str
    """
    delete_resource(glance.images, img_id, msg="glance image")


def upload_image_to_glance(glance, local_path, image_name, disk_format='qcow2',
                           visibility='public', container_format='bare'):
    """Upload the given image to glance and apply the given label.

    :param glance: Authenticated glanceclient
    :type glance: glanceclient.Client
    :param local_path: Path to local image
    :type local_path: str
    :param image_name: The label to give the image in glance
    :type image_name: str
    :param disk_format: The of the underlying disk image.
    :type disk_format: str
    :param visibility: Who can access image
    :type visibility: str (public, private, shared or community)
    :param container_format: Whether the virtual machine image is in a file
                             format that also contains metadata about the
                             actual virtual machine.
    :type container_format: str
    :returns: glance image pointer
    :rtype: glanceclient.common.utils.RequestIdProxy
    """
    # Create glance image
    image = glance.images.create(
        name=image_name,
        disk_format=disk_format,
        visibility=visibility,
        container_format=container_format)
    glance.images.upload(image.id, open(local_path, 'rb'))

    resource_reaches_status(
        glance.images,
        image.id,
        expected_status='active',
        msg='Image status wait')

    return image


def create_image(glance, image_url, image_name, image_cache_dir=None, tags=[]):
    """Download the image and upload it to glance.

    Download an image from image_url and upload it to glance labelling
    the image with image_url, validate and return a resource pointer.

    :param glance: Authenticated glanceclient
    :type glance: glanceclient.Client
    :param image_url: URL to download image from
    :type image_url: str
    :param image_name: display name for new image
    :type image_name: str
    :param image_cache_dir: Directory to store image in before uploading. If it
        is not passed, or is None, then a tmp directory is used.
    :type image_cache_dir: Option[str, None]
    :param tags: Tags to add to image
    :type tags: list of str
    :returns: glance image pointer
    :rtype: glanceclient.common.utils.RequestIdProxy
    """
    if image_cache_dir is None:
        image_cache_dir = tempfile.gettempdir()

    logging.debug('Creating glance cirros image '
                  '({})...'.format(image_name))

    img_name = os.path.basename(urllib.parse.urlparse(image_url).path)
    local_path = os.path.join(image_cache_dir, img_name)

    if not os.path.exists(local_path):
        download_image(image_url, local_path)

    image = upload_image_to_glance(glance, local_path, image_name)
    for tag in tags:
        result = glance.image_tags.update(image.id, tag)
        logging.debug(
            'applying tag to image: glance.image_tags.update({}, {}) = {}'
            .format(image.id, tags, result))
    return image


def create_ssh_key(nova_client, keypair_name, replace=False):
    """Create ssh key.

    :param nova_client: Authenticated nova client
    :type nova_client: novaclient.v2.client.Client
    :param keypair_name: Label to apply to keypair in Openstack.
    :type keypair_name: str
    :param replace: Whether to replace the existing keypair if it already
                    exists.
    :type replace: str
    :returns: The keypair
    :rtype: nova.objects.keypair
    """
    existing_keys = nova_client.keypairs.findall(name=keypair_name)
    if existing_keys:
        if replace:
            logging.info('Deleting key(s) {}'.format(keypair_name))
            for key in existing_keys:
                nova_client.keypairs.delete(key)
        else:
            return existing_keys[0]
    logging.info('Creating key %s' % (keypair_name))
    return nova_client.keypairs.create(name=keypair_name)


def get_private_key_file(keypair_name):
    """Location of the file containing the private key with the given label.

    :param keypair_name: Label of keypair in Openstack.
    :type keypair_name: str
    :returns: Path to file containing key
    :rtype: str
    """
    return 'tests/id_rsa_{}'.format(keypair_name)


def write_private_key(keypair_name, key):
    """Store supplied private key in file.

    :param keypair_name: Label of keypair in Openstack.
    :type keypair_name: str
    :param key: PEM Encoded Private Key
    :type key: str
    """
    with open(get_private_key_file(keypair_name), 'w') as key_file:
        key_file.write(key)


def get_private_key(keypair_name):
    """Return private key.

    :param keypair_name: Label of keypair in Openstack.
    :type keypair_name: str
    :returns: PEM Encoded Private Key
    :rtype: str
    """
    key_file = get_private_key_file(keypair_name)
    if not os.path.isfile(key_file):
        return None
    with open(key_file, 'r') as key_file:
        key = key_file.read()
    return key


def get_public_key(nova_client, keypair_name):
    """Return public key from Openstack.

    :param nova_client: Authenticated nova client
    :type nova_client: novaclient.v2.client.Client
    :param keypair_name: Label of keypair in Openstack.
    :type keypair_name: str
    :returns: OpenSSH Encoded Public Key
    :rtype: str or None
    """
    keys = nova_client.keypairs.findall(name=keypair_name)
    if keys:
        return keys[0].public_key
    else:
        return None


def valid_key_exists(nova_client, keypair_name):
    """Check if a valid public/private keypair exists for keypair_name.

    :param nova_client: Authenticated nova client
    :type nova_client: novaclient.v2.client.Client
    :param keypair_name: Label of keypair in Openstack.
    :type keypair_name: str
    """
    pub_key = get_public_key(nova_client, keypair_name)
    priv_key = get_private_key(keypair_name)
    if not all([pub_key, priv_key]):
        return False
    return cert.is_keys_valid(pub_key, priv_key)


def get_ports_from_device_id(neutron_client, device_id):
    """Return the ports associated with a given device.

    :param neutron_client: Authenticated neutronclient
    :type neutron_client: neutronclient.Client object
    :param device_id: The id of the device to look for
    :type device_id: str
    :returns: List of port objects
    :rtype: []
    """
    ports = []
    for _port in neutron_client.list_ports().get('ports'):
        if device_id in _port.get('device_id'):
            ports.append(_port)
    return ports


@tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, max=60),
                reraise=True, stop=tenacity.stop_after_attempt(8))
def cloud_init_complete(nova_client, vm_id, bootstring):
    """Wait for cloud init to complete on the given vm.

    If cloud init does not complete in the alloted time then
    exceptions.CloudInitIncomplete is raised.

    :param nova_client: Authenticated nova client
    :type nova_client: novaclient.v2.client.Client
    :param vm_id,: The id of the server to monitor.
    :type vm_id: str (uuid)
    :param bootstring: The string to look for in the console output that will
                       indicate cloud init is complete.
    :type bootstring: str
    :raises: exceptions.CloudInitIncomplete
    """
    instance = nova_client.servers.find(id=vm_id)
    console_log = instance.get_console_output()
    if bootstring not in console_log:
        raise exceptions.CloudInitIncomplete()


@tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, max=60),
                reraise=True, stop=tenacity.stop_after_attempt(8))
def ping_response(ip):
    """Wait for ping to respond on the given IP.

    :param ip: IP address to ping
    :type ip: str
    :raises: subprocess.CalledProcessError
    """
    cmd = ['ping', '-c', '1', '-W', '1', ip]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL)


def ssh_test(username, ip, vm_name, password=None, privkey=None):
    """SSH to given ip using supplied credentials.

    :param username: Username to connect with
    :type username: str
    :param ip: IP address to ssh to.
    :type ip: str
    :param vm_name: Name of VM.
    :type vm_name: str
    :param password: Password to authenticate with. If supplied it is used
                     rather than privkey.
    :type password: str
    :param privkey: Private key to authenticate with. If a password is
                    supplied it is used rather than the private key.
    :type privkey: str
    :raises: exceptions.SSHFailed
    """
    logging.info('Attempting to ssh to %s(%s)' % (vm_name, ip))
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if password:
        ssh.connect(ip, username=username, password=password)
    else:
        key = paramiko.RSAKey.from_private_key(io.StringIO(privkey))
        ssh.connect(ip, username=username, password='', pkey=key)
    stdin, stdout, stderr = ssh.exec_command('uname -n')
    return_string = stdout.readlines()[0].strip()
    ssh.close()
    if return_string == vm_name:
        logging.info('SSH to %s(%s) succesfull' % (vm_name, ip))
    else:
        logging.info('SSH to %s(%s) failed (%s != %s)' % (vm_name, ip,
                                                          return_string,
                                                          vm_name))
        raise exceptions.SSHFailed()


@tenacity.retry(wait=tenacity.wait_exponential(multiplier=0.01),
                reraise=True, stop=tenacity.stop_after_delay(60) |
                tenacity.stop_after_attempt(100))
def neutron_agent_appears(neutron_client, binary):
    """Wait for Neutron agent to appear and return agent_id.

    :param neutron_client: Neutron client
    :type neutron_client: Pointer to Neutron client object
    :param binary: Name of agent we want to appear
    :type binary: str
    :returns: result set from Neutron list_agents call
    :rtype: dict
    :raises: exceptions.NeutronAgentMissing
    """
    result = neutron_client.list_agents(binary=binary)
    for agent in result.get('agents', []):
        agent_id = agent.get('id', None)
        if agent_id:
            break
    else:
        raise exceptions.NeutronAgentMissing(
            'no agents for binary "{}"'.format(binary))
    return result


@tenacity.retry(wait=tenacity.wait_exponential(multiplier=0.01),
                reraise=True,
                stop=tenacity.stop_after_delay(60) |
                tenacity.stop_after_attempt(100))
def neutron_bgp_speaker_appears_on_agent(neutron_client, agent_id):
    """Wait for Neutron BGP speaker to appear on agent.

    :param neutron_client: Neutron client
    :type neutron_client: Pointer to Neutron client object
    :param agent_id: Neutron agent UUID
    :type agent_id: str
    :param speaker_id: Neutron BGP speaker UUID
    :type speaker_id: str
    :returns: result set from Neutron list_bgp_speaker_on_dragent call
    :rtype: dict
    :raises: exceptions.NeutronBGPSpeakerMissing
    """
    result = neutron_client.list_bgp_speaker_on_dragent(agent_id)
    for bgp_speaker in result.get('bgp_speakers', []):
        bgp_speaker_id = bgp_speaker.get('id', None)
        if bgp_speaker_id:
            break
    else:
        raise exceptions.NeutronBGPSpeakerMissing(
            'No BGP Speaker appeared on agent "{}"'
            ''.format(agent_id))
    return result


@tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, max=60),
                reraise=True, stop=tenacity.stop_after_attempt(80))
def wait_for_server_migration(nova_client, vm_name, original_hypervisor):
    """Wait for guest to migrate to a different hypervisor.

    :param nova_client: Authenticated nova client
    :type nova_client: novaclient.v2.client.Client
    :param vm_name: Name of guest to monitor
    :type vm_name: str
    :param original_hypervisor: Name of hypervisor that was hosting guest
                                prior to migration.
    :type original_hypervisor: str
    :raises: exceptions.NovaGuestMigrationFailed
    """
    server = nova_client.servers.find(name=vm_name)
    current_hypervisor = getattr(server, 'OS-EXT-SRV-ATTR:host')
    logging.info('{} is on {} in state {}'.format(
        vm_name,
        current_hypervisor,
        server.status))
    if original_hypervisor == current_hypervisor or server.status != 'ACTIVE':
        raise exceptions.NovaGuestMigrationFailed(
            'Migration of {} away from {} timed out or failed'.format(
                vm_name,
                original_hypervisor))
    else:
        logging.info('SUCCESS {} has migrated to {}'.format(
            vm_name,
            current_hypervisor))


def enable_all_nova_services(nova_client):
    """Enable all nova services.

    :param nova_client: Authenticated nova client
    :type nova_client: novaclient.v2.client.Client
    """
    for svc in nova_client.services.list():
        if svc.status == 'disabled':
            logging.info("Enabling {} on {}".format(svc.binary, svc.host))
            nova_client.services.enable(svc.host, svc.binary)


def get_hypervisor_for_guest(nova_client, guest_name):
    """Return the name of the hypervisor hosting a guest.

    :param nova_client: Authenticated nova client
    :type nova_client: novaclient.v2.client.Client
    :param vm_name: Name of guest to loohup
    :type vm_name: str
    """
    logging.info('Finding hosting hypervisor')
    server = nova_client.servers.find(name=guest_name)
    return getattr(server, 'OS-EXT-SRV-ATTR:host')
