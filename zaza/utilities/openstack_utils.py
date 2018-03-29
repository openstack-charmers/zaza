#!/usr/bin/env python

from .os_versions import (
    OPENSTACK_CODENAMES,
    SWIFT_CODENAMES,
    PACKAGE_CODENAMES,
)

import swiftclient
import glanceclient
from aodhclient.v2 import client as aodh_client
from keystoneclient.v2_0 import client as keystoneclient_v2
from keystoneclient.v3 import client as keystoneclient_v3
from keystoneauth1 import session
from keystoneauth1.identity import (
    v3,
    v2,
)
from . import juju_utils as mojo_utils
from novaclient import client as novaclient_client
from neutronclient.v2_0 import client as neutronclient
from neutronclient.common import exceptions as neutronexceptions


import designateclient
import designateclient.client as designate_client
import designateclient.v1.domains as des_domains
import designateclient.v1.records as des_records
import designateclient.exceptions as des_exceptions

import logging
import re
import sys
import tempfile
import six
if six.PY3:
    from urllib.request import urlretrieve
else:
    from urllib import urlretrieve
import os
import time
import subprocess
import paramiko
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import dns.resolver

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


def get_swift_creds(cloud_creds):
    auth = {
        'user': cloud_creds['OS_USERNAME'],
        'key': cloud_creds['OS_PASSWORD'],
        'authurl': cloud_creds['OS_AUTH_URL'],
        'tenant_name': cloud_creds['OS_TENANT_NAME'],
        'auth_version': '2.0',
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


def get_aodh_session_client(session):
    return aodh_client.Client(session=session)


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


def get_swift_client(novarc_creds, insecure=True):
    swift_creds = get_swift_creds(novarc_creds)
    swift_creds['insecure'] = insecure
    return swiftclient.client.Connection(**swift_creds)


def get_swift_session_client(session):
    return swiftclient.client.Connection(session=session)


def get_designate_session_client(session, all_tenants=True,
                                 client_version=None):
    client_version = client_version or '2'
    if client_version == '1':
        client = designate_client.Client(
            version=client_version,
            session=session,
            all_tenants=all_tenants)
    else:
        client = designate_client.Client(
            version=client_version,
            session=session)
    return client


def get_glance_session_client(session):
    return glanceclient.Client('1', session=session)


def get_glance_client(novarc_creds, insecure=True):
    if novarc_creds.get('API_VERSION', 2) == 2:
        kc = get_keystone_client(novarc_creds)
        glance_ep_url = kc.service_catalog.url_for(service_type='image',
                                                   interface='publicURL')
    else:
        keystone_creds = get_ks_creds(novarc_creds, scope='PROJECT')
        kc = keystoneclient_v3.Client(**keystone_creds)
        glance_svc_id = kc.services.find(name='glance').id
        ep = kc.endpoints.find(service_id=glance_svc_id, interface='public')
        glance_ep_url = ep.url
    return glanceclient.Client('1', glance_ep_url, token=kc.auth_token,
                               insecure=insecure)


# Glance Helpers
def download_image(image, image_glance_name=None):
    logging.info('Downloading ' + image)
    tmp_dir = tempfile.mkdtemp(dir='/tmp')
    if not image_glance_name:
        image_glance_name = image.split('/')[-1]
    local_file = os.path.join(tmp_dir, image_glance_name)
    urlretrieve(image, local_file)
    return local_file


def upload_image(gclient, ifile, image_name, public, disk_format,
                 container_format):
    logging.info('Uploading %s to glance ' % (image_name))
    with open(ifile, 'rb') as fimage:
        gclient.images.create(
            name=image_name,
            is_public=public,
            disk_format=disk_format,
            container_format=container_format,
            data=fimage)


def get_images_list(gclient):
    return [image.name for image in gclient.images.list()]


# Keystone helpers
def tenant_create(kclient, tenants):
    current_tenants = [tenant.name for tenant in kclient.tenants.list()]
    for tenant in tenants:
        if tenant in current_tenants:
            logging.warning('Not creating tenant %s it already'
                            ' exists' % (tenant))
        else:
            logging.info('Creating tenant %s' % (tenant))
            kclient.tenants.create(tenant_name=tenant)


def project_create(kclient, projects, domain=None):
    domain_id = None
    for dom in kclient.domains.list():
        if dom.name == domain:
            domain_id = dom.id
    current_projects = []
    for project in kclient.projects.list():
        if not domain_id or project.domain_id == domain_id:
            current_projects.append(project.name)
    for project in projects:
        if project in current_projects:
            logging.warning('Not creating project %s it already'
                            ' exists' % (project))
        else:
            logging.info('Creating project %s' % (project))
            kclient.projects.create(project, domain_id)


def domain_create(kclient, domains):
    current_domains = [domain.name for domain in kclient.domains.list()]
    for dom in domains:
        if dom in current_domains:
            logging.warning('Not creating domain %s it already'
                            ' exists' % (dom))
        else:
            logging.info('Creating domain %s' % (dom))
            kclient.domains.create(dom)


def user_create_v2(kclient, users):
    current_users = [user.name for user in kclient.users.list()]
    for user in users:
        if user['username'] in current_users:
            logging.warning('Not creating user %s it already'
                            'exists' % (user['username']))
        else:
            logging.info('Creating user %s' % (user['username']))
            project_id = get_project_id(kclient, user['project'])
            kclient.users.create(name=user['username'],
                                 password=user['password'],
                                 email=user['email'],
                                 tenant_id=project_id)


def user_create_v3(kclient, users):
    current_users = [user.name for user in kclient.users.list()]
    for user in users:
        project = user.get('project') or user.get('tenant')
        if user['username'] in current_users:
            logging.warning('Not creating user %s it already'
                            'exists' % (user['username']))
        else:
            if user['scope'] == 'project':
                logging.info('Creating user %s' % (user['username']))
                project_id = get_project_id(kclient, project,
                                            api_version=3)
                kclient.users.create(name=user['username'],
                                     password=user['password'],
                                     email=user['email'],
                                     project_id=project_id)


def get_roles_for_user(kclient, user_id, tenant_id):
    roles = []
    ksuser_roles = kclient.roles.roles_for_user(user_id, tenant_id)
    for role in ksuser_roles:
        roles.append(role.id)
    return roles


def add_users_to_roles(kclient, users):
    for user_details in users:
        tenant_id = get_project_id(kclient, user_details['project'])
        for role_name in user_details['roles']:
            role = kclient.roles.find(name=role_name)
            user = kclient.users.find(name=user_details['username'])
            users_roles = get_roles_for_user(kclient, user, tenant_id)
            if role.id in users_roles:
                logging.warning('Not adding role %s to %s it already has '
                                'it' % (user_details['username'], role_name))
            else:
                logging.info('Adding %s to role %s for tenant'
                             '%s' % (user_details['username'], role_name,
                                     tenant_id))
                kclient.roles.add_user_role(user_details['username'], role,
                                            tenant_id)


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
    gateway_config = mojo_utils.get_juju_status('neutron-gateway')
    uuids = []
    for machine in gateway_config['machines']:
        uuids.append(gateway_config['machines'][machine]['instance-id'])
    return uuids


def get_ovs_uuids():
    gateway_config = mojo_utils.get_juju_status('neutron-openvswitch')
    uuids = []
    for machine in gateway_config['machines']:
        uuids.append(gateway_config['machines'][machine]['instance-id'])
    return uuids


BRIDGE_MAPPINGS = 'bridge-mappings'
NEW_STYLE_NETWORKING = 'physnet1:br-ex'


def deprecated_external_networking(dvr_mode=False):
    '''Determine whether deprecated external network mode is in use'''
    bridge_mappings = None
    if dvr_mode:
        bridge_mappings = mojo_utils.juju_get('neutron-openvswitch',
                                              BRIDGE_MAPPINGS)
    else:
        bridge_mappings = mojo_utils.juju_get('neutron-gateway',
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
        service_name = 'neutron-openvswitch'
    else:
        service_name = 'neutron-gateway'
    # XXX Trying to track down a failure with juju run neutron-gateway/0 in
    #     the post juju_set check. Try a sleep here to see if some network
    #     reconfigureing on the gateway is still in progress and that's
    #     causing the issue
    if ext_br_macs:
        logging.info('Setting {} on {} external port to {}'.format(
            config_key, service_name, ext_br_macs_str))
        current_data_port = mojo_utils.juju_get(service_name, config_key)
        if current_data_port == ext_br_macs_str:
            logging.info('Config already set to value')
            return
        mojo_utils.juju_set(
            service_name,
            '{}={}'.format(config_key,
                           ext_br_macs_str),
            wait=False
        )
        time.sleep(240)
        mojo_utils.juju_wait_finished()


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
    peer_unit = mojo_utils.get_juju_units(service=peer_application_name)[0]
    peer_ip = mojo_utils.get_juju_unit_ip(peer_unit)
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


# Nova Helpers
def create_keypair(nova_client, keypair_name):
    if nova_client.keypairs.findall(name=keypair_name):
        _oldkey = nova_client.keypairs.find(name=keypair_name)
        logging.info('Deleting key %s' % (keypair_name))
        nova_client.keypairs.delete(_oldkey)
    logging.info('Creating key %s' % (keypair_name))
    new_key = nova_client.keypairs.create(name=keypair_name)
    return new_key.private_key


def boot_instance(nova_client, neutron_client, image_name,
                  flavor_name, key_name):
    image = nova_client.glance.find_image(image_name)
    flavor = nova_client.flavors.find(name=flavor_name)
    net = neutron_client.find_resource("network", "private")
    nics = [{'net-id': net.get('id')}]
    # Obviously time may not produce a unique name
    vm_name = time.strftime("%Y%m%d%H%M%S")
    logging.info('Creating %s %s %s'
                 'instance %s' % (flavor_name, image_name, nics, vm_name))
    instance = nova_client.servers.create(name=vm_name,
                                          image=image,
                                          flavor=flavor,
                                          key_name=key_name,
                                          nics=nics)
    logging.info('Issued boot')
    return instance


def wait_for_active(nova_client, vm_name, wait_time):
    logging.info('Waiting %is for %s to reach ACTIVE '
                 'state' % (wait_time, vm_name))
    for counter in range(wait_time):
        instance = nova_client.servers.find(name=vm_name)
        if instance.status == 'ACTIVE':
            logging.info('%s is ACTIVE' % (vm_name))
            return True
        elif instance.status not in ('BUILD', 'SHUTOFF'):
            logging.error('instance %s in unknown '
                          'state %s' % (instance.name, instance.status))
            return False
        time.sleep(1)
    logging.error('instance %s failed to reach '
                  'active state in %is' % (instance.name, wait_time))
    return False


def wait_for_cloudinit(nova_client, vm_name, bootstring, wait_time):
    logging.info('Waiting %is for cloudinit on %s to '
                 'complete' % (wait_time, vm_name))
    instance = nova_client.servers.find(name=vm_name)
    for counter in range(wait_time):
        instance = nova_client.servers.find(name=vm_name)
        console_log = instance.get_console_output()
        if bootstring in console_log:
            logging.info('Cloudinit for %s is complete' % (vm_name))
            return True
        time.sleep(1)
    logging.error('cloudinit for instance %s failed '
                  'to complete in %is' % (instance.name, wait_time))
    return False


def wait_for_boot(nova_client, vm_name, bootstring, active_wait,
                  cloudinit_wait):
    logging.info('Waiting for boot')
    if not wait_for_active(nova_client, vm_name, active_wait):
        raise Exception('Error initialising %s' % vm_name)
    if not wait_for_cloudinit(nova_client, vm_name, bootstring,
                              cloudinit_wait):
        raise Exception('Cloudinit error %s' % vm_name)


def wait_for_ping(ip, wait_time):
    logging.info('Waiting for ping to %s' % (ip))
    for counter in range(wait_time):
        if ping(ip):
            logging.info('Ping %s success' % (ip))
            return True
        time.sleep(10)
    logging.error('Ping failed for %s' % (ip))
    return False


def assign_floating_ip(nova_client, neutron_client, vm_name):
    ext_net_id = None
    instance_port = None
    for network in neutron_client.list_networks().get('networks'):
        if 'ext_net' in network.get('name'):
            ext_net_id = network.get('id')
    instance = nova_client.servers.find(name=vm_name)
    for port in neutron_client.list_ports().get('ports'):
        if instance.id in port.get('device_id'):
            instance_port = port
    floating_ip = neutron_client.create_floatingip({'floatingip':
                                                    {'floating_network_id':
                                                     ext_net_id,
                                                     'port_id':
                                                     instance_port.get('id')}})
    ip = floating_ip.get('floatingip').get('floating_ip_address')
    logging.info('Assigning floating IP %s to %s' % (ip, vm_name))
    return ip


def add_secgroup_rules(nova_client):
    secgroup = nova_client.security_groups.find(name="default")
    # Using presence of a 22 rule to indicate whether secgroup rules
    # have been added
    port_rules = [rule['to_port'] for rule in secgroup.rules]
    if 22 in port_rules:
        logging.warn('Security group rules for ssh already added')
    else:
        logging.info('Adding ssh security group rule')
        nova_client.security_group_rules.create(secgroup.id,
                                                ip_protocol="tcp",
                                                from_port=22,
                                                to_port=22)
    if -1 in port_rules:
        logging.warn('Security group rules for ping already added')
    else:
        logging.info('Adding ping security group rule')
        nova_client.security_group_rules.create(secgroup.id,
                                                ip_protocol="icmp",
                                                from_port=-1,
                                                to_port=-1)


def add_neutron_secgroup_rules(neutron_client, project_id):
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


def ping(ip):
    # Use the system ping command with count of 1 and wait time of 1.
    ret = subprocess.call(['ping', '-c', '1', '-W', '1', ip],
                          stdout=open('/dev/null', 'w'),
                          stderr=open('/dev/null', 'w'))
    return ret == 0


def ssh_test(username, ip, vm_name, password=None, privkey=None):
    logging.info('Attempting to ssh to %s(%s)' % (vm_name, ip))
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if privkey:
        key = paramiko.RSAKey.from_private_key(StringIO(privkey))
        ssh.connect(ip, username=username, password='', pkey=key)
    else:
        ssh.connect(ip, username=username, password=password)
    stdin, stdout, stderr = ssh.exec_command('uname -n')
    return_string = stdout.readlines()[0].strip()
    ssh.close()
    if return_string == vm_name:
        logging.info('SSH to %s(%s) succesfull' % (vm_name, ip))
        return True
    else:
        logging.info('SSH to %s(%s) failed (%s != %s)' % (vm_name, ip,
                                                          return_string,
                                                          vm_name))
        return False


def boot_and_test(nova_client, neutron_client, image_name, flavor_name,
                  number, privkey, active_wait=180, cloudinit_wait=180,
                  ping_wait=180):
    image_config = mojo_utils.get_mojo_config('images.yaml')
    for counter in range(number):
        instance = boot_instance(nova_client,
                                 neutron_client,
                                 image_name=image_name,
                                 flavor_name=flavor_name,
                                 key_name='mojo')
        logging.info("Launched {}".format(instance))
        wait_for_boot(nova_client, instance.name,
                      image_config[image_name]['bootstring'], active_wait,
                      cloudinit_wait)
        ip = assign_floating_ip(nova_client, neutron_client, instance.name)
        wait_for_ping(ip, ping_wait)
        if not wait_for_ping(ip, ping_wait):
            raise Exception('Ping of %s failed' % (ip))
        ssh_test_args = {
            'username': image_config[image_name]['username'],
            'ip': ip,
            'vm_name': instance.name,
        }
        if image_config[image_name]['auth_type'] == 'password':
            ssh_test_args['password'] = image_config[image_name]['password']
        elif image_config[image_name]['auth_type'] == 'privkey':
            ssh_test_args['privkey'] = privkey
        if not ssh_test(**ssh_test_args):
            raise Exception('SSH failed to instance at %s' % (ip))


def check_guest_connectivity(nova_client, ping_wait=180):
    for guest in nova_client.servers.list():
        fip = nova_client.floating_ips.find(instance_id=guest.id).ip
        if not wait_for_ping(fip, ping_wait):
            raise Exception('Ping of %s failed' % (fip))


# Hacluster helper

def get_juju_leader(service):
    # XXX Juju status should report the leader but doesn't at the moment.
    # So, until it does run leader on the units
    for unit in mojo_utils.get_juju_units(service=service):
        leader_out = mojo_utils.remote_run(unit, 'is-leader')[0].strip()
        if leader_out == 'True':
            return unit


def delete_juju_leader(service, resource=None, method='juju'):
    mojo_utils.delete_unit(get_juju_leader(service), method=method)


def get_crm_leader(service, resource=None):
    if not resource:
        resource = 'res_.*_vip'
    leader = set()
    for unit in mojo_utils.get_juju_units(service=service):
        crm_out = mojo_utils.remote_run(unit, 'sudo crm status')[0]
        for line in crm_out.splitlines():
            line = line.lstrip()
            if re.match(resource, line):
                leader.add(line.split()[-1])
    if len(leader) != 1:
        raise Exception('Unexpected leader count: ' + str(len(leader)))
    return leader.pop().split('-')[-1]


def delete_crm_leader(service, resource=None, method='juju'):
    mach_no = get_crm_leader(service, resource)
    unit = mojo_utils.convert_machineno_to_unit(mach_no)
    mojo_utils.delete_unit(unit, method=method)

# OpenStack Version helpers

# XXX get_swift_codename and get_os_code_info are based on the functions with
# the same name in ~charm-helpers/charmhelpers/contrib/openstack/utils.py
# It'd be neat if we actually shared a common library.


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


def next_release(release):
    old_index = OPENSTACK_CODENAMES.values().index(release)
    new_index = old_index + 1
    return OPENSTACK_CODENAMES.items()[new_index]


def get_current_os_versions(deployed_services):
    versions = {}
    for service in UPGRADE_SERVICES:
        if service['name'] not in deployed_services:
            continue
        version = mojo_utils.get_pkg_version(service['name'],
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


def update_network_dns(neutron_client, network, domain_name):
    msg = {
        'network': {
            'dns_domain': domain_name,
        }
    }
    logging.info('Updating dns_domain for network {}'.format(network))
    neutron_client.update_network(network, msg)


def get_designate_server_id(client, server_name):
    server_id = None
    for server in client.servers.list():
        if server.name == server_name:
            server_id = server.id
            break
    return server_id


def get_designate_domain_id(client, domain_name):
    domain_id = None
    for domain in client.domains.list():
        if domain.name == domain_name:
            domain_id = domain.id
            break
    return domain_id


def get_designate_record_id(client, domain_id, record_name):
    record_id = None
    for record in client.records.list(domain_id):
        if record.name == record_name:
            record_id = record.id
            break
    return record_id


def get_designate_domain_object_v1(designate_client, domain_name):
    """Get the one and only domain matching the given domain_name, if none are
    found or multiple are found then raise an AssertionError. To access a list
    matching the domain name use get_designate_domain_objects.

    @param designate_client: designateclient.v1.Client Client to query
                                                       designate
    @param domain_name: str Name of domain to lookup
    @returns designateclient.v1.domains.Domain
    @raises AssertionError: if domain_name not found or multiple domains with
                            the same name.
    """
    dns_zone_id = get_designate_domain_objects_v1(designate_client,
                                                  domain_name=domain_name)
    assert len(dns_zone_id) == 1, "Found {} domains for {}".format(
        len(dns_zone_id),
        domain_name)
    return dns_zone_id[0]


def get_designate_domain_object_v2(designate_client, domain_name):
    """Get the one and only domain matching the given domain_name, if none are
    found or multiple are found then raise an AssertionError. To access a list
    matching the domain name use get_designate_domain_objects.

    @param designate_client: designateclient.v1.Client Client to query
                                                       designate
    @param domain_name: str Name of domain to lookup
    @returns designateclient.v1.domains.Domain
    @raises AssertionError: if domain_name not found or multiple domains with
                            the same name.
    """
    dns_zone_id = get_designate_zone_objects_v2(designate_client,
                                                domain_name=domain_name)
    msg = "Found {} domains for {}".format(
        len(dns_zone_id),
        domain_name)
    assert len(dns_zone_id) == 1, msg
    return dns_zone_id[0]


def get_designate_domain_objects_v1(designate_client, domain_name=None,
                                    domain_id=None):
    """Get all domains matching a given domain_name or domain_id

    @param designate_client: designateclient.v1.Client Client to query
                                                       designate
    @param domain_name: str Name of domain to lookup
    @param domain_id: str UUID of domain to lookup
    @returns [] List of designateclient.v1.domains.Domain objects matching
                domain_name or domain_id
    """
    all_domains = designate_client.domains.list()
    a = [d for d in all_domains if d.name == domain_name or d.id == domain_id]
    return a


def get_designate_zone_objects_v2(designate_client, domain_name=None,
                                  domain_id=None):
    """Get all domains matching a given domain_name or domain_id

    @param designate_client: designateclient.v1.Client Client to query
                                                       designate
    @param domain_name: str Name of domain to lookup
    @param domain_id: str UUID of domain to lookup
    @returns [] List of designateclient.v1.domains.Domain objects matching
                domain_name or domain_id
    """
    all_zones = designate_client.zones.list()
    a = [z for z in all_zones
         if z['name'] == domain_name or z['id'] == domain_id]
    return a


def get_designate_dns_records_v1(designate_client, domain_name, ip):
    """Look for records in designate that match the given ip

    @param designate_client: designateclient.v1.Client Client to query
                                                       designate
    @param domain_name: str Name of domain to lookup
    @returns [] List of designateclient.v1.records.Record objects with
                a matching IP address
    """
    dns_zone = get_designate_domain_object_v1(designate_client, domain_name)
    domain = designate_client.domains.get(dns_zone.id)
    return [r for r in designate_client.records.list(domain) if r.data == ip]


def get_designate_dns_records_v2(designate_client, domain_name, ip):
    """Look for records in designate that match the given ip

    @param designate_client: designateclient.v1.Client Client to query
                                                       designate
    @param domain_name: str Name of domain to lookup
    @returns [] List of designateclient.v1.records.Record objects with
                a matching IP address
    """
    dns_zone = get_designate_domain_object_v2(designate_client, domain_name)
    return [r for r in designate_client.recordsets.list(dns_zone['id'])
            if r['records'] == ip]


def get_designate_zone(designate_client, zone_name):
    zone = None
    zones = [z for z in designate_client.zones.list()
             if z['name'] == zone_name]
    assert len(zones) <= 1, "Multiple matching zones found"
    if zones:
        zone = zones[0]
    return zone


def create_designate_zone(designate_client, domain_name, email):
    return designate_client.zones.create(
        name=domain_name,
        email=email)


def create_designate_dns_domain(designate_client, domain_name, email,
                                recreate=True):
    """Create the given domain in designate

    @param designate_client: designateclient.v1.Client Client to query
                                                       designate
    @param domain_name: str Name of domain to lookup
    @param email: str Email address to associate with domain
    @param recreate: boolean Whether to delete any matching domains first.
    """
    if recreate:
        delete_designate_dns_domain(designate_client, domain_name)
        for i in range(1, 10):
            try:
                domain = des_domains.Domain(name=domain_name, email=email)
                dom_obj = designate_client.domains.create(domain)
            except des_exceptions.Conflict:
                print("Waiting for delete {}/10".format(i))
                time.sleep(10)
            else:
                break
        else:
            raise des_exceptions.Conflict
    else:
        domain = des_domains.Domain(name=domain_name, email=email)
        dom_obj = designate_client.domains.create(domain)
    return dom_obj


def create_designate_dns_record(designate_client, domain_id, name, rtype,
                                data):
    """Create the given record in designmate

    @param designate_client: designateclient.v1.Client Client to query
                                                       designate
    @param domain_id: str UUID of domain to create record in
    @param name: str DNS fqdn entry to be created
    @param rtype: str record type eg A, CNAME etc
    @param data: str data to be associated with record
    @returns designateclient.v1.records.Record
    """
    record = des_records.Record(name=name, type=rtype, data=data)
    return designate_client.records.create(domain_id, record)


def delete_designate_dns_domain(designate_client, domain_name):
    """Delete the domains matching the given domain_name

    @param designate_client: designateclient.v1.Client Client to query
                                                       designate
    @param domain_name: str Name of domain to lookup
    @raises AssertionError: if domain deletion fails
    """
    dns_zone_id = get_designate_domain_objects(designate_client, domain_name)
    old_doms = get_designate_domain_objects(designate_client, domain_name)
    for old_dom in old_doms:
        logging.info("Deleting old domain {}".format(old_dom.id))
        designate_client.domains.delete(old_dom.id)


def check_dns_record_exists(dns_server_ip, query_name, expected_ip,
                            retry_count=1):
    """Lookup a DNS record against the given dns server address

    @param dns_server_ip: str IP address to run query against
    @param query_name: str Record to lookup
    @param expected_ip: str IP address expected to be associated with record.
    @param retry_count: int Number of times to retry query. Useful if waiting
                            for record to propagate.
    @raises AssertionError: if record is not found or expected_ip is set and
                            does not match the IP associated with the record
    """
    my_resolver = dns.resolver.Resolver()
    my_resolver.nameservers = [dns_server_ip]
    for i in range(1, retry_count + 1):
        try:
            answers = my_resolver.query(query_name)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
            logging.info(
                'Attempt {}/{} to lookup {}@{} failed. Sleeping before '
                'retrying'.format(i, retry_count, query_name,
                                  dns_server_ip))
            time.sleep(5)
        else:
            break
    else:
        raise dns.resolver.NXDOMAIN
    assert len(answers) > 0
    if expected_ip:
        for rdata in answers:
            logging.info("Checking address returned by {} is correct".format(
                dns_server_ip))
            assert str(rdata) == expected_ip


def check_dns_entry(des_client, ip, domain, record_name, juju_status=None,
                    designate_api='2'):
    """Check that record for ip address is in designate and in bind if bind
       server is available.

    @param ip: str IP address to lookup
    @param domain: str domain to look for record in
    @param record_name: str record name
    @param juju_status: dict Current juju status
    """
    if not juju_status:
        juju_status = mojo_utils.get_juju_status()
    if designate_api == '1':
        check_dns_entry_in_designate_v1(des_client, ip, domain,
                                        record_name=record_name)
    else:
        check_dns_entry_in_designate_v2(des_client, [ip], domain,
                                        record_name=record_name)
    check_dns_entry_in_bind(ip, record_name, juju_status=juju_status)


def check_dns_entry_in_designate_v1(des_client, ip, domain, record_name=None):
    """Look for records in designate that match the given ip in the given
       domain

    @param designate_client: designateclient.v1.Client Client to query
                                                       designate
    @param ip: str IP address to lookup in designate
    @param domain: str Name of domain to lookup
    @param record_name: str Retrieved record should have this name
    @raises AssertionError: if no record is found or record_name is set and
                            does not match the name associated with the record
    """
    records = get_designate_dns_records_v1(des_client, domain, ip)
    assert records, "Record not found for {} in designate".format(ip)

    if record_name:
        recs = [r for r in records if r.name == record_name]
        assert recs, "No DNS entry name matches expected name {}".format(
            record_name)


def check_dns_entry_in_designate_v2(des_client, ip, domain, record_name=None):
    """Look for records in designate that match the given ip in the given
       domain

    @param designate_client: designateclient.v1.Client Client to query
                                                       designate
    @param ip: str IP address to lookup in designate
    @param domain: str Name of domain to lookup
    @param record_name: str Retrieved record should have this name
    @raises AssertionError: if no record is found or record_name is set and
                            does not match the name associated with the record
    """
    records = get_designate_dns_records_v2(des_client, domain, ip)
    assert records, "Record not found for {} in designate".format(ip)

    if record_name:
        recs = [r for r in records if r['name'] == record_name]
        assert recs, "No DNS entry name matches expected name {}".format(
            record_name)


def check_dns_entry_in_bind(ip, record_name, juju_status=None):
    """Check that record for ip address in bind if a bind
       server is available.

    @param ip: str IP address to lookup
    @param record_name: str record name
    @param juju_status: dict Current juju status
    """
    if not juju_status:
        juju_status = mojo_utils.get_juju_status()

    bind_units = mojo_utils.get_juju_units(
        service='designate-bind',
        juju_status=juju_status)

    for unit in bind_units:
        addr = mojo_utils.get_juju_unit_ip(unit, juju_status=juju_status)
        logging.info("Checking {} is {} against {} ({})".format(
            record_name,
            ip,
            unit,
            addr))
        check_dns_record_exists(addr, record_name, ip, retry_count=6)


def create_or_return_zone(client, name, email):
    try:
        zone = client.zones.create(
            name=name,
            email=email)
    except designateclient.exceptions.Conflict:
        logging.info('{} zone already exists.'.format(name))
        zones = [z for z in client.zones.list() if z['name'] == name]
        assert len(zones) == 1, "Wrong number of zones found {}".format(zones)
        zone = zones[0]
    return zone


def create_or_return_recordset(client, zone_id, sub_domain, record_type, data):
    try:
        rs = client.recordsets.create(
            zone_id,
            sub_domain,
            record_type,
            data)
    except designateclient.exceptions.Conflict:
        logging.info('{} record already exists.'.format(data))
        for r in client.recordsets.list(zone_id):
            if r['name'].split('.')[0] == sub_domain:
                rs = r
    return rs


# Aodh helpers
def get_alarm(aclient, alarm_name):
    for alarm in aclient.alarm.list():
        if alarm['name'] == alarm_name:
            return alarm
    return None


def delete_alarm(aclient, alarm_name):
    alarm = get_alarm(aclient, alarm_name)
    if alarm:
        aclient.alarm.delete(alarm['alarm_id'])


def get_alarm_state(aclient, alarm_id):
    alarm = aclient.alarm.get(alarm_id)
    return alarm['state']
