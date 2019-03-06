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

"""Encapsulate keystone testing."""
import collections
import json
import logging
import pprint

import keystoneauth1

import zaza.model
import zaza.utilities.exceptions as zaza_exceptions
import zaza.utilities.juju as juju_utils
import zaza.utilities.openstack as openstack_utils

import zaza.charm_tests.test_utils as test_utils
from zaza.charm_tests.keystone import (
    BaseKeystoneTest,
    DEMO_DOMAIN,
    DEMO_TENANT,
    DEMO_USER,
    DEMO_PASSWORD,
    DEMO_PROJECT,
    DEMO_ADMIN_USER,
    DEMO_ADMIN_USER_PASSWORD,
)


class CharmOperationTest(BaseKeystoneTest):
    """Charm operation tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running Keystone charm operation tests."""
        super(CharmOperationTest, cls).setUpClass()

    def test_001_vip_in_catalog(self):
        """Verify the VIP is in the identity catalog entry.

        This test should run early. It validates that if a VIP is set it is in
        the catalog entry for keystone.
        """
        vip = (zaza.model.get_application_config('keystone')
               .get('vip').get('value'))
        if not vip:
            # If the vip is not set skip this test.
            return
        endpoint_filter = {'service_type': 'identity',
                           'interface': 'public',
                           'region_name': 'RegionOne'}
        ep = self.admin_keystone_client.session.get_endpoint(**endpoint_filter)
        assert vip in ep, (
            "VIP: {} not found in catalog entry: {}".format(vip, ep))

    def test_pause_resume(self):
        """Run pause and resume tests.

        Pause service and check services are stopped, then resume and check
        they are started.
        """
        self.pause_resume(['apache2'])

    def test_key_distribution_and_rotation(self):
        """Verify key rotation.

        Note that we make the assumption that test bundle configure
        `token-expiration` to 60 and that it takes > 60s from deployment
        completes until we get to this test.
        """
        if (openstack_utils.get_os_release() <
                openstack_utils.get_os_release('xenial_ocata')):
            logging.info('skipping test < xenial_ocata')
            return

        with self.pause_resume(['apache2']):
            KEY_KEY_REPOSITORY = 'key_repository'
            CREDENTIAL_KEY_REPOSITORY = '/etc/keystone/credential-keys/'
            FERNET_KEY_REPOSITORY = '/etc/keystone/fernet-keys/'

            # get key repostiroy from leader storage
            key_repository = json.loads(juju_utils.leader_get(
                self.application_name, KEY_KEY_REPOSITORY))
            # sort keys so we can compare it to on-disk repositories
            key_repository = json.loads(json.dumps(
                key_repository, sort_keys=True),
                object_pairs_hook=collections.OrderedDict)
            logging.info('key_repository: "{}"'
                         .format(pprint.pformat(key_repository)))
            for repo in [CREDENTIAL_KEY_REPOSITORY, FERNET_KEY_REPOSITORY]:
                try:
                    for key_name, key in key_repository[repo].items():
                        if int(key_name) > 1:
                            # after initialization the repository contains the
                            # staging key (0) and the primary key (1).  After
                            # rotation the repository contains at least one key
                            # with higher index.
                            break
                    else:
                        # NOTE the charm should only rotate the fernet key
                        # repostiory and not rotate the credential key
                        # repository.
                        if repo == FERNET_KEY_REPOSITORY:
                            raise zaza_exceptions.KeystoneKeyRepositoryError(
                                'Keys in Fernet key repository has not been '
                                'rotated.')
                except KeyError:
                    raise zaza_exceptions.KeystoneKeyRepositoryError(
                        'Dict in leader setting "{}" does not contain key '
                        'repository "{}"'.format(KEY_KEY_REPOSITORY, repo))

            # get on-disk key repository from all units
            on_disk = {}
            units = zaza.model.get_units(self.application_name)
            for unit in units:
                on_disk[unit.entity_id] = {}
                for repo in [CREDENTIAL_KEY_REPOSITORY, FERNET_KEY_REPOSITORY]:
                    on_disk[unit.entity_id][repo] = {}
                    result = zaza.model.run_on_unit(
                        unit.entity_id, 'sudo ls -1 {}'.format(repo))
                    for key_name in result.get('Stdout').split():
                        result = zaza.model.run_on_unit(
                            unit.entity_id,
                            'sudo cat {}/{}'.format(repo, key_name))
                        on_disk[unit.entity_id][repo][key_name] = result.get(
                            'Stdout')
            # sort keys so we can compare it to leader storage repositories
            on_disk = json.loads(
                json.dumps(on_disk, sort_keys=True),
                object_pairs_hook=collections.OrderedDict)
            logging.info('on_disk: "{}"'.format(pprint.pformat(on_disk)))

            for unit in units:
                unit_repo = on_disk[unit.entity_id]
                lead_repo = key_repository
                if unit_repo != lead_repo:
                    raise zaza_exceptions.KeystoneKeyRepositoryError(
                        'expect: "{}" actual({}): "{}"'
                        .format(pprint.pformat(lead_repo), unit.entity_id,
                                pprint.pformat(unit_repo)))
                logging.info('"{}" == "{}"'
                             .format(pprint.pformat(unit_repo),
                                     pprint.pformat(lead_repo)))


class AuthenticationAuthorizationTest(BaseKeystoneTest):
    """Keystone authentication and authorization tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running Keystone aa-tests."""
        super(AuthenticationAuthorizationTest, cls).setUpClass()

    def test_admin_project_scoped_access(self):
        """Verify cloud admin access using project scoped token.

        `admin` user in `admin_domain` should be able to access API methods
        guarded by `rule:cloud_admin` policy using a token scoped to `admin`
        project in `admin_domain`.

        We implement a policy that enables domain segregation and
        administration delegation [0].  It is important to understand that this
        differs from the default policy.

        In the initial implementation it was necessary to switch between using
        a `domain` scoped and `project` scoped token to successfully manage a
        cloud, but since the introduction of `is_admin` functionality in
        Keystone [1][2][3] and our subsequent adoption of it in Keystone charm
        [4], this is no longer necessary.

        This test here to validate this behaviour.

        0: https://github.com/openstack/keystone/commit/c7a5c6c
        1: https://github.com/openstack/keystone/commit/e702369
        2: https://github.com/openstack/keystone/commit/e923a14
        3: https://github.com/openstack/keystone/commit/9804081
        4: https://github.com/openstack/charm-keystone/commit/10e3d84
        """
        if (openstack_utils.get_os_release() <
                openstack_utils.get_os_release('trusty_mitaka')):
            logging.info('skipping test < trusty_mitaka')
            return
        with self.config_change(
                {'preferred-api-version': self.default_api_version},
                {'preferred-api-version': '3'}):
            for ip in self.keystone_ips:
                try:
                    logging.info('keystone IP {}'.format(ip))
                    ks_session = openstack_utils.get_keystone_session(
                        openstack_utils.get_overcloud_auth(address=ip))
                    ks_client = openstack_utils.get_keystone_session_client(
                        ks_session)
                    result = ks_client.domains.list()
                    logging.info('.domains.list: "{}"'
                                 .format(pprint.pformat(result)))
                except keystoneauth1.exceptions.http.Forbidden as e:
                    raise zaza_exceptions.KeystoneAuthorizationStrict(
                        'Retrieve domain list as admin with project scoped '
                        'token FAILED. ({})'.format(e))
            logging.info('OK')

    def test_end_user_domain_admin_access(self):
        """Verify that end-user domain admin does not have elevated privileges.

        In additon to validating that the `policy.json` is written and the
        service is restarted on config-changed, the test validates that our
        `policy.json` is correct.

        Catch regressions like LP: #1651989
        """
        if (openstack_utils.get_os_release() <
                openstack_utils.get_os_release('xenial_ocata')):
            logging.info('skipping test < xenial_ocata')
            return
        with self.config_change(
                {'preferred-api-version': self.default_api_version},
                {'preferred-api-version': '3'}):
            for ip in self.keystone_ips:
                openrc = {
                    'API_VERSION': 3,
                    'OS_USERNAME': DEMO_ADMIN_USER,
                    'OS_PASSWORD': DEMO_ADMIN_USER_PASSWORD,
                    'OS_AUTH_URL': 'http://{}:5000/v3'.format(ip),
                    'OS_USER_DOMAIN_NAME': DEMO_DOMAIN,
                    'OS_DOMAIN_NAME': DEMO_DOMAIN,
                }
                logging.info('keystone IP {}'.format(ip))
                keystone_session = openstack_utils.get_keystone_session(
                    openrc, scope='DOMAIN')
                keystone_client = openstack_utils.get_keystone_session_client(
                    keystone_session)
                try:
                    # expect failure
                    keystone_client.domains.list()
                except keystoneauth1.exceptions.http.Forbidden as e:
                    logging.debug('Retrieve domain list as end-user domain '
                                  'admin NOT allowed...OK ({})'.format(e))
                    pass
                else:
                    raise zaza_exceptions.KeystoneAuthorizationPermissive(
                        'Retrieve domain list as end-user domain admin '
                        'allowed when it should not be.')
        logging.info('OK')

    def test_end_user_acccess_and_token(self):
        """Verify regular end-user access resources and validate token data.

        In effect this also validates user creation, presence of standard
        roles (`_member_`, `Member`), effect of policy and configuration
        of `token-provider`.
        """
        def _validate_token_data(openrc):
            keystone_session = openstack_utils.get_keystone_session(
                openrc)
            keystone_client = openstack_utils.get_keystone_session_client(
                keystone_session)
            token = keystone_session.get_token()
            if (openstack_utils.get_os_release() <
                    openstack_utils.get_os_release('xenial_ocata')):
                if len(token) != 32:
                    raise zaza_exceptions.KeystoneWrongTokenProvider(
                        'We expected a UUID token and got this: "{}"'
                        .format(token))
            else:
                if len(token) < 180:
                    raise zaza_exceptions.KeystoneWrongTokenProvider(
                        'We expected a Fernet token and got this: "{}"'
                        .format(token))
            logging.info('token: "{}"'.format(pprint.pformat(token)))

            if (openstack_utils.get_os_release() <
                    openstack_utils.get_os_release('trusty_mitaka')):
                logging.info('skip: tokens.get_token_data() not allowed prior '
                             'to trusty_mitaka')
                return
            # get_token_data call also gets the service catalog
            token_data = keystone_client.tokens.get_token_data(token)
            if token_data.get('token', {}).get('catalog', None) is None:
                raise zaza_exceptions.KeystoneAuthorizationStrict(
                    # NOTE(fnordahl) the above call will probably throw a
                    # http.Forbidden exception, but just in case
                    'Regular end user not allowed to retrieve the service '
                    'catalog. ("{}")'.format(pprint.pformat(token_data)))
            logging.info('token_data: "{}"'.format(pprint.pformat(token_data)))

        if (openstack_utils.get_os_release() <
                openstack_utils.get_os_release('xenial_queens')):
            openrc = {
                'API_VERSION': 2,
                'OS_USERNAME': DEMO_USER,
                'OS_PASSWORD': DEMO_PASSWORD,
                'OS_TENANT_NAME': DEMO_TENANT,
            }
            for ip in self.keystone_ips:
                openrc.update(
                    {'OS_AUTH_URL': 'http://{}:5000/v2.0'.format(ip)})
                _validate_token_data(openrc)

        if (openstack_utils.get_os_release() >=
                openstack_utils.get_os_release('trusty_mitaka')):
            openrc = {
                'API_VERSION': 3,
                'OS_REGION_NAME': 'RegionOne',
                'OS_USER_DOMAIN_NAME': DEMO_DOMAIN,
                'OS_USERNAME': DEMO_USER,
                'OS_PASSWORD': DEMO_PASSWORD,
                'OS_PROJECT_DOMAIN_NAME': DEMO_DOMAIN,
                'OS_PROJECT_NAME': DEMO_PROJECT,
            }
            with self.config_change(
                    {'preferred-api-version': self.default_api_version},
                    {'preferred-api-version': '3'}):
                for ip in self.keystone_ips:
                    openrc.update(
                        {'OS_AUTH_URL': 'http://{}:5000/v3'.format(ip)})
                    _validate_token_data(openrc)


class SecurityTests(BaseKeystoneTest):
    """Keystone security tests tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running Keystone aa-tests."""
        super(SecurityTests, cls).setUpClass()

    def test_security_checklist(self):
        """Verify expected state with security-checklist."""
        # Changes fixing the below expected failures will be made following
        # this initial work to get validation in. There will be bugs targeted
        # to each one and resolved independently where possible.
        expected_failures = [
            'check-max-request-body-size',
            'disable-admin-token',
            'uses-sha256-for-hashing-tokens',
            'validate-file-ownership',
            'validate-file-permissions',
        ]
        expected_passes = [
            'uses-fernet-token-after-default',
            'insecure-debug-is-false',
        ]

        logging.info('Running `security-checklist` action'
                     ' on Keystone leader unit')
        test_utils.audit_assertions(
            zaza.model.run_action_on_leader(
                'keystone',
                'security-checklist',
                action_params={}),
            expected_passes,
            expected_failures,
            expected_to_pass=False)
