#!/usr/bin/env python3

import hvac
import logging
import os
import requests
import time
import unittest
import urllib3
import uuid
import yaml

import zaza.charm_tests.test_utils as test_utils
import zaza.charm_tests.vault.utils as vault_utils


class VaultTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
#        vault_utils = VaultUtils()
#        cls.clients = vault_utils.get_clients()
#        unseal_client = cls.clients[0]
#        initialized = vault_utils.is_initialized(unseal_client)
#        # The credentials are written to a file to allow the tests to be re-run
#        # this is mainly useful for manually working on the tests.
#        auth_file = "/tmp/vault_tests.yaml"
#        if initialized:
#            vault_creds = vault_utils.get_credentails_from_file(auth_file)
#        else:
#            vault_creds = vault_utils.init_vault(unseal_client[1])
#            vault_utils.write_credentails(auth_file, vault_creds)
        cls.clients = vault_utils.get_clients()
        vault_creds = vault_utils.get_credentails()
        vault_utils.unseal_all(cls.clients, vault_creds['keys'][0])
        vault_utils.auth_all(cls.clients, vault_creds['root_token'])

    def test_all_clients_authenticated(self):
        for (addr, client) in self.clients:
            for i in range(1, 10):
                try:
                    self.assertTrue(client.is_authenticated())
                except hvac.exceptions.InternalServerError:
                    time.sleep(2)
                else:
                    break
            else:
                self.assertTrue(client.is_authenticated())

    def check_read(self, key, value):
        for (addr, client) in self.clients:
            self.assertEqual(
                client.read('secret/uuids')['data']['uuid'],
                value)

    def test_consistent_read_write(self):
        key = 'secret/uuids'
        for (addr, client) in self.clients:
            value = str(uuid.uuid1())
            client.write(key, uuid=value, lease='1h')
            # Now check all clients read the same value back
            self.check_read(key, value)

    @test_utils.skipIfNotHA('vault')
    def test_vault_ha_statuses(self):
        leader = []
        leader_address = []
        leader_cluster_address = []
        for (addr, client) in self.clients:
            self.assertTrue(client.ha_status['ha_enabled'])
            leader_address.append(
                client.ha_status['leader_address'])
            leader_cluster_address.append(
                client.ha_status['leader_cluster_address'])
            if client.ha_status['is_self']:
                leader.append(addr)
        # Check there is exactly one leader
        self.assertEqual(len(leader), 1)
        # Check both cluster addresses match accross the cluster
        self.assertEqual(len(set(leader_address)), 1)
        self.assertEqual(len(set(leader_cluster_address)), 1)

    def test_check_vault_status(self):
        for (addr, client) in self.clients:
            self.assertFalse(client.seal_status['sealed'])
            self.assertTrue(client.seal_status['cluster_name'])


if __name__ == '__main__':
    unittest.main()
