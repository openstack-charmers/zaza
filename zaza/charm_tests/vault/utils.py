#!/usr/bin/env python3

import asyncio
import hvac
import logging
import os
import requests
import time
import tempfile
import unittest
import urllib3
import uuid
import yaml

import zaza.charm_tests.test_utils as test_utils
import zaza.model

AUTH_FILE = "vault_tests.yaml"


def get_client(vault_url):
    """Return an hvac client for the given URL

    :param vault_url: Vault url to point client at
    :returns: hvac.Client
    """
    return hvac.Client(url=vault_url)

def init_vault(client, shares=1, threshold=1):
    """Initialise vault

    :param client: hvac.Client Client to use for initiliasation
    :param shares: int Number of key shares to create
    :param threshold: int Number of keys needed to unseal vault
    :returns: hvac.Client
    """
    return client.initialize(shares, threshold)

def get_clients(units=None):
    """Create a list of clients, one per vault server

    :param units: [ip1, ip2, ...] List of IP addresses of vault endpoints
    :returns: [hvac.Client, ...] List of clients
    """
    if not units:
        units = zaza.model.get_app_ips('vault')
    clients = []
    for unit in units:
        vault_url = 'http://{}:8200'.format(unit)
        clients.append((unit, get_client(vault_url)))
    return clients

def is_initialized(client):
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

def get_credentails():
    unit = zaza.model.get_first_unit('vault')
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmp_file = '{}/{}'.format(tmpdirname, AUTH_FILE)
        zaza.model.scp_from_unit(unit, '~/{}'.format(AUTH_FILE), tmp_file)
        with open(tmp_file, 'r') as stream:
            creds = yaml.load(stream)
    return creds

def store_credentails(creds):
    unit = zaza.model.get_first_unit('vault')
    with tempfile.NamedTemporaryFile(mode='w') as fp:
        fp.write(yaml.dump(creds))
        fp.flush()
        zaza.model.scp_to_unit(unit, fp.name, '~/{}'.format(AUTH_FILE))
        
def get_credentails_from_file(auth_file):
    """Read the vault credentials from the auth_file

    :param auth_file: str Path to file with credentials
    :returns: {} Dictionary of credentials
    """
    with open(auth_file, 'r') as stream:
        vault_creds = yaml.load(stream)
    return vault_creds

def write_credentails(auth_file, vault_creds):
    """Write the vault credentials to the auth_file

    :param auth_file: str Path to file to write credentials
    """
    with open(auth_file, 'w') as outfile:
        yaml.dump(vault_creds, outfile, default_flow_style=False)

def unseal_all(clients, key):
    """Unseal all the vaults with the given clients with the provided key

    :param clients: [hvac.Client, ...] List of clients
    :param key: str key to unlock clients
    """
    for (addr, client) in clients:
        if client.is_sealed():
            client.unseal(key)

def auth_all(clients, token):
    """Authenticate all the given clients with the provided token

    :param clients: [hvac.Client, ...] List of clients
    :param token: str token to authorize clients
    """
    for (addr, client) in clients:
        client.token = token
