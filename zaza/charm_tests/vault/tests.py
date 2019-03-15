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

"""Collection of tests for vault."""

import hvac
import time
import unittest
import uuid
import tempfile

import requests
import zaza.charm_lifecycle.utils as lifecycle_utils
import zaza.charm_tests.test_utils as test_utils
import zaza.charm_tests.vault.utils as vault_utils
import zaza.utilities.cert
import zaza.utilities.openstack
import zaza.model


class BaseVaultTest(unittest.TestCase):
    """Base class for vault tests."""

    @classmethod
    def setUpClass(cls):
        """Run setup for Vault tests."""
        cls.clients = vault_utils.get_clients()
        cls.vip_client = vault_utils.get_vip_client()
        if cls.vip_client:
            cls.clients.append(cls.vip_client)
        cls.vault_creds = vault_utils.get_credentails()
        vault_utils.unseal_all(cls.clients, cls.vault_creds['keys'][0])
        vault_utils.auth_all(cls.clients, cls.vault_creds['root_token'])


class UnsealVault(BaseVaultTest):
    """Unseal Vault only.

    Useful for bootstrapping Vault when it is present in test bundles for other
    charms.
    """

    @classmethod
    def setUpClass(cls):
        """Run setup for UnsealVault class."""
        super(UnsealVault, cls).setUpClass()

    def test_unseal(self, test_config=None):
        """Unseal Vault.

        :param test_config: (Optional) Zaza test config
        :type test_config: charm_lifecycle.utils.get_charm_config()
        """
        vault_utils.run_charm_authorize(self.vault_creds['root_token'])
        if not test_config:
            test_config = lifecycle_utils.get_charm_config()
        del test_config['target_deploy_status']['vault']
        zaza.model.wait_for_application_states(
            states=test_config.get('target_deploy_status', {}))


class VaultTest(BaseVaultTest):
    """Encapsulate vault tests."""

    @classmethod
    def setUpClass(cls):
        """Run setup for Vault tests."""
        super(VaultTest, cls).setUpClass()

    def test_csr(self):
        """Test generating a csr and uploading a signed certificate."""
        vault_actions = zaza.model.get_actions(
            'vault')
        if 'get-csr' not in vault_actions:
            raise unittest.SkipTest('Action not defined')
        try:
            zaza.model.get_application(
                'keystone')
        except KeyError:
            raise unittest.SkipTest('No client to test csr')
        action = vault_utils.run_charm_authorize(
            self.vault_creds['root_token'])
        action = vault_utils.run_get_csr()

        intermediate_csr = action.data['results']['output']
        (cakey, cacert) = zaza.utilities.cert.generate_cert(
            'DivineAuthority',
            generate_ca=True)
        intermediate_cert = zaza.utilities.cert.sign_csr(
            intermediate_csr,
            cakey.decode(),
            cacert.decode(),
            generate_ca=True)
        action = vault_utils.run_upload_signed_csr(
            pem=intermediate_cert,
            root_ca=cacert,
            allowed_domains='openstack.local')

        test_config = lifecycle_utils.get_charm_config()
        del test_config['target_deploy_status']['vault']
        zaza.model.block_until_file_has_contents(
            'keystone',
            zaza.utilities.openstack.KEYSTONE_REMOTE_CACERT,
            cacert.decode().strip())
        zaza.model.wait_for_application_states(
            states=test_config.get('target_deploy_status', {}))
        ip = zaza.model.get_app_ips(
            'keystone')[0]
        with tempfile.NamedTemporaryFile(mode='w') as fp:
            fp.write(cacert.decode())
            fp.flush()
            requests.get('https://{}:5000'.format(ip), verify=fp.name)

    def test_all_clients_authenticated(self):
        """Check all vault clients are authenticated."""
        for client in self.clients:
            for i in range(1, 10):
                try:
                    self.assertTrue(client.hvac_client.is_authenticated())
                except hvac.exceptions.InternalServerError:
                    time.sleep(2)
                else:
                    break
            else:
                self.assertTrue(client.hvac_client.is_authenticated())

    def check_read(self, key, value):
        """Check reading the key from all vault units."""
        for client in self.clients:
            self.assertEqual(
                client.hvac_client.read('secret/uuids')['data']['uuid'],
                value)

    def test_consistent_read_write(self):
        """Test reading and writing data to vault."""
        key = 'secret/uuids'
        for client in self.clients:
            value = str(uuid.uuid1())
            client.hvac_client.write(key, uuid=value, lease='1h')
            # Now check all clients read the same value back
            self.check_read(key, value)

    @test_utils.skipIfNotHA('vault')
    def test_vault_ha_statuses(self):
        """Check Vault charm HA status."""
        leader = []
        leader_address = []
        leader_cluster_address = []
        for client in self.clients:
            self.assertTrue(client.hvac_client.ha_status['ha_enabled'])
            leader_address.append(
                client.hvac_client.ha_status['leader_address'])
            leader_cluster_address.append(
                client.hvac_client.ha_status['leader_cluster_address'])
            if (client.hvac_client.ha_status['is_self'] and not
                    client.vip_client):
                leader.append(client.addr)
        # Check there is exactly one leader
        self.assertEqual(len(leader), 1)
        # Check both cluster addresses match accross the cluster
        self.assertEqual(len(set(leader_address)), 1)
        self.assertEqual(len(set(leader_cluster_address)), 1)

    def test_check_vault_status(self):
        """Check Vault charm status."""
        for client in self.clients:
            self.assertFalse(client.hvac_client.seal_status['sealed'])
            self.assertTrue(client.hvac_client.seal_status['cluster_name'])

    def test_vault_authorize_charm_action(self):
        """Test the authorize_charm action."""
        vault_actions = zaza.model.get_actions(
            'vault')
        if 'authorize-charm' not in vault_actions:
            raise unittest.SkipTest('Action not defined')
        action = vault_utils.run_charm_authorize(
            self.vault_creds['root_token'])
        self.assertEqual(action.status, 'completed')
        client = self.clients[0]
        self.assertIn(
            'local-charm-policy',
            client.hvac_client.list_policies())


if __name__ == '__main__':
    unittest.main()
