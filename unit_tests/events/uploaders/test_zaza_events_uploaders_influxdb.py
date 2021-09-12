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

"""Unit tests for zaza.events.uploaders.influxdb"""

import mock

import unit_tests.utils as tests_utils

import zaza.events.uploaders.influxdb as influxdb


class TestInfluxDBUploader(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.mock_collection = mock.Mock()
        self.patch_object(influxdb, 'requests', name='mock_requests')
        self.patch_object(influxdb, 'logger', name='mock_logger')

    def test_upload_invalid_spec_s3(self):
        with self.assertRaises(AssertionError):
            influxdb.upload({'type': 's3'}, self.mock_collection)

    def test_upload_invalid_spec_no_url(self):
        with self.assertRaises(KeyError):
            influxdb.upload({'type': 'InfluxDB',
                             'raise-exceptions': True}, self.mock_collection)
            self.mock_logger.error.assert_called_once_with(
                "No url supplied to upload for InfluxDB.")

        self.mock_logger.reset_mock()
        influxdb.upload({'type': 'InfluxDB'}, self.mock_collection)
        self.mock_logger.error.assert_called_once_with(
            "No url supplied to upload for InfluxDB.")

    def test_upload_invalid_spec_no_db(self):
        with self.assertRaises(KeyError):
            influxdb.upload({'type': 'InfluxDB',
                             'url': '1.2.3.4:80',
                             'raise-exceptions': True}, self.mock_collection)
            self.mock_logger.error.assert_called_once_with(
                "No database supplied to upload for InfluxDB.")

        self.mock_logger.reset_mock()
        influxdb.upload({'type': 'InfluxDB',
                         'url': '1.2.3.4:80'}, self.mock_collection)
        self.mock_logger.error.assert_called_once_with(
            "No database supplied to upload for InfluxDB.")

    def test_upload_invalid_spec_bad_resolution(self):
        with self.assertRaises(KeyError):
            influxdb.upload({'type': 'InfluxDB',
                             'url': '1.2.3.4:80',
                             'database': 'db-name',
                             'timestamp-resolution': 'p',
                             'raise-exceptions': True}, self.mock_collection)
            self.mock_logger.error.assert_called_once_with(mock.ANY, 'p')

        self.mock_logger.reset_mock()
        influxdb.upload({'type': 'InfluxDB',
                         'url': '1.2.3.4:80',
                         'database': 'db-name',
                         'timestamp-resolution': 'p'}, self.mock_collection)
        self.mock_logger.error.assert_called_once_with(mock.ANY, 'p')

    def test_upload_successful(self):
        mock_cm = mock.MagicMock()
        events = (
            ('1.log', '1'),
            ('2.log', '2'),
            ('1.log', '3'),
            ('2.log', '4'),
        )
        mock_cm.__enter__.return_value = iter(events)
        self.mock_collection.events.return_value = mock_cm

        mock_request_result = mock.Mock()
        mock_request_result.status_code = influxdb.requests.codes.ok
        self.mock_requests.post.return_value = mock_request_result

        with mock.patch.object(influxdb, 'expand_vars',
                               wraps=influxdb.expand_vars) as mock_expand_vars:
            influxdb.upload({'type': 'InfluxDB',
                             'url': '1.2.3.4:80',
                             'database': 'db-name',
                             'user': 'a-user',
                             'password': 'a-password',
                             'batch-size': 2,
                             'raise-exceptions': True},
                            self.mock_collection)
            mock_expand_vars.assert_has_calls((
                mock.call({}, '1.2.3.4:80'),
                mock.call({}, 'db-name'),
                mock.call({}, 'a-user'),
                mock.call({}, 'a-password')))
            self.mock_requests.post.assert_has_calls((
                mock.call(
                    '1.2.3.4:80/write?db=db-name&precision=u'
                    '&u=a-user&p=a-password',
                    data='1\n2'),
                mock.call(
                    '1.2.3.4:80/write?db=db-name&precision=u'
                    '&u=a-user&p=a-password',
                    data='3\n4')))

    def test_upload_exception_on_post(self):
        class CustomException(Exception):
            pass

        def raise_(*args, **kwargs):
            raise CustomException('bang')

        mock_cm = mock.MagicMock()
        events = (
            ('1.log', '1'),
            ('2.log', '2'),
            ('1.log', '3'),
            ('2.log', '4'),
        )
        mock_cm.__enter__.return_value = iter(events)
        self.mock_collection.events.return_value = mock_cm
        self.mock_requests.post.side_effect = raise_

        with mock.patch.object(influxdb, 'expand_vars',
                               wraps=influxdb.expand_vars):
            influxdb.upload({'type': 'InfluxDB',
                             'url': '1.2.3.4:80',
                             'database': 'db-name',
                             'user': 'a-user',
                             'password': 'a-password',
                             'batch-size': 2,
                             'raise-exceptions': False},
                            self.mock_collection)

            self.mock_requests.post.assert_called_once_with(
                '1.2.3.4:80/write?db=db-name&precision=u'
                '&u=a-user&p=a-password',
                data='1\n2')
            self.mock_logger.error.assert_called_once_with(mock.ANY, 'bang')

    def test_upload_exception_on_post_raised(self):
        class CustomException(Exception):
            pass

        def raise_(*args, **kwargs):
            raise CustomException('bang')

        mock_cm = mock.MagicMock()
        events = (
            ('1.log', '1'),
            ('2.log', '2'),
            ('1.log', '3'),
            ('2.log', '4'),
        )
        mock_cm.__enter__.return_value = iter(events)
        self.mock_collection.events.return_value = mock_cm
        self.mock_requests.post.side_effect = raise_

        with mock.patch.object(influxdb, 'expand_vars',
                               wraps=influxdb.expand_vars):
            with self.assertRaises(CustomException):
                influxdb.upload({'type': 'InfluxDB',
                                 'url': '1.2.3.4:80',
                                 'database': 'db-name',
                                 'user': 'a-user',
                                 'password': 'a-password',
                                 'batch-size': 2,
                                 'raise-exceptions': True},
                                self.mock_collection)

            self.mock_requests.post.assert_called_once_with(
                '1.2.3.4:80/write?db=db-name&precision=u'
                '&u=a-user&p=a-password',
                data='1\n2')
            self.mock_logger.error.assert_called_once_with(mock.ANY, 'bang')

    def test_upload_bad_result_code(self):
        mock_cm = mock.MagicMock()
        events = (
            ('1.log', '1'),
            ('2.log', '2'),
            ('1.log', '3'),
            ('2.log', '4'),
        )
        mock_cm.__enter__.return_value = iter(events)
        self.mock_collection.events.return_value = mock_cm

        mock_request_result = mock.Mock()
        mock_request_result.status_code = influxdb.requests.codes.not_found
        self.mock_requests.post.return_value = mock_request_result

        with mock.patch.object(influxdb, 'expand_vars',
                               wraps=influxdb.expand_vars):
            influxdb.upload({'type': 'InfluxDB',
                             'url': '1.2.3.4:80',
                             'database': 'db-name',
                             'user': 'a-user',
                             'password': 'a-password',
                             'batch-size': 2,
                             'raise-exceptions': False},
                            self.mock_collection)

            self.mock_requests.post.assert_called_once_with(
                '1.2.3.4:80/write?db=db-name&precision=u'
                '&u=a-user&p=a-password',
                data='1\n2')
            self.mock_logger.error.assert_has_calls((
                mock.call('Batch upload failed.  status_code: %s', mock.ANY),
                mock.call('Abandoning batch upload to InfluxDB'),
            ))

    def test_upload_bad_result_code_with_raise(self):
        class CustomException(Exception):
            pass

        def raise_(*args, **kwargs):
            raise CustomException('bang')

        mock_cm = mock.MagicMock()
        events = (
            ('1.log', '1'),
            ('2.log', '2'),
            ('1.log', '3'),
            ('2.log', '4'),
        )
        mock_cm.__enter__.return_value = iter(events)
        self.mock_collection.events.return_value = mock_cm

        mock_request_result = mock.Mock()
        mock_request_result.status_code = influxdb.requests.codes.not_found
        mock_request_result.raise_for_status.side_effect = raise_
        self.mock_requests.post.return_value = mock_request_result

        with mock.patch.object(influxdb, 'expand_vars',
                               wraps=influxdb.expand_vars):
            with self.assertRaises(CustomException):
                influxdb.upload({'type': 'InfluxDB',
                                 'url': '1.2.3.4:80',
                                 'database': 'db-name',
                                 'user': 'a-user',
                                 'password': 'a-password',
                                 'batch-size': 2,
                                 'raise-exceptions': True},
                                self.mock_collection)

            self.mock_requests.post.assert_called_once_with(
                '1.2.3.4:80/write?db=db-name&precision=u'
                '&u=a-user&p=a-password',
                data='1\n2')
            self.mock_logger.error.assert_called_once_with(
                'Batch upload failed.  status_code: %s', mock.ANY)
