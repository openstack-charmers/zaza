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

"""Unit tests for zaza.events.plugins.__init__.py."""

import datetime
import mock
import os
import tempfile

import unit_tests.utils as tests_utils


import zaza.events.plugins as plugins


class TestPluginManagerBase(tests_utils.BaseTestCase):

    def test__init__(self):
        p = plugins.PluginManagerBase(collection_object='hello')
        self.assertEqual(p.managed_name, 'DEFAULT')
        self.assertEqual(p.collection_object, 'hello')

    def test_configure_plugin(self):
        p = plugins.PluginManagerBase()
        with self.assertRaises(NotImplementedError):
            p.configure_plugin()

    def test_collection_property(self):
        mock_collection_object = mock.Mock()
        mock_collection_object.collection = 'my-collection'
        p = plugins.PluginManagerBase(collection_object=mock_collection_object)
        self.assertEqual(p.collection, 'my-collection')

    def test_logs_dir_property(self):
        mock_collection_object = mock.Mock()
        mock_collection_object.logs_dir = 'my-logs'
        p = plugins.PluginManagerBase(collection_object=mock_collection_object)
        self.assertEqual(p.logs_dir, 'my-logs')

    def test_log_format_property(self):
        mock_collection_object = mock.Mock()
        mock_collection_object.log_format = 'log-format'
        p = plugins.PluginManagerBase(collection_object=mock_collection_object)
        self.assertEqual(p.log_format, 'log-format')

    def test_finalise(self):
        p = plugins.PluginManagerBase()
        with self.assertRaises(NotImplementedError):
            p.finalise()

    def test_log_files(self):
        p = plugins.PluginManagerBase()
        with self.assertRaises(NotImplementedError):
            p.log_files()

    def test_clean_up(self):
        p = plugins.PluginManagerBase()
        with self.assertRaises(NotImplementedError):
            p.clean_up()

    def test_reset(self):
        p = plugins.PluginManagerBase()
        with self.assertRaises(NotImplementedError):
            p.reset()
