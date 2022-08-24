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
import zaza.utilities.juju as juju_utils


class RegressionTest(unittest.TestCase):
    """Regression Tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup."""
        super().setUpClass()
        cls._model = zaza.model.get_juju_model()
        logging.info("model is %s", cls._model)

    def test_01_get_app_ips(self):
        """Verify that get_app_ips() doesn't invoke to async loops."""
        logging.info('Verify that get_app_ips() works.')
        ips = zaza.model.get_app_ips('ubuntu', model_name=self._model)
        for ip in ips:
            logging.info("Ip found %s", ip)
            self.assertIsNotNone(ip)

    def test_02_get_unit_public_address(self):
        """Verify get_unit_public_address()."""
        logging.info('Verify that get_unit_public_address() function works.')
        units = zaza.model.get_units('ubuntu')
        logging.info('units found: %s', units)
        ips = [zaza.model.get_unit_public_address(unit, model_name=self._model)
               for unit in units]
        for ip in ips:
            logging.info("Ip found %s", ip)
            self.assertIsNotNone(ip)

    def test_03_get_subordinates(self):
        """Get the subordinates associated to a principal."""
        logging.info('Get the list of subordinates.')
        units = [u.entity_id for u in zaza.model.get_units('ubuntu')]
        logging.info('principal units found: %s', units)
        subordinate = juju_utils.get_subordinate_units([units[0]],
                                                       charm_name='ntp')
        logging.info('subordinate(s) found %s for principal %s',
                     subordinate, units[0])
        self.assertEqual(len(subordinate), 1)
