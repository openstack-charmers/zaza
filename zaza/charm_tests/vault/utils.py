#!/usr/bin/env python3

import base64
import hvac
import requests
import tempfile
import time
import urllib3
import yaml

import collections

import zaza.model

AUTH_FILE = "vault_tests.yaml"
CharmVaultClient = collections.namedtuple(
    'CharmVaultClient', ['addr', 'hvac_client', 'vip_client'])


def get_unit_api_url(ip):
    """Return URL for api access

    :param unit_ip: IP address to use in vault url
    :type unit_ip: str
    :returns: URL
    :rtype: atr
    """
    return 'http://{}:8200'.format(ip)


def get_hvac_client(vault_url):
    """Return an hvac client for the given URL

    :param vault_url: Vault url to point client at
    :type vault_url: str
    :returns: hvac client for given url
    :rtype: hvac.Client
    """
    return hvac.Client(url=vault_url)


def get_vip_client():
    """Return CharmVaultClient for the vip if a vip is being used

    :returns: CharmVaultClient
    :rtype: CharmVaultClient or None
    """
    client = None
    vault_config = zaza.model.get_application_config('vault')
    vip = vault_config.get('vip', {}).get('value')
    if vip:
        client = CharmVaultClient(
            vip,
            get_hvac_client(get_unit_api_url(vip)),
            True)
    return client


def init_vault(client, shares=1, threshold=1):
    """Initialise vault

    :param client: Client to use for initiliasation
    :type client: CharmVaultClient
    :param shares: Number of key shares to create
    :type shares: int
    :param threshold: Number of keys needed to unseal vault
    :type threshold: int
    :returns: Token and key(s) for accessing vault
    :rtype: dict
    """
    return client.hvac_client.initialize(shares, threshold)


def get_clients(units=None):
    """Create a list of clients, one per vault server

    :param units: List of IP addresses of vault endpoints
    :type units: [str, str, ...]
    :returns: List of CharmVaultClients
    :rtype: [CharmVaultClient, ...]
    """
    if not units:
        units = zaza.model.get_app_ips('vault')
    clients = []
    for unit in units:
        vault_url = get_unit_api_url(unit)
        clients.append(CharmVaultClient(
            unit,
            get_hvac_client(vault_url),
            False))
    return clients


def is_initialized(client):
    """Check if vault is initialized

    :param client: Client to use to check if vault is initialized
    :type client: CharmVaultClient
    :returns: Whether vault is initialized
    :rtype: bool
    """
    initialized = False
    for i in range(1, 10):
        try:
            initialized = client.hvac_client.is_initialized()
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
    """Retrieve vault token and keys from unit. These are stored on a unit
       during functional tests.

    :returns: Tokens and keys for accessing test environment
    :rtype: dict
    """
    unit = zaza.model.get_first_unit_name('vault')
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmp_file = '{}/{}'.format(tmpdirname, AUTH_FILE)
        zaza.model.scp_from_unit(
            unit,
            '~/{}'.format(AUTH_FILE),
            tmp_file)
        with open(tmp_file, 'r') as stream:
            creds = yaml.load(stream)
    return creds


def store_credentails(creds):
    """Store the supplied credentials on a vault unit. ONLY USE FOR FUNCTIONAL
       TESTING.

    :param creds: Keys and token to store
    :type creds: dict
    """
    unit = zaza.model.get_first_unit_name('vault')
    with tempfile.NamedTemporaryFile(mode='w') as fp:
        fp.write(yaml.dump(creds))
        fp.flush()
        zaza.model.scp_to_unit(
            unit,
            fp.name,
            '~/{}'.format(AUTH_FILE))


def get_credentails_from_file(auth_file):
    """Read the vault credentials from the auth_file

    :param auth_file: Path to file with credentials
    :type auth_file: str
    :returns: Token and keys
    :rtype: dict
    """
    with open(auth_file, 'r') as stream:
        vault_creds = yaml.load(stream)
    return vault_creds


def write_credentails(auth_file, vault_creds):
    """Write the vault credentials to the auth_file

    :param auth_file: Path to file to write credentials
    :type auth_file: str
    """
    with open(auth_file, 'w') as outfile:
        yaml.dump(vault_creds, outfile, default_flow_style=False)


def unseal_all(clients, key):
    """Unseal all the vaults with the given clients with the provided key

    :param clients: List of clients
    :type clients: [CharmVaultClient, ...]
    :param key: key to unlock clients
    :type key: str
    """
    for client in clients:
        if client.hvac_client.is_sealed():
            client.hvac_client.unseal(key)


def auth_all(clients, token):
    """Authenticate all the given clients with the provided token

    :param clients: List of clients
    :type clients: [CharmVaultClient, ...]
    :param token: Token to authorize clients
    :type token: str
    """
    for client in clients:
        client.hvac_client.token = token


def run_charm_authorize(token):
    return zaza.model.run_action_on_leader(
        'vault',
        'authorize-charm',
        action_params={'token': token})


def run_get_csr():
    return zaza.model.run_action_on_leader(
        'vault',
        'get-csr',
        action_params={})


def run_upload_signed_csr(pem, root_ca, allowed_domains):
    return zaza.model.run_action_on_leader(
        'vault',
        'upload-signed-csr',
        action_params={
            'pem': base64.b64encode(pem).decode(),
            'root-ca': base64.b64encode(root_ca).decode(),
            'allowed-domains=': allowed_domains,
            'ttl': '24h'})
