#!/usr/bin/env python3

import unittest

from zaza.utilities import _local_utils
from zaza.charm_tests.dragent import test_dragent


class DRAgentTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _local_utils.setup_logging()

    def test_bgp_routes(self):
        test_dragent.test_bgp_routes(peer_application_name="quagga")


if __name__ == "__main__":
    unittest.main()
