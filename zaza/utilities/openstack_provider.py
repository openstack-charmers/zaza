# Copyright 2021 Canonical Ltd.
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

"""Functions to work with the openstack provider."""

import logging
import os
import tenacity

from keystoneauth1 import session
from keystoneauth1.identity import (
    v3,
    v2,
)
from novaclient import client as novaclient_client


USER_AGENT = 'zaza'


class MissingOSAthenticationException(Exception):
    """Exception when some data needed to authenticate is missing."""

    pass


def get_undercloud_keystone_session(verify=None):
    """Return Undercloud keystone session.

    :param verify: Control TLS certificate verification behaviour
    :type verify: any
    :returns keystone_session: keystoneauth1.session.Session object
    :rtype: keystoneauth1.session.Session
    """
    return get_keystone_session(get_undercloud_auth(),
                                verify=verify)


def get_keystone_session(openrc_creds, scope='PROJECT', verify=None):
    """Return keystone session.

    :param openrc_creds: OpenStack RC credentials
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
    keystone_creds = get_ks_creds(openrc_creds, scope=scope)
    if not verify and openrc_creds.get('OS_CACERT'):
        verify = openrc_creds['OS_CACERT']
    if openrc_creds.get('API_VERSION', 2) == 2:
        auth = v2.Password(**keystone_creds)
    else:
        auth = v3.Password(**keystone_creds)
    return session.Session(auth=auth, verify=verify,
                           user_agent=USER_AGENT)


def get_ks_creds(cloud_creds, scope='PROJECT'):
    """Return the credentials for authenticating against keystone.

    :param cloud_creds: OpenStack RC environment credentials
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
        # raise exceptions.MissingOSAthenticationException(
        raise MissingOSAthenticationException(
            'One or more OpenStack authentication variables could '
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
            auth_settings['OS_DOMAIN_NAME'] = domain
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

    _os_cacert = os.environ.get('OS_CACERT')
    if _os_cacert:
        auth_settings.update({'OS_CACERT': _os_cacert})

    # Validate settings
    for key, settings in list(auth_settings.items()):
        if settings is None:
            logging.error('Missing OS authentication setting: {}'
                          ''.format(key))
            # raise exceptions.MissingOSAthenticationException(
            raise MissingOSAthenticationException(
                'One or more OpenStack authentication variables could '
                'be found in the environment. Please export the OS_* '
                'settings into the environment.')

    return auth_settings


# Nova utilities
def get_nova_session_client(session, version=2):
    """Return novaclient authenticated by keystone session.

    :param session: Keystone session object
    :type session: keystoneauth1.session.Session object
    :param version: Version of client to request.
    :type version: float
    :returns: Authenticated novaclient
    :rtype: novaclient.Client object
    """
    return novaclient_client.Client(version, session=session,
                                    user_agent=USER_AGENT)


# Manage resources
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


def _resource_removed(resource, resource_id, msg="resource"):
    """Raise AssertError if a resource  is still longer present.

    :param resource: pointer to os resource type, ex: heat_client.stacks
    :type resource: str
    :param resource_id: unique id for the openstack resource
    :type resource_id: str
    :param msg: text to identify purpose in logging
    :type msg: str
    :raises: AssertionError
    """
    matching = [r for r in resource.list() if r.id == resource_id]
    logging.debug("{}: resource {} still present".format(msg, resource_id))
    assert len(matching) == 0


def resource_removed(resource,
                     resource_id,
                     msg='resource',
                     wait_exponential_multiplier=1,
                     wait_iteration_max_time=60,
                     stop_after_attempt=8):
    """Wait for an openstack resource to no longer be present.

    :param resource: pointer to os resource type, ex: heat_client.stacks
    :type resource: str
    :param resource_id: unique id for the openstack resource
    :type resource_id: str
    :param msg: text to identify purpose in logging
    :type msg: str
    :param wait_exponential_multiplier: Wait 2^x * wait_exponential_multiplier
                                        seconds between each retry
    :type wait_exponential_multiplier: int
    :param wait_iteration_max_time: Wait a max of wait_iteration_max_time
                                    between retries.
    :type wait_iteration_max_time: int
    :param stop_after_attempt: Stop after stop_after_attempt retires.
    :type stop_after_attempt: int
    :raises: AssertionError
    """
    retryer = tenacity.Retrying(
        wait=tenacity.wait_exponential(
            multiplier=wait_exponential_multiplier,
            max=wait_iteration_max_time),
        reraise=True,
        stop=tenacity.stop_after_attempt(stop_after_attempt))
    retryer(
        _resource_removed,
        resource,
        resource_id,
        msg)


def clean_up_instances(model_name, machines):
    """Clean up any remaining instances that might exist on OpenStack.

    This is used after delete to remove any instances that might exists after
    destroy model.  It does this by matching the model name to the OpenStack
    instance name, where the model_name is a part of the name.

    :param model_name: the model to destroy.
    :type model_name: str
    :param machines: the value of get_status(model_name)['machines'] prior to
        model deletion.
    :type machines: List[???]
    """
    machine_ids = [d.instance_id for d in machines.values()]
    session = get_undercloud_keystone_session()
    nova_client = get_nova_session_client(session)
    servers = [s for s in nova_client.servers.list() if s.id in machine_ids]
    if servers:
        logging.warning("Possibly having to clean-up {} servers after "
                        " destroy - due to async they may already be gone."
                        .format(len(servers)))
        for server in servers:
            try:
                delete_resource(
                    nova_client.servers,
                    server.id,
                    msg="server")
                logging.info("Removed server {} - id:{}"
                             .format(server.name, server.id))
            except novaclient_client.exceptions.NotFound:
                # Due to the async nature of all the bits of technology,
                # sometimes OpenStack will report the server existing despite
                # having removed it.  We get this exception if it was going
                # depite being in the list, so just ignore this error.
                logging.info("Server {} already removed - race due to async."
                             " id:{}" .format(server.name, server.id))


def report_machine_errors(model_name, machines):
    """Display information about machines in an error state.

    :param model_name: the model to destroy.
    :type model_name: str
    :param machines: List of machines in model.
    :type machines: List
    """
    machine_ids = {v.instance_id: k for k, v in machines.items()}
    session = get_undercloud_keystone_session()
    nova_client = get_nova_session_client(session)
    servers = [
        s for s in nova_client.servers.list() if s.id in machine_ids.keys()]
    for server in servers:
        logging.info("Juju Machine {}. Openstack ID {}. Status {}".format(
            machine_ids[server.id],
            server.id,
            server.status))
        if server.status == 'ACTIVE':
            logging.warning("Detected Error Status")
            logging.warning(dir(server))
            try:
                logging.warning(server.fault)
                logging.warning(dir(server.fault))
            except Exception:
                pass
