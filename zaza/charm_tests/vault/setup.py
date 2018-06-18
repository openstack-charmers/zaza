"""Run configuration phase."""

import zaza.charm_tests.vault.utils as vault_utils


def basic_setup():
    """Run basic setup for vault tests."""
    clients = vault_utils.get_clients()
    vip_client = vault_utils.get_vip_client()
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
