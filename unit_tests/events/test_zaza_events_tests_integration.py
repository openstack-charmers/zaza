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

"""Unit tests for zaza.events.tests_integration."""

import datetime
import mock

import unit_tests.utils as tests_utils


import zaza.events.tests_integration as ti


class TestTestsIntegration(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(ti, 'get_option', name='mock_get_option')
        self.mock_get_option.side_effect = self._get_option
        self._options = {}

    def _get_option(self, key, default=None):
        try:
            return self._options[key]
        except KeyError:
            return default

    def test_get_global_events_logging_manager(self):
        self.patch_object(ti, 'get_plugin_manager',
                          name='mock_get_plugin_manager')
        self.mock_get_plugin_manager.return_value = 'a-manager'
        self.assertEqual(ti.get_global_events_logging_manager(), 'a-manager')
        self.mock_get_plugin_manager.assert_called_once_with('DEFAULT')

    def test_get_global_events_logging_manager_named(self):
        self.patch_object(ti, 'get_plugin_manager',
                          name='mock_get_plugin_manager')
        self._options['zaza-events.modules.logging.logger-name'] = 'a-name'
        self.mock_get_plugin_manager.return_value = 'a-manager'
        self.assertEqual(ti.get_global_events_logging_manager(), 'a-manager')
        self.mock_get_plugin_manager.assert_called_once_with('a-name')

    def test_get_global_events_logging_manager_by_collection(self):
        self.patch_object(ti, 'get_plugin_manager',
                          name='mock_get_plugin_manager')
        self._options['zaza-events.collection-name'] = 'a-collection'
        self.mock_get_plugin_manager.return_value = 'a-manager'
        self.assertEqual(ti.get_global_events_logging_manager(), 'a-manager')
        self.mock_get_plugin_manager.assert_called_once_with('a-collection')

    def test_get_global_event_logger_instance(self):
        self.patch_object(ti, 'get_global_events_logging_manager',
                          new=mock.MagicMock(),
                          name='mock_get_global_events_logging_manager')
        self.mock_get_global_events_logging_manager \
            .return_value \
            .get_event_logger_instance.return_value = 'an-instance'
        self.assertEqual(ti.get_global_event_logger_instance(), 'an-instance')

