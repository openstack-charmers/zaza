# Copyright 2021 Canonical Ltd.
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

"""Unit tests for zaza.plugins.events.py."""

import unit_tests.utils as tests_utils


import zaza.plugins.events as events


class TestPluginsEvents(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(events, 'get_option', name='mock_get_option')
        self.patch_object(events, 'logger', name='mock_logger')
        self.patch_object(events, 'EventsPlugin', name='mock_EventsPlugin')

    def test_configure_none(self):
        self.mock_get_option.return_value = None

        events.configure('env-deployment')

        self.mock_get_option.assert_called_once_with(
            'zaza-events', raise_exception=False)

        self.mock_EventsPlugin.assert_not_called()

    def test_configure_good_to_go(self):
        self.mock_get_option.return_value = 'configured'

        events.configure('env-deployment')

        self.mock_get_option.assert_called_once_with(
            'zaza-events', raise_exception=False)

        self.mock_EventsPlugin.assert_called_once_with('env-deployment')
