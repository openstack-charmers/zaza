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

"""Module of functions for interfacing with vault and the vault charm."""

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
    """Return URL for api access.

    :param unit_ip: IP address to use in vault url
    :type unit_ip: str
    :returns: URL
    :rtype: atr
    """
    vault_config = zaza.model.get_application_config('vault')
    transport = 'http'
    if vault_config['ssl-cert']['value']:
        transport = 'https'
    return '{}://{}:8200'.format(transport, ip)


def get_hvac_client(vault_url, cacert=None):
    """Return an hvac client for the given URL.

    :param vault_url: Vault url to point client at
    :type vault_url: str
    :param cacert: Path to CA cert used for vaults api cert.
    :type cacert: str
    :returns: hvac client for given url
    :rtype: hvac.Client
    """
    return hvac.Client(url=vault_url, verify=cacert)


def get_vip_client(cacert=None):
    """Return CharmVaultClient for the vip if a vip is being used.

    :param cacert: Path to CA cert used for vaults api cert.
    :type cacert: str
    :returns: CharmVaultClient
    :rtype: CharmVaultClient or None
    """
    client = None
    vault_config = zaza.model.get_application_config('vault')
    vip = vault_config.get('vip', {}).get('value')
    if vip:
        client = CharmVaultClient(
            vip,
            get_hvac_client(get_unit_api_url(vip), cacert=cacert),
            True)
    return client


def init_vault(client, shares=1, threshold=1):
    """Initialise vault.

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


def get_clients(units=None, cacert=None):
    """Create a list of clients, one per vault server.

    :param units: List of IP addresses of vault endpoints
    :type units: [str, str, ...]
    :param cacert: Path to CA cert used for vaults api cert.
    :type cacert: str
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
            get_hvac_client(vault_url, cacert=cacert),
            False))
    return clients


def is_initialized(client):
    """Check if vault is initialized.

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


def ensure_secret_backend(client):
    """Ensure that vault has a KV backend mounted at secret.

    :param client: Client to use to talk to vault
    :type client: CharmVaultClient
    """
    try:
        client.hvac_client.enable_secret_backend(
            backend_type='kv',
            description='Charm created KV backend',
            mount_point='secret',
            options={'version': 1})
    except hvac.exceptions.InvalidRequest:
        pass


def get_credentails():
    """Retrieve vault token and keys from unit.

    Retrieve vault token and keys from unit. These are stored on a unit
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
            creds = yaml.safe_load(stream)
    return creds


def store_credentails(creds):
    """Store the supplied credentials.

    Store the supplied credentials on a vault unit. ONLY USE FOR FUNCTIONAL
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
    """Read the vault credentials from the auth_file.

    :param auth_file: Path to file with credentials
    :type auth_file: str
    :returns: Token and keys
    :rtype: dict
    """
    with open(auth_file, 'r') as stream:
        vault_creds = yaml.safe_load(stream)
    return vault_creds


def write_credentails(auth_file, vault_creds):
    """Write the vault credentials to the auth_file.

    :param auth_file: Path to file to write credentials
    :type auth_file: str
    """
    with open(auth_file, 'w') as outfile:
        yaml.dump(vault_creds, outfile, default_flow_style=False)


def unseal_all(clients, key):
    """Unseal all the vaults with the given clients with the provided key.

    :param clients: List of clients
    :type clients: [CharmVaultClient, ...]
    :param key: key to unlock clients
    :type key: str
    """
    for client in clients:
        if client.hvac_client.is_sealed():
            client.hvac_client.unseal(key)


def auth_all(clients, token):
    """Authenticate all the given clients with the provided token.

    :param clients: List of clients
    :type clients: [CharmVaultClient, ...]
    :param token: Token to authorize clients
    :type token: str
    """
    for client in clients:
        client.hvac_client.token = token


def run_charm_authorize(token):
    """Authorize charm to perfom certain actions.

    Run vault charm action to authorize the charm to perform a limited
    set of calls against the vault API.

    :param token: Token to authorize action against vault.
    :type token: str
    :returns: Action object
    :rtype: juju.action.Action
    """
    return zaza.model.run_action_on_leader(
        'vault',
        'authorize-charm',
        action_params={'token': token})


def run_get_csr():
    """Retrieve CSR from vault.

    Run vault charm action to retrieve CSR from vault.

    :returns: Action object
    :rtype: juju.action.Action
    """
    return zaza.model.run_action_on_leader(
        'vault',
        'get-csr',
        action_params={})


def run_upload_signed_csr(pem, root_ca, allowed_domains):
    """Upload signed cert to vault.

    :param pem: Signed certificate text
    :type pem: str
    :param token: Root CA text.
    :type token: str
    :param allowed_domains: List of domains that may have certs issued from
                            certificate.
    :type allowed_domains: list
    :returns: Action object
    :rtype: juju.action.Action
    """
    return zaza.model.run_action_on_leader(
        'vault',
        'upload-signed-csr',
        action_params={
            'pem': base64.b64encode(pem).decode(),
            'root-ca': base64.b64encode(root_ca).decode(),
            'allowed-domains=': allowed_domains,
            'ttl': '24h'})
