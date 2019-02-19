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

import unittest
import zaza.charm_tests.vault.utils as vault_utils
import zaza.charm_tests.vault.tests as vault_tests


def basic_setup(cacert=None):
    """Run basic setup for vault tests.

    :param cacert: Path to CA cert used for vaults api cert.
    :type cacert: str
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


def auto_inititialize():
    """Auto initialize vault for testing.

    In a stack that includes and relies on certificate in vault initialize
    vault by unsealing and creating a certificate authority.
    """
    suite = unittest.TestLoader().loadTestsFromTestCase(vault_tests.VaultTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
