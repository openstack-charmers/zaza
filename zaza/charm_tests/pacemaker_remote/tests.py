#!/usr/bin/env python3

# Copyright 2019 Canonical Ltd.
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

"""Encapsulate pacemaker-remote testing."""

import logging
import unittest
import xml.etree.ElementTree as ET

import zaza.model


class PacemakerRemoteTest(unittest.TestCase):
    """Encapsulate pacemaker-remote tests."""

    def test_check_nodes_online(self):
        """Test that all nodes are online."""
        status_cmd = 'crm status --as-xml'
        status_xml = zaza.model.run_on_leader('api', status_cmd)['Stdout']
        root = ET.fromstring(status_xml)
        for child in root:
            if child.tag == 'nodes':
                for node in child:
                    logging.info(
                        'Node {name} of type {type} is '
                        '{online}'.format(**node.attrib))
                    self.assertEqual(node.attrib['online'], "true")
