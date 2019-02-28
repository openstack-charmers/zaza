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

"""Ceph-osd Testing."""

import logging
import unittest

import zaza.charm_tests.test_utils as test_utils
import zaza.model as zaza_model


class SecurityTest(unittest.TestCase):
    """Ceph Security Tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running ceph security tests."""
        super(SecurityTest, cls).setUpClass()

    def test_osd_security_checklist(self):
        """Verify expected state with security-checklist."""
        expected_failures = []
        expected_passes = [
            'validate-file-ownership',
            'validate-file-permissions',
        ]

        logging.info('Running `security-checklist` action'
                     ' on Ceph OSD leader unit')
        test_utils.audit_assertions(
            zaza_model.run_action_on_leader(
                'ceph-osd',
                'security-checklist',
                action_params={}),
            expected_passes,
            expected_failures,
            expected_to_pass=True)
