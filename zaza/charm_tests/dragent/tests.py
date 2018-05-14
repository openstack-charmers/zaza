#!/usr/bin/env python3

import unittest

from zaza.utilities import cli as cli_utils
from zaza.charm_tests.dragent import test


class DRAgentTest(unittest.TestCase):

    BGP_PEER_APPLICATION = 'quagga'

    @classmethod
    def setUpClass(cls):
        cli_utils.setup_logging()

    def test_bgp_routes(self):
        test.test_bgp_routes(peer_application_name=self.BGP_PEER_APPLICATION)


if __name__ == "__main__":
    unittest.main()
