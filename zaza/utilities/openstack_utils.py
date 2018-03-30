#!/usr/bin/env python

from .os_versions import (
    OPENSTACK_CODENAMES,
    SWIFT_CODENAMES,
    PACKAGE_CODENAMES,
)

from keystoneclient.v2_0 import client as keystoneclient_v2
from keystoneclient.v3 import client as keystoneclient_v3
from keystoneauth1 import session
from keystoneauth1.identity import (
    v3,
    v2,
)
from novaclient import client as novaclient_client
from neutronclient.v2_0 import client as neutronclient
from neutronclient.common import exceptions as neutronexceptions

import logging
import os
import re
import six
import sys
import juju_wait

from zaza import model
from zaza.charm_lifecycle import utils as lifecycle_utils
from zaza.utilities import (
    exceptions,
    test_utils,
)

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


# Openstack Client helpers
def get_nova_creds(cloud_creds):
    auth = get_ks_creds(cloud_creds)
    if cloud_creds.get('OS_PROJECT_ID'):
        auth['project_id'] = cloud_creds.get('OS_PROJECT_ID')
    return auth


def get_ks_creds(cloud_creds, scope='PROJECT'):
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


def get_nova_client(novarc_creds, insecure=True):
    nova_creds = get_nova_creds(novarc_creds)
    nova_creds['insecure'] = insecure
    nova_creds['version'] = 2
    return novaclient_client.Client(**nova_creds)


def get_nova_session_client(session):
    return novaclient_client.Client(2, session=session)


def get_neutron_client(novarc_creds, insecure=True):
    neutron_creds = get_ks_creds(novarc_creds)
    neutron_creds['insecure'] = insecure
    return neutronclient.Client(**neutron_creds)


def get_neutron_session_client(session):
    return neutronclient.Client(session=session)


def get_keystone_session(novarc_creds, insecure=True, scope='PROJECT'):
    keystone_creds = get_ks_creds(novarc_creds, scope=scope)
    if novarc_creds.get('API_VERSION', 2) == 2:
        auth = v2.Password(**keystone_creds)
    else:
        auth = v3.Password(**keystone_creds)
    return session.Session(auth=auth, verify=not insecure)


def get_keystone_session_client(session):
    return keystoneclient_v3.Client(session=session)


def get_keystone_client(novarc_creds, insecure=True):
    keystone_creds = get_ks_creds(novarc_creds)
    if novarc_creds.get('API_VERSION', 2) == 2:
        auth = v2.Password(**keystone_creds)
        sess = session.Session(auth=auth, verify=True)
        client = keystoneclient_v2.Client(session=sess)
    else:
        auth = v3.Password(**keystone_creds)
        sess = get_keystone_session(novarc_creds, insecure)
        client = keystoneclient_v3.Client(session=sess)
    # This populates the client.service_catalog
    client.auth_ref = auth.get_access(sess)
    return client


def get_project_id(ks_client, project_name, api_version=2, domain_name=None):
    domain_id = None
    if domain_name:
        domain_id = ks_client.domains.list(name=domain_name)[0].id
    all_projects = ks_client.projects.list(domain=domain_id)
    for t in all_projects:
        if t._info['name'] == project_name:
            return t._info['id']
    return None


# Neutron Helpers
def get_gateway_uuids():
    return test_utils.get_machine_uuids_for_application('neutron-gateway')


def get_ovs_uuids():
    return test_utils.get_machine_uuids_for_application('neutron-openvswitch')


BRIDGE_MAPPINGS = 'bridge-mappings'
NEW_STYLE_NETWORKING = 'physnet1:br-ex'


def deprecated_external_networking(dvr_mode=False):
    '''Determine whether deprecated external network mode is in use'''
    bridge_mappings = None
    if dvr_mode:
        bridge_mappings = juju_get('neutron-openvswitch',
                                   BRIDGE_MAPPINGS)
    else:
        bridge_mappings = juju_get('neutron-gateway',
                                   BRIDGE_MAPPINGS)

    if bridge_mappings == NEW_STYLE_NETWORKING:
        return False
    return True


def get_net_uuid(neutron_client, net_name):
    network = neutron_client.list_networks(name=net_name)['networks'][0]
    return network['id']


def get_admin_net(neutron_client):
    for net in neutron_client.list_networks()['networks']:
        if net['name'].endswith('_admin_net'):
            return net


def configure_gateway_ext_port(novaclient, neutronclient,
                               dvr_mode=None, net_id=None):
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

    # XXX Trying to track down a failure with juju run neutron-gateway/0 in
    #     the post juju_set check. Try a sleep here to see if some network
    #     reconfigureing on the gateway is still in progress and that's
    #     causing the issue
    if ext_br_macs:
        logging.info('Setting {} on {} external port to {}'.format(
            config_key, application_name, ext_br_macs_str))
        current_data_port = juju_get(application_name, config_key)
        if current_data_port == ext_br_macs_str:
            logging.info('Config already set to value')
            return
        model.set_application_config(
            lifecycle_utils.get_juju_model(), application_name,
            configuration={config_key: ext_br_macs_str})
        juju_wait.wait(wait_for_workload=True)


def create_project_network(neutron_client, project_id, net_name='private',
                           shared=False, network_type='gre', domain=None):
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
    networks = neutron_client.list_networks(name=net_name)
    if len(networks['networks']) == 0:
        logging.info('Configuring external network')
        network_msg = {
            'name': net_name,
            'router:external': True,
            'tenant_id': project_id,
        }
        if not deprecated_external_networking(dvr_mode):
            network_msg['provider:physical_network'] = 'physnet1'
            network_msg['provider:network_type'] = 'flat'

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


def create_external_subnet(neutron_client, tenant_id, network,
                           default_gateway=None, cidr=None,
                           start_floating_ip=None, end_floating_ip=None,
                           subnet_name='ext_net_subnet'):
    subnets = neutron_client.list_subnets(name=subnet_name)
    if len(subnets['subnets']) == 0:
        subnet_msg = {
            'name': subnet_name,
            'network_id': network['id'],
            'enable_dhcp': False,
            'ip_version': 4,
            'tenant_id': tenant_id
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
    msg = {
        'subnet': {
            'dns_nameservers': dns_servers.split(',')
        }
    }
    logging.info('Updating dns_nameservers (%s) for subnet',
                 dns_servers)
    neutron_client.update_subnet(subnet['id'], msg)


def create_provider_router(neutron_client, tenant_id):
    routers = neutron_client.list_routers(name='provider-router')
    if len(routers['routers']) == 0:
        logging.info('Creating provider router for external network access')
        router_info = {
            'router': {
                'name': 'provider-router',
                'tenant_id': tenant_id
            }
        }
        router = neutron_client.create_router(router_info)['router']
        logging.info('New router created: %s', (router['id']))
    else:
        logging.warning('Router provider-router already exists.')
        router = routers['routers'][0]
    return router


def plug_extnet_into_router(neutron_client, router, network):
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
    """Create address scope

    :param ip_version: integer 4 or 6
    :param name: strint name for the address scope
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
                      address_scope, shared=True, domain=None):
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
    """Create BGP Speaker

    @param neutron_client: Instance of neutronclient.v2.Client
    @param local_as: int Local Autonomous System Number
    @returns dict BGP Speaker object
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
    """Advertise network on BGP Speaker

    @param neutron_client: Instance of neutronclient.v2.Client
    @param bgp_speaker: dict BGP Speaker object
    @param network_name: str Name of network to advertise
    @returns None
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
    """Create BGP Peer

    @param neutron_client: Instance of neutronclient.v2.Client
    @param peer_application_name: str Name of juju application to find peer IP
                                  Default: 'quagga'
    @param remote_as: int Remote Autonomous System Number
    @param auth_type: str BGP authentication type.
                      Default: 'none'
    @returns dict BGP Peer object
    """
    peer_unit = model.get_units(
        lifecycle_utils.get_juju_model(), peer_application_name)[0]
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
    """Setup BGP peering relationship with BGP Peer and BGP Speaker

    @param neutron_client: Instance of neutronclient.v2.Client
    @param bgp_speaker: dict BGP Speaker object
    @param bgp_peer: dict BGP Peer object
    @returns None
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


def get_swift_codename(version):
    '''Determine OpenStack codename that corresponds to swift version.'''
    codenames = [k for k, v in six.iteritems(SWIFT_CODENAMES) if version in v]
    return codenames[0]


def get_os_code_info(package, pkg_version):
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


def get_current_os_versions(deployed_services):
    versions = {}
    for service in UPGRADE_SERVICES:
        if service['name'] not in deployed_services:
            continue

        version = test_utils.get_pkg_version(service['name'],
                                             service['type']['pkg'])
        versions[service['name']] = get_os_code_info(service['type']['pkg'],
                                                     version)
    return versions


def get_lowest_os_version(current_versions):
    lowest_version = 'zebra'
    for svc in current_versions.keys():
        if current_versions[svc] < lowest_version:
            lowest_version = current_versions[svc]
    return lowest_version


def juju_get_config_keys(application):
    logging.warn("Deprecated function: juju_get_config_keys. Use "
                 "get_application_config_keys")
    return get_application_config_keys(application)


def get_application_config_keys(application):
    application_config = model.get_application_config(
        lifecycle_utils.get_juju_model(), application)
    return list(application_config.keys())


def juju_get(application, option):
    logging.warn("Deprecated function: juju_get. Use "
                 "get_application_config_option")
    return get_application_config_option(application, option)


def get_application_config_option(application, option):
    application_config = model.get_application_config(
        lifecycle_utils.get_juju_model(), application)
    try:
        return application_config.get(option).get('value')
    except AttributeError:
        return None


def get_undercloud_auth():
    """ Get the undercloud OpenStack authentication settings from the
    environment.

    @raises MissingOSAthenticationException if one or more settings are
            missing.
    @returns Dictionary of authentication settings
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
    if juju_get('keystone', 'vip'):
        return juju_get('keystone', 'vip')
    unit = model.get_units(
        lifecycle_utils.get_juju_model(), 'keystone')[0]
    return unit.public_address


def get_auth_url():
    logging.warn("Deprecated function: get_auth_url. Use get_keystone_ip")
    return get_keystone_ip()


def get_overcloud_auth():
    if juju_get('keystone', 'use-https').lower() == 'yes':
        transport = 'https'
        port = 35357
    else:
        transport = 'http'
        port = 5000
    address = get_auth_url()

    os_version = get_current_os_versions('keystone')['keystone']

    api_version = juju_get('keystone', 'preferred-api-version')
    if os_version >= 'queens':
        api_version = 3
    elif api_version is None:
        api_version = 2

    if api_version == 2:
        # V2 Explicitly, or None when charm does not possess the config key
        logging.info('Using keystone API V2 for overcloud auth')
        auth_settings = {
            'OS_AUTH_URL': '%s://%s:%i/v2.0' % (transport, address, port),
            'OS_TENANT_NAME': 'admin',
            'OS_USERNAME': 'admin',
            'OS_PASSWORD': 'openstack',
            'OS_REGION_NAME': 'RegionOne',
            'API_VERSION': 2,
        }
    else:
        # V3 or later
        logging.info('Using keystone API V3 (or later) for overcloud auth')
        auth_settings = {
            'OS_AUTH_URL': '%s://%s:%i/v3' % (transport, address, port),
            'OS_USERNAME': 'admin',
            'OS_PASSWORD': 'openstack',
            'OS_REGION_NAME': 'RegionOne',
            'OS_DOMAIN_NAME': 'admin_domain',
            'OS_USER_DOMAIN_NAME': 'admin_domain',
            'OS_PROJECT_NAME': 'admin',
            'OS_PROJECT_DOMAIN_NAME': 'admin_domain',
            'API_VERSION': 3,
        }
    return auth_settings
