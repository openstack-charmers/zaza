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

import zaza.charms_tests.test_utils as test_utils
import zaza.model


class VaultUtils(object):

    def get_client(self, vault_url):
        """Return an hvac client for the given URL

        :param vault_url: Vault url to point client at
        :returns: hvac.Client
        """
        return hvac.Client(url=vault_url)

    def init_vault(self, client, shares=1, threshold=1):
        """Initialise vault

        :param client: hvac.Client Client to use for initiliasation
        :param shares: int Number of key shares to create
        :param threshold: int Number of keys needed to unseal vault
        :returns: hvac.Client
        """
        return client.initialize(shares, threshold)

    def get_clients(self, units=None):
        """Create a list of clients, one per vault server

        :param units: [ip1, ip2, ...] List of IP addresses of vault endpoints
        :returns: [hvac.Client, ...] List of clients
        """
        if not units:
            units = zaza.model.unit_ips('vault')
        clients = []
        for unit in units:
            vault_url = 'http://{}:8200'.format(unit)
            clients.append((unit, self.get_client(vault_url)))
        return clients

    def is_initialized(self, client):
        """Check if vault is initialized

        :param client: hvac.Client Client to use to check if vault is
                                   initialized
        :returns: bool
        """
        initialized = False
        for i in range(1, 10):
            try:
                initialized = client[1].is_initialized()
            except (ConnectionRefusedError,
                    urllib3.exceptions.NewConnectionError,
                    urllib3.exceptions.MaxRetryError,
                    requests.exceptions.ConnectionError):
                time.sleep(2)
            else:
                break
        else:
            raise Exception("Cannot connect")
        return initialized

    def get_credentails_from_file(self, auth_file):
        """Read the vault credentials from the auth_file

        :param auth_file: str Path to file with credentials
        :returns: {} Dictionary of credentials
        """
        with open(auth_file, 'r') as stream:
            vault_creds = yaml.load(stream)
        return vault_creds

    def write_credentails(self, auth_file, vault_creds):
        """Write the vault credentials to the auth_file

        :param auth_file: str Path to file to write credentials
        """
        with open(auth_file, 'w') as outfile:
            yaml.dump(vault_creds, outfile, default_flow_style=False)

    def unseal_all(self, clients, key):
        """Unseal all the vaults with the given clients with the provided key

        :param clients: [hvac.Client, ...] List of clients
        :param key: str key to unlock clients
        """
        for (addr, client) in clients:
            if client.is_sealed():
                client.unseal(key)

    def auth_all(self, clients, token):
        """Authenticate all the given clients with the provided token

        :param clients: [hvac.Client, ...] List of clients
        :param token: str token to authorize clients
        """
        for (addr, client) in clients:
            client.token = token


class VaultTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        vutils = VaultUtils()
        cls.clients = vutils.get_clients()
        unseal_client = cls.clients[0]
        initialized = vutils.is_initialized(unseal_client)
        # The credentials are written to a file to allow the tests to be re-run
        # this is mainly useful for manually working on the tests.
        auth_file = "/tmp/vault_tests.yaml"
        if initialized:
            vault_creds = vutils.get_credentails_from_file(auth_file)
        else:
            vault_creds = vutils.init_vault(unseal_client[1])
            vutils.write_credentails(auth_file, vault_creds)
        vutils.unseal_all(cls.clients, vault_creds['keys'][0])
        vutils.auth_all(cls.clients, vault_creds['root_token'])

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
