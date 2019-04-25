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

"""Code for setting up keystone."""

import zaza.openstack.utilities.openstack as openstack_utils
from zaza.openstack.charm_tests.keystone import (
    BaseKeystoneTest,
    DEMO_TENANT,
    DEMO_DOMAIN,
    DEMO_PROJECT,
    DEMO_ADMIN_USER,
    DEMO_ADMIN_USER_PASSWORD,
    DEMO_USER,
    DEMO_PASSWORD,
)


def add_demo_user():
    """Add a demo user to the current deployment."""
    def _v2():
        keystone_session = openstack_utils.get_overcloud_keystone_session()
        keystone_client = openstack_utils.get_keystone_session_client(
            keystone_session, client_api_version=2)
        tenant = keystone_client.tenants.create(tenant_name=DEMO_TENANT,
                                                description='Demo Tenant',
                                                enabled=True)
        keystone_client.users.create(name=DEMO_USER,
                                     password=DEMO_PASSWORD,
                                     tenant_id=tenant.id)

    def _v3():
        keystone_session = openstack_utils.get_overcloud_keystone_session()
        keystone_client = openstack_utils.get_keystone_session_client(
            keystone_session)
        domain = keystone_client.domains.create(
            DEMO_DOMAIN,
            description='Demo Domain',
            enabled=True)
        project = keystone_client.projects.create(
            DEMO_PROJECT,
            domain,
            description='Demo Project',
            enabled=True)
        demo_user = keystone_client.users.create(
            DEMO_USER,
            domain=domain,
            project=project,
            password=DEMO_PASSWORD,
            email='demo@demo.com',
            description='Demo User',
            enabled=True)
        member_role = keystone_client.roles.find(name='Member')
        keystone_client.roles.grant(
            member_role,
            user=demo_user,
            project_domain=domain,
            project=project)
        demo_admin_user = keystone_client.users.create(
            DEMO_ADMIN_USER,
            domain=domain,
            project=project,
            password=DEMO_ADMIN_USER_PASSWORD,
            email='demo_admin@demo.com',
            description='Demo Admin User',
            enabled=True)
        admin_role = keystone_client.roles.find(name='Admin')
        keystone_client.roles.grant(
            admin_role,
            user=demo_admin_user,
            domain=domain)
        keystone_client.roles.grant(
            member_role,
            user=demo_admin_user,
            project_domain=domain,
            project=project)
        keystone_client.roles.grant(
            admin_role,
            user=demo_admin_user,
            project_domain=domain,
            project=project)

    if (openstack_utils.get_os_release() <
            openstack_utils.get_os_release('trusty_mitaka')):
        # create only V2 user
        _v2()
        return

    if (openstack_utils.get_os_release() >=
        openstack_utils.get_os_release('trusty_mitaka') and
        openstack_utils.get_os_release() <
            openstack_utils.get_os_release('xenial_queens')):
        # create V2 and V3 user
        _v2()

        _singleton = BaseKeystoneTest()
        _singleton.setUpClass()
        # Explicitly set application name in case setup is called by a charm
        # under test other than keystone.
        with _singleton.config_change(
                {'preferred-api-version': _singleton.default_api_version},
                {'preferred-api-version': '3'}, application_name="keystone"):
            _v3()
    else:
        # create only V3 user
        _v3()
