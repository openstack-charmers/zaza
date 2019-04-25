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

# import mock

import unit_tests.utils as ut_utils
import zaza.openstack.utilities.bundle as bundle

import yaml

TEST_BUNDLE_WITH_PLACEMENT = """
machines:
  '0':
    series: bionic
  '1':
    series: bionic
  '2':
    series: bionic
relations:
- - ceph-osd:mon
  - ceph-mon:osd
series: bionic
services:
  ceph-mon:
    annotations:
      gui-x: '750'
      gui-y: '500'
    charm: cs:ceph-mon-26
    num_units: 3
    options:
      expected-osd-count: 3
      source: cloud:bionic-rocky
    to:
    - lxd:0
    - lxd:1
    - lxd:2
  ceph-osd:
    annotations:
      gui-x: '1000'
      gui-y: '500'
    charm: cs:ceph-osd-269
    num_units: 3
    options:
      osd-devices: /dev/sdb
      source: cloud:bionic-rocky
    to:
    - '0'
    - '1'
    - '2'
"""


TEST_BUNDLE_WITHOUT_PLACEMENT = """
relations:
- - ceph-osd:mon
  - ceph-mon:osd
series: bionic
services:
  ceph-mon:
    annotations:
      gui-x: '750'
      gui-y: '500'
    charm: cs:ceph-mon-26
    num_units: 3
    options:
      expected-osd-count: 3
      source: cloud:bionic-rocky
  ceph-osd:
    annotations:
      gui-x: '1000'
      gui-y: '500'
    charm: cs:ceph-osd-269
    num_units: 3
    options:
      osd-devices: /dev/sdb
      source: cloud:bionic-rocky
"""


class TestUtilitiesBundle(ut_utils.BaseTestCase):

    def test_flatten_bundle(self):
        self.maxDiff = 1500
        input_yaml = yaml.safe_load(TEST_BUNDLE_WITH_PLACEMENT)
        flattened = bundle.remove_machine_specification(input_yaml)
        expected = yaml.safe_load(TEST_BUNDLE_WITHOUT_PLACEMENT)

        self.assertEqual(expected, flattened)

    def test_add_series(self):
        self.maxDiff = 1500
        input_yaml = yaml.safe_load(TEST_BUNDLE_WITH_PLACEMENT)
        input_yaml.pop('series', None)
        flattened = bundle.remove_machine_specification(input_yaml)
        expected = yaml.safe_load(TEST_BUNDLE_WITHOUT_PLACEMENT)

        self.assertEqual(expected, flattened)

    def test_parser(self):
        args = bundle.parse_args([
            '-i', 'bundle.yaml'])
        self.assertEqual(args.input, 'bundle.yaml')
        self.assertEqual(args.output, '/dev/stdout')

    def test_parser_output(self):
        args = bundle.parse_args([
            '-i', 'bundle.yaml',
            '-o', 'bundle_out.yaml'])
        self.assertEqual(args.input, 'bundle.yaml')
        self.assertEqual(args.output, 'bundle_out.yaml')
