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

"""Encapsulate nova testing."""

import logging
import unittest

import zaza.charm_tests.glance.setup as glance_setup
import zaza.configure.guest


class BaseGuestCreateTest(unittest.TestCase):
    """Deprecated: Use zaza.configure.guest.launch_instance."""

    def launch_instance(self, instance_key):
        """Deprecated: Use zaza.configure.guest.launch_instance."""
        logging.info('BaseGuestCreateTest.launch_instance is deprecated '
                     'please use zaza.configure.guest.launch_instance')
        zaza.configure.guest.launch_instance(instance_key)


class CirrosGuestCreateTest(BaseGuestCreateTest):
    """Tests to launch a cirros image."""

    def test_launch_small_instance(self):
        """Launch a cirros instance and test connectivity."""
        zaza.configure.guest.launch_instance(
            glance_setup.CIRROS_IMAGE_NAME)


class LTSGuestCreateTest(BaseGuestCreateTest):
    """Tests to launch a LTS image."""

    def test_launch_small_instance(self):
        """Launch a Bionic instance and test connectivity."""
        zaza.configure.guest.launch_instance(
            glance_setup.LTS_IMAGE_NAME)
