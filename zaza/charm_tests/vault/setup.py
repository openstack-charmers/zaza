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

def basic_setup():
    clients = vault_utils.get_clients()
    unseal_client = clients[0]
    initialized = vault_utils.is_initialized(unseal_client)
    # The credentials are written to a file to allow the tests to be re-run
    # this is mainly useful for manually working on the tests.
    if initialized:
       vault_creds = vault_utils.get_credentails()
    else:
       vault_creds = vault_utils.init_vault(unseal_client[1])
       vault_utils.store_credentails(vault_creds)
    print(vault_creds)
