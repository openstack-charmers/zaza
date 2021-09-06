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

"""Unit tests for zaza.plugins.__init__.py."""

import mock

import unit_tests.utils as tests_utils


import zaza.plugins as plugins


class TestPlugins__init__(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(plugins, 'get_option', name='mock_get_option')
        self.patch_object(plugins, 'logger', name='mock_logger')
        self.patch_object(plugins.utils, 'get_class', name='mock_get_class')

    def test_find_and_configure_plugins_noop(self):
        self.mock_get_option.return_value = None

        plugins.find_and_configure_plugins("env_deployments")

        self.mock_get_option.assert_called_once_with('plugins')
        self.mock_get_class.assert_not_called()

    def test_find_and_configure_plugins_with_empty_iterable(self):
        self.mock_get_option.return_value = tuple()

        plugins.find_and_configure_plugins("env_deployments")

        self.mock_get_option.assert_called_once_with('plugins')
        self.mock_get_class.assert_not_called()

        self.mock_get_option.return_value = []
        plugins.find_and_configure_plugins("env_deployments")
        self.mock_get_class.assert_not_called()

    def test_find_and_configure_plugins_with_not_str_or_iterable(self):
        self.mock_get_option.return_value = 3

        plugins.find_and_configure_plugins("env_deployments")

        self.mock_get_option.assert_called_once_with('plugins')
        self.mock_get_class.assert_not_called()

    def test_find_and_configure_plugins_with_list(self):
        self.mock_get_option.return_value = ["a", "b"]
        mock_callable1 = mock.Mock()
        mock_callable2 = mock.Mock()
        self.mock_get_class.side_effect = [mock_callable1, mock_callable2]

        plugins.find_and_configure_plugins("env_deployments")

        self.mock_get_class.assert_has_calls((
            mock.call("a"),
            mock.call("b")))
        mock_callable1.assert_called_once_with("env_deployments")
        mock_callable2.assert_called_once_with("env_deployments")

    def test_find_and_configure_plugins_with_str(self):
        self.mock_get_option.return_value = "a"
        mock_callable1 = mock.Mock()
        self.mock_get_class.return_value = mock_callable1

        plugins.find_and_configure_plugins("env_deployments")

        self.mock_get_class.assert_called_once_with("a")
        mock_callable1.assert_called_once_with("env_deployments")

    def test_find_and_configure_plugins_plugin_raises_exception(self):
        self.mock_get_option.return_value = "a"

        def raises_(self):
            raise Exception("hello")

        mock_callable1 = mock.Mock()
        mock_callable1.side_effect = raises_
        self.mock_get_class.return_value = mock_callable1

        with self.assertRaises(Exception):
            plugins.find_and_configure_plugins("env_deployments")
