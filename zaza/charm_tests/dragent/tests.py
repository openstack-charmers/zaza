#!/usr/bin/env python3
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
