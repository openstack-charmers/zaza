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

"""Unit tests for zaza.events.uploaders.__init__"""

import mock

import unit_tests.utils as tests_utils

import zaza.events.uploaders as uploaders


class TestUploadersInit(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(uploaders, 'get_option', name='mock_get_option')
        self.patch_object(uploaders, 'logger', name='mock_logger')
        self.patch_object(uploaders, 'upload_influxdb',
                          name='mock_upload_influxdb')

    def test_upload_collection_by_config__no_config(self):
        self.mock_get_option.return_value = None
        uploaders.upload_collection_by_config('a-collection')
        self.mock_logger.error.assert_called_once_with(mock.ANY, None)

    def test_upload_collection_by_config__config_is_str(self):
        self.mock_get_option.return_value = 'a-string-is-bad'
        uploaders.upload_collection_by_config('a-collection')
        self.mock_logger.error.assert_called_once_with(
            mock.ANY, 'a-string-is-bad')

    def test_upload_collection_by_config__config_is_str_list(self):
        self.mock_get_option.return_value = ['a-list-of-strings-is-bad']
        uploaders.upload_collection_by_config('a-collection')
        self.mock_logger.error.assert_called_once_with(
            mock.ANY, 'a-list-of-strings-is-bad')

    def test_upload_collection_by_config__config_has_no_type(self):
        self.mock_get_option.return_value = [{'some': 'config'}]
        uploaders.upload_collection_by_config('a-collection')
        self.mock_logger.error.assert_called_once_with(
            mock.ANY, {'some': 'config'})

    def test_upload_collection_by_config__config_type_is_not_str(self):
        self.mock_get_option.return_value = [{'type': 1234}]
        uploaders.upload_collection_by_config('a-collection')
        self.mock_logger.error.assert_called_once_with(
            mock.ANY, 1234)

    def test_upload_collection_by_config__config_type_is_not_influxdb(self):
        self.mock_get_option.return_value = [{'type': 'S3'}]
        uploaders.upload_collection_by_config('a-collection')
        self.mock_logger.error.assert_called_once_with(
            mock.ANY, 's3')

    def test_upload_collection_by_config__config_type_is_influxdb(self):
        self.mock_get_option.return_value = [{'type': 'InfluxDB'}]
        uploaders.upload_collection_by_config('a-collection')
        self.mock_logger.error.assert_not_called()
        self.mock_upload_influxdb.assert_called_once_with(
            {'type': 'InfluxDB'}, 'a-collection', None)
