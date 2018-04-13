#!/usr/bin/env python3

import hvac
import time
import unittest
import uuid

import zaza.charm_tests.test_utils as test_utils
import zaza.charm_tests.vault.utils as vault_utils


class VaultTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.clients = vault_utils.get_clients()
        cls.vip_client = vault_utils.get_vip_client()
        if cls.vip_client:
            cls.clients.append(cls.vip_client)
        vault_creds = vault_utils.get_credentails()
        vault_utils.unseal_all(cls.clients, vault_creds['keys'][0])
        vault_utils.auth_all(cls.clients, vault_creds['root_token'])

    def test_all_clients_authenticated(self):
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
        for client in self.clients:
            self.assertEqual(
                client.hvac_client.read('secret/uuids')['data']['uuid'],
                value)

    def test_consistent_read_write(self):
        key = 'secret/uuids'
        for client in self.clients:
            value = str(uuid.uuid1())
            client.hvac_client.write(key, uuid=value, lease='1h')
            # Now check all clients read the same value back
            self.check_read(key, value)

    @test_utils.skipIfNotHA('vault')
    def test_vault_ha_statuses(self):
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
        for client in self.clients:
            self.assertFalse(client.hvac_client.seal_status['sealed'])
            self.assertTrue(client.hvac_client.seal_status['cluster_name'])


if __name__ == '__main__':
    unittest.main()
