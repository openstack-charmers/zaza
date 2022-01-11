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

"""Test regression libjuju / zaza integration."""

import logging
import unittest

import zaza.model


class RegressionTest(unittest.TestCase):
    """Regression Tests."""

    def test_get_unit_public_address(self):
        """Verify get_unit_public_address()."""
        logging.info('Verify that get_unit_public_address() function works.')
        units = zaza.model.get_units('ubuntu')
        ips = [zaza.model.get_unit_public_address(unit) for unit in units]
        for ip in ips:
            self.assertIsNotNone(ip)

    def test_get_app_ips(self):
        """Verify that get_app_ips() doesn't invoke to async loops."""
        logging.info('Verify that get_app_ips() works.')
        ips = zaza.model.get_app_ips('ubuntu')
        for ip in ips:
            self.assertIsNotNone(ip)

