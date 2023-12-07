# Copyright 2023 Canonical Ltd.
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

import json
import unittest

import unit_tests.utils as ut_utils
import zaza.utilities.launchpad as launchpad


class TestUtilitiesLaunchpad(ut_utils.BaseTestCase):

    def test_get_ubuntu_series(self):
        self.patch_object(launchpad.requests, 'get')
        expect = {'entries': {}}
        r = unittest.mock.MagicMock()
        r.text = json.dumps(expect)
        self.get.return_value = r
        self.assertEquals(
            launchpad.get_ubuntu_series(),
            expect,
        )
        self.get.assert_called_once_with(
            'https://api.launchpad.net/devel/ubuntu/series')

    def test_get_ubuntu_series_by_version(self):
        self.patch_object(launchpad, 'get_ubuntu_series')

        self.get_ubuntu_series.return_value = {
            'entries': [{'version': 'fakeVersion'}]}

        self.assertEquals(
            launchpad.get_ubuntu_series_by_version(),
            {'fakeVersion': {'version': 'fakeVersion'}})

    def test_get_ubuntu_series_by_name(self):
        self.patch_object(launchpad, 'get_ubuntu_series')

        self.get_ubuntu_series.return_value = {
            'entries': [{'name': 'fakeName'}]}

        self.assertEquals(
            launchpad.get_ubuntu_series_by_name(),
            {'fakeName': {'name': 'fakeName'}})
