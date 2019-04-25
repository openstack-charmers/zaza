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

import mock
import unit_tests.utils as ut_utils
import zaza.openstack.utilities.file_assertions as file_assertions


class TestFileAssertionUtils(ut_utils.BaseTestCase):
    def setUp(self):
        super(TestFileAssertionUtils, self).setUp()
        # Patch all run_on_unit calls
        self.patch(
            'zaza.openstack.utilities.file_assertions.model.run_on_unit',
            new_callable=mock.MagicMock(),
            name='run_on_unit'
        )
        self._assert = mock.MagicMock()
        self._assert.assertEqual = mock.MagicMock()

    def test_path_glob(self):
        self.run_on_unit.return_value = {
            'Stdout': 'file-name root root 600'
        }
        file_details = {'path': '*'}
        file_assertions.assert_path_glob(
            self._assert, 'test/0', file_details)
        self.run_on_unit.assert_called_once_with(
            'test/0', 'bash -c "shopt -s -q globstar;'
            ' stat -c "%n %U %G %a" *"')

    def test_single_path(self):
        self.run_on_unit.return_value = {
            'Stdout': 'root root 600'
        }
        file_details = {'path': 'test'}
        file_assertions.assert_single_file(
            self._assert, 'test/0', file_details)
        self.run_on_unit.assert_called_once_with(
            'test/0', 'stat -c "%U %G %a" test')

    def test_error_message_glob(self):
        message = file_assertions._error_message(
            "Owner", "test/0", "root", "/path/to/something")
        self.assertEqual(
            message,
            "Owner is incorrect for /path/to/something on test/0: root")

    def test_error_message_single(self):

        message = file_assertions._error_message(
            "Owner", "test/0", "root")
        self.assertEqual(message, "Owner is incorrect on test/0: root")
