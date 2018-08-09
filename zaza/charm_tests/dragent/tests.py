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

"""Define class of BGP tests."""

import unittest

from zaza.utilities import cli as cli_utils
from zaza.charm_tests.dragent import test


class DRAgentTest(unittest.TestCase):
    """Class to encapsulate BPG tests."""

    BGP_PEER_APPLICATION = 'quagga'

    @classmethod
    def setUpClass(cls):
        """Run setup for BGP tests."""
        cli_utils.setup_logging()

    def test_bgp_routes(self):
        """Run bgp tests."""
        test.test_bgp_routes(peer_application_name=self.BGP_PEER_APPLICATION)


if __name__ == "__main__":
    unittest.main()
