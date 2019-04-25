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

"""Encapsulate barbican-vault testing."""

import zaza
import zaza.openstack.charm_tests.vault.tests as vault_tests


class BarbicanVaultUnsealVault(vault_tests.UnsealVault):
    """Helper class to unseal Vault and update deploy status expectations."""

    @classmethod
    def setUpClass(cls):
        """Run setup for UnsealVault class."""
        super(BarbicanVaultUnsealVault, cls).setUpClass()

    def test_unseal(self):
        """Unseal vault, update barbican-vault deploy status expectations."""
        test_config = zaza.charm_lifecycle.utils.get_charm_config()
        del test_config['target_deploy_status']['barbican-vault']
        super().test_unseal(test_config)
