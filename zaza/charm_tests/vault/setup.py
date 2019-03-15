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

"""Run configuration phase."""

import requests
import tempfile

import zaza.charm_lifecycle.utils as lifecycle_utils
import zaza.charm_tests.vault.utils as vault_utils
import zaza.model
import zaza.utilities.cert
import zaza.utilities.openstack


def basic_setup(cacert=None, unseal_and_authorize=False):
    """Run basic setup for vault tests.

    :param cacert: Path to CA cert used for vaults api cert.
    :type cacert: str
    :param unseal_and_authorize: Whether to unseal and authorize vault.
    :type unseal_and_authorize: bool
    """
    clients = vault_utils.get_clients(cacert=cacert)
    vip_client = vault_utils.get_vip_client(cacert=cacert)
    if vip_client:
        unseal_client = vip_client
    else:
        unseal_client = clients[0]
    initialized = vault_utils.is_initialized(unseal_client)
    # The credentials are written to a file to allow the tests to be re-run
    # this is mainly useful for manually working on the tests.
    if initialized:
        vault_creds = vault_utils.get_credentails()
    else:
        vault_creds = vault_utils.init_vault(unseal_client)
        vault_utils.store_credentails(vault_creds)

    # For use by charms or bundles other than vault
    if unseal_and_authorize:
        vault_utils.unseal_all(clients, vault_creds['keys'][0])
        vault_utils.auth_all(clients, vault_creds['root_token'])
        vault_utils.run_charm_authorize(vault_creds['root_token'])


def auto_inititialize(cacert=None):
    """Auto initialize vault for testing.

    Generate a csr and uploading a signed certificate.
    In a stack that includes and relies on certificates in vault, initialize
    vault by unsealing and creating a certificate authority.

    :param cacert: Path to CA cert used for vault's api cert.
    :type cacert: str
    :returns: None
    :rtype: None
    """
    basic_setup(cacert=cacert, unseal_and_authorize=True)

    action = vault_utils.run_get_csr()
    intermediate_csr = action.data['results']['output']
    (cakey, cacertificate) = zaza.utilities.cert.generate_cert(
        'DivineAuthority',
        generate_ca=True)
    intermediate_cert = zaza.utilities.cert.sign_csr(
        intermediate_csr,
        cakey.decode(),
        cacertificate.decode(),
        generate_ca=True)
    action = vault_utils.run_upload_signed_csr(
        pem=intermediate_cert,
        root_ca=cacertificate,
        allowed_domains='openstack.local')

    validate_ca(cacertificate)


def validate_ca(cacertificate, application="keystone", port=5000):
    """Validate Certificate Authority against application.

    :param cacertificate: PEM formatted CA certificate
    :type cacertificate: str
    :param application: Which application to validate against.
    :type application: str
    :param port: Port to validate against.
    :type port: int
    :returns: None
    :rtype: None
    """
    zaza.model.block_until_file_has_contents(
        application,
        zaza.utilities.openstack.KEYSTONE_REMOTE_CACERT,
        cacertificate.decode().strip())
    test_config = lifecycle_utils.get_charm_config()
    zaza.model.wait_for_application_states(
        states=test_config.get('target_deploy_status', {}))
    vip = (zaza.model.get_application_config(application)
           .get("vip").get("value"))
    if vip:
        ip = vip
    else:
        ip = zaza.model.get_app_ips(application)[0]
    with tempfile.NamedTemporaryFile(mode='w') as fp:
        fp.write(cacertificate.decode())
        fp.flush()
        requests.get('https://{}:{}'.format(ip, str(port)), verify=fp.name)
