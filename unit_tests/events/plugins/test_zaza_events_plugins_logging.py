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

"""Unit tests for zaza.events.plugins.logging.py."""

import collections
import datetime
import mock
import sys

import unit_tests.utils as tests_utils


import zaza.events.plugins.logging as logging


class TestAutoConfigureFunction(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(logging, 'logger', name='mock_logger')
        self.patch_object(
            logging, 'get_plugin_manager', name='mock_get_plugin_manager')
        self.patch_object(
            logging, 'add_stdout_to_logger', name='mock_add_stdout_to_logger')
        self.patch_object(logging, 'make_writer', name='mock_make_writer')
        self.patch_object(
            logging, 'HandleToLogging', name='mock_HandleToLogging')
        self.mock_collection = mock.Mock()
        self.mock_logging_manager = mock.Mock()
        self.mock_event_logger = mock.Mock()

    def test_auto_configure_with_collection_empty_config(self):
        self.mock_get_plugin_manager.return_value = self.mock_logging_manager
        logging.auto_configure_with_collection(self.mock_collection)
        self.mock_get_plugin_manager.assert_called_once_with('DEFAULT')
        self.mock_collection.add_logging_manager.assert_called_once_with(
            self.mock_logging_manager)
        self.mock_logging_manager.get_logger.assert_called_once_with()

    def test_auto_configure_with_collection_non_default_logger_name(self):
        self.mock_get_plugin_manager.return_value = self.mock_logging_manager
        logging.auto_configure_with_collection(
            self.mock_collection,
            {
                'logger-name': 'a-logger',
            })
        self.mock_get_plugin_manager.assert_called_once_with('a-logger')
        self.mock_collection.add_logging_manager.assert_called_once_with(
            self.mock_logging_manager)
        self.mock_logging_manager.get_logger.assert_called_once_with()

    def test_auto_configure_with_collection_add_stdout(self):
        self.mock_get_plugin_manager.return_value = self.mock_logging_manager
        self.mock_logging_manager.get_logger.return_value = (
            self.mock_event_logger)
        logging.auto_configure_with_collection(
            self.mock_collection,
            {
                'log-to-stdout': True,
            })
        self.mock_get_plugin_manager.assert_called_once_with('DEFAULT')
        self.mock_collection.add_logging_manager.assert_called_once_with(
            self.mock_logging_manager)
        self.mock_logging_manager.get_logger.assert_called_once_with()
        self.mock_add_stdout_to_logger.assert_called_once_with(
            self.mock_event_logger)

    def test_auto_configure_with_collection_add_python_logging(self):
        self.mock_get_plugin_manager.return_value = self.mock_logging_manager
        self.mock_logging_manager.get_logger.return_value = (
            self.mock_event_logger)
        self.mock_HandleToLogging.return_value = "a-handle"
        self.mock_make_writer.return_value = "a-writer"

        logging.auto_configure_with_collection(
            self.mock_collection,
            {
                'log-to-python-logging': True,
            })

        self.mock_get_plugin_manager.assert_called_once_with('DEFAULT')
        self.mock_collection.add_logging_manager.assert_called_once_with(
            self.mock_logging_manager)
        self.mock_logging_manager.get_logger.assert_called_once_with()
        self.mock_HandleToLogging.assert_called_once_with(
            name='auto-logger', level=logging.logging.DEBUG,
            python_logger=logging.logger)
        self.mock_make_writer.assert_called_once_with(logging.LogFormats.LOG,
                                                      'a-handle')
        self.mock_event_logger.add_writers.assert_called_once_with('a-writer')

    def test_auto_configure_with_collection_add_python_logging_set_level(self):
        self.mock_get_plugin_manager.return_value = self.mock_logging_manager
        self.mock_logging_manager.get_logger.return_value = (
            self.mock_event_logger)
        self.mock_HandleToLogging.return_value = "a-handle"
        self.mock_make_writer.return_value = "a-writer"

        logging.auto_configure_with_collection(
            self.mock_collection,
            {
                'log-to-python-logging': True,
                'python-logging-level': 'info',
            })

        self.mock_get_plugin_manager.assert_called_once_with('DEFAULT')
        self.mock_collection.add_logging_manager.assert_called_once_with(
            self.mock_logging_manager)
        self.mock_logging_manager.get_logger.assert_called_once_with()
        self.mock_HandleToLogging.assert_called_once_with(
            name='auto-logger', level=logging.logging.INFO,
            python_logger=logging.logger)
        self.mock_make_writer.assert_called_once_with(logging.LogFormats.LOG,
                                                      'a-handle')
        self.mock_event_logger.add_writers.assert_called_once_with('a-writer')

    def test_auto_configure_with_collection_add_python_logging_invalid_level(
            self):
        self.mock_get_plugin_manager.return_value = self.mock_logging_manager
        self.mock_logging_manager.get_logger.return_value = (
            self.mock_event_logger)
        self.mock_HandleToLogging.return_value = "a-handle"
        self.mock_make_writer.return_value = "a-writer"

        with self.assertRaises(ValueError) as e:
            logging.auto_configure_with_collection(
                self.mock_collection,
                {
                    'log-to-python-logging': True,
                    'python-logging-level': 'bizarre',
                })
            self.assertIn("Invalid", str(e))
            self.assertIn('BIZARRE', str(e))


class TestModuleAPIFunctions(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(logging, '_loggers', new=dict(),
                          name='mock__loggers')

    def test_get_logger(self):
        self.patch_object(logging, 'EventLogger', name='mock_EventLogger')
        self.mock_EventLogger.return_value = 'a-logger'
        self.assertEqual(logging.get_logger(), 'a-logger')
        self.assertEqual(self.mock__loggers, {'DEFAULT': 'a-logger'})
        self.mock_EventLogger.assert_called_once_with('DEFAULT')

    def test_get_logger_named(self):
        self.patch_object(logging, 'EventLogger', name='mock_EventLogger')
        self.mock_EventLogger.return_value = 'a-logger'
        self.assertEqual(logging.get_logger('a-name'), 'a-logger')
        self.assertEqual(self.mock__loggers, {'a-name': 'a-logger'})
        self.mock_EventLogger.assert_called_once_with('a-name')

    def test_get_logger_already_exists(self):
        self.patch_object(logging, 'EventLogger', name='mock_EventLogger')
        self.mock__loggers['DEFAULT'] = 'default-logger'
        self.assertEqual(logging.get_logger(), 'default-logger')
        self.assertEqual(self.mock__loggers, {'DEFAULT': 'default-logger'})
        self.mock_EventLogger.assert_not_called()

    def test_get_logger_instance(self):
        mock_get_logger_instance = mock.Mock()
        # mocking chained calls is relatively hard; note duplicate of
        # 'get_logger_instance'.
        mock_get_logger_instance.get_logger_instance.return_value = (
            'a-logger-instance')
        self.patch_object(logging, 'get_logger', name='mock_get_logger',
                          new=mock.Mock())
        self.mock_get_logger.return_value = mock_get_logger_instance
        self.assertEqual(logging.get_logger_instance(), 'a-logger-instance')
        self.mock_get_logger.assert_called_once_with('DEFAULT')
        mock_get_logger_instance.get_logger_instance.assert_called_once_with()

    def test_get_logger_instance_with_name_and_args(self):
        mock_get_logger_instance = mock.Mock()
        # mocking chained calls is relatively hard; note duplicate of
        # 'get_logger_instance'.
        mock_get_logger_instance.get_logger_instance.return_value = (
            'a-logger-instance')
        self.patch_object(logging, 'get_logger', name='mock_get_logger',
                          new=mock.Mock())
        self.mock_get_logger.return_value = mock_get_logger_instance
        self.assertEqual(logging.get_logger_instance('thing', some='this'),
                         'a-logger-instance')
        self.mock_get_logger.assert_called_once_with('thing')
        mock_get_logger_instance.get_logger_instance.assert_called_once_with(
            some='this')

    def test_add_stdout_to_logger(self):
        self.patch_object(logging, 'WriterDefault', name='mock_WriterDefault')
        self.mock_WriterDefault.return_value = 'a-writer'
        self.patch_object(logging, 'get_logger', name='mock_get_logger',
                          new=mock.Mock())
        mock_logger = mock.Mock()
        self.mock_get_logger.return_value = mock_logger
        logging.add_stdout_to_logger()
        self.mock_get_logger.assert_called_once_with('DEFAULT')
        mock_logger.add_writers.assert_called_once_with('a-writer')
        self.mock_WriterDefault.assert_called_once_with(sys.stdout)

    def test_add_stdout_to_logger_non_default_name(self):
        self.patch_object(logging, 'WriterDefault', name='mock_WriterDefault')
        self.mock_WriterDefault.return_value = 'a-writer'
        self.patch_object(logging, 'get_logger', name='mock_get_logger',
                          new=mock.Mock())
        mock_logger = mock.Mock()
        self.mock_get_logger.return_value = mock_logger
        logging.add_stdout_to_logger('a-logger')
        self.mock_get_logger.assert_called_once_with('a-logger')
        mock_logger.add_writers.assert_called_once_with('a-writer')
        self.mock_WriterDefault.assert_called_once_with(sys.stdout)

    def test_add_stdout_to_logger_using_logger(self):
        self.patch_object(logging, 'WriterDefault', name='mock_WriterDefault')
        self.mock_WriterDefault.return_value = 'a-writer'

        class MyEventLogger(logging.EventLogger):

            def __init__(self):
                pass

            def add_writers(writer):
                pass

        self.patch_object(MyEventLogger, 'add_writers',
                          name='mock_add_writers')
        self.patch_object(logging, 'get_logger', name='mock_get_logger',
                          new=mock.Mock())
        mock_logger = mock.Mock()
        self.mock_get_logger.return_value = mock_logger
        logging.add_stdout_to_logger(MyEventLogger())
        self.mock_get_logger.assert_not_called()
        self.mock_add_writers.assert_called_once_with('a-writer')
        self.mock_WriterDefault.assert_called_once_with(sys.stdout)


class TestGetPluginManager(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(logging, '_logger_plugin_managers', new=dict(),
                          name='mock__logger_plugin_managers')

    def test_get_plugin_manager(self):
        self.patch_object(logging, 'LoggerPluginManager',
                          name='mock_LoggerPluginManager')
        self.mock_LoggerPluginManager.return_value = 'a-plugin-manager'
        self.assertEqual(logging.get_plugin_manager(), 'a-plugin-manager')
        self.assertEqual(self.mock__logger_plugin_managers,
                         {'DEFAULT': 'a-plugin-manager'})
        self.mock_LoggerPluginManager.assert_called_once_with(
            managed_name='DEFAULT')

    def test_get_plugin_manager_named(self):
        self.patch_object(logging, 'LoggerPluginManager',
                          name='mock_LoggerPluginManager')
        self.mock_LoggerPluginManager.return_value = 'a-plugin-manager'
        self.assertEqual(logging.get_plugin_manager('a-name'),
                         'a-plugin-manager')
        self.assertEqual(self.mock__logger_plugin_managers,
                         {'a-name': 'a-plugin-manager'})
        self.mock_LoggerPluginManager.assert_called_once_with(
            managed_name='a-name')

    def test_get_plugin_manager_already_exists(self):
        self.patch_object(logging, 'LoggerPluginManager',
                          name='mock_LoggerPluginManager')
        self.mock__logger_plugin_managers['DEFAULT'] = 'default-plugin-manager'
        self.assertEqual(logging.get_plugin_manager(),
                         'default-plugin-manager')
        self.assertEqual(self.mock__logger_plugin_managers,
                         {'DEFAULT': 'default-plugin-manager'})
        self.mock_LoggerPluginManager.assert_not_called()


class TestLoggerPluginManager(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.mock_collection_object = mock.Mock()
        self.mock_collection_object.logs_dir = "a-logs-dir"
        self.mock_collection_object.log_format = logging.LogFormats.InfluxDB
        self.mock_collection_object.collection = 'a-collection'
        self.patch('uuid.uuid4', name='mock_uuid4')
        self.mock_uuid4.return_value = '01234567890123456789'
        self.patch_object(logging, 'WriterFile', name='mock_WriterFile')
        self.mock_managed_writer = mock.Mock()
        self.mock_managed_writer.handle = 'a-handle'
        self.mock_WriterFile.return_value = self.mock_managed_writer
        self.patch_object(logging, 'make_writer', name='mock_make_writer')
        self.mock_make_writer.return_value = 'a-writer'
        self.patch_object(logging, 'get_logger', name='mock_get_logger')
        self.mock_event_logger = mock.Mock()
        self.mock_get_logger.return_value = self.mock_event_logger

    def test_init(self):
        lpm = logging.LoggerPluginManager(filename="some-file")
        self.assertEqual(lpm.filename, 'some-file')

    def test_configure_plugin(self):
        lpm = logging.LoggerPluginManager(
            managed_name='a-plugin',
            collection_object=self.mock_collection_object)
        lpm.configure_plugin()

        self.assertEqual(lpm.filename,
                         "a-logs-dir/a-collection_InfluxDB_23456789.log")
        self.mock_WriterFile.assert_called_once_with(
            logging.LogFormats.InfluxDB, lpm.filename)
        self.mock_make_writer.assert_called_once_with(
            logging.LogFormats.InfluxDB, 'a-handle')
        self.mock_get_logger.assert_called_once_with('a-plugin')
        self.mock_event_logger.add_writers.assert_called_once_with('a-writer')

    def test_get_logger(self):
        lpm = logging.LoggerPluginManager(
            managed_name='a-plugin',
            collection_object=self.mock_collection_object)
        self.assertEqual(lpm.get_logger(), self.mock_event_logger)

        self.mock_get_logger.assert_called_once_with('a-plugin')

    def test_event_logger_instance(self):
        lpm = logging.LoggerPluginManager(
            managed_name='a-plugin',
            collection_object=self.mock_collection_object)
        self.mock_event_logger.get_logger_instance.return_value = (
            'a-logger-instance')
        self.patch_object(lpm, 'get_logger', name='mock_lpm_get_logger')
        self.mock_lpm_get_logger.return_value = (
            self.mock_event_logger)

        def raise_(*args, **kwargs):
            raise Exception("bang")

        self.mock_get_logger.side_effect = raise_

        self.assertEqual(lpm.get_event_logger_instance(), 'a-logger-instance')
        self.mock_event_logger.get_logger_instance.assert_called_once_with(
            collection='a-collection', unit='a-plugin')

    def test_event_logger_instance_attribute_error(self):
        lpm = logging.LoggerPluginManager(
            managed_name='a-plugin',
            collection_object=self.mock_collection_object)
        self.mock_event_logger.get_logger_instance.return_value = (
            'a-logger-instance')
        self.patch_object(lpm, 'get_logger', name='mock_lpm_get_logger',
                          new=mock.MagicMock())

        def raise_(*args, **kwargs):
            raise AttributeError("bang")

        self.mock_lpm_get_logger.return_value.get_logger_instance.side_effect = raise_  # NOQA

        self.assertEqual(lpm.get_event_logger_instance(), 'a-logger-instance')
        self.mock_event_logger.get_logger_instance.assert_called_once_with()

    def test_finalise(self):
        lpm = logging.LoggerPluginManager(
            managed_name='a-plugin',
            collection_object=self.mock_collection_object)
        lpm.configure_plugin()

        self.mock_get_logger.reset_mock()
        lpm.finalise()

        self.mock_get_logger.assert_called_once_with(lpm.managed_name)
        self.mock_event_logger.remove_writer.assert_called_once_with(
            lpm._managed_writer)
        self.mock_managed_writer.close.assert_called_once_with()

    def test_finalise_no_writer(self):
        lpm = logging.LoggerPluginManager(
            managed_name='a-plugin',
            collection_object=self.mock_collection_object)
        self.patch_object(logging, 'logger', name='mock_logger')

        lpm.finalise()

        self.mock_get_logger.assert_not_called()

    def test_log_files(self):
        lpm = logging.LoggerPluginManager(
            managed_name='a-plugin',
            collection_object=self.mock_collection_object)
        lpm.configure_plugin()

        self.assertEqual(
            list(lpm.log_files())[0],
            ('a-plugin',
             logging.LogFormats.InfluxDB,
             'a-logs-dir/a-collection_InfluxDB_23456789.log'))

    def test_clean_up(self):
        lpm = logging.LoggerPluginManager(
            managed_name='a-plugin',
            collection_object=self.mock_collection_object)
        # call clean_up to get the coverage; it's a TODO item/Noop
        lpm.clean_up()

    def test_reset(self):
        lpm = logging.LoggerPluginManager(
            managed_name='a-plugin',
            collection_object=self.mock_collection_object)
        lpm.configure_plugin()

        self.patch_object(lpm, 'finalise', name='mock_lpm_finalise')

        lpm.reset()
        self.mock_lpm_finalise.assert_called_once_with()
        self.assertIsNone(lpm._managed_writer_file)
        self.assertIsNone(lpm._managed_writer)
        self.assertIsNone(lpm.filename)


class TestEventLogger(tests_utils.BaseTestCase):

    def test_init(self):
        ev = logging.EventLogger('a-logger')
        self.assertEqual(ev.name, 'a-logger')
        self.assertEqual(ev._writers, [])

    def test_get_logger_instance(self):
        self.patch_object(
            logging, 'LoggerInstance', name='mock_LoggerInstance')
        self.mock_LoggerInstance.return_value = 'a-logger-instance'
        ev = logging.EventLogger('a-logger')
        self.assertEqual(ev.get_logger_instance(thing='hello'),
                         'a-logger-instance')
        self.mock_LoggerInstance.assert_called_once_with(ev, thing='hello')

    def test__log(self):
        self.patch('datetime.datetime', name='mock_datetime')
        self.mock_datetime.now.return_value = 'a-timestamp'
        ev = logging.EventLogger('a-logger')
        self.patch_object(
            ev, '_validate_attrs', name='mock_ev__validate_attrs')
        mock_writer1 = mock.Mock()
        mock_writer2 = mock.Mock()
        ev._writers = [mock_writer1, mock_writer2]

        ev._log(logging.Events.START_TEST)

        self.mock_datetime.now.assert_called_once_with()
        self.mock_ev__validate_attrs.assert_called_once_with(
            dict(event='start', timestamp='a-timestamp'))
        mock_writer1.write.assert_called_once_with(
            newline=True, event='start', timestamp='a-timestamp')
        mock_writer2.write.assert_called_once_with(
            newline=True, event='start', timestamp='a-timestamp')

    def test__log_with_invalid_span_and_timestamp(self):
        self.patch('datetime.datetime', name='mock_datetime')
        self.mock_datetime.now.return_value = 'a-timestamp'
        ev = logging.EventLogger('a-logger')
        self.patch_object(
            ev, '_validate_attrs', name='mock_ev__validate_attrs')
        mock_writer1 = mock.Mock()
        ev._writers = [mock_writer1]
        mock_span = mock.Mock()

        ev._log(logging.Events.START_TEST, timestamp='my-timestamp',
                span=mock_span)

        self.mock_datetime.now.assert_not_called()
        self.mock_ev__validate_attrs.assert_called_once_with(
            dict(event='start', timestamp='my-timestamp', span=mock_span))
        mock_writer1.write.assert_called_once_with(
            newline=True, event='start', timestamp='my-timestamp',
            span=mock_span)

    def test__log_with_valid_span(self):
        self.patch('uuid.uuid4', name='mock_uuid4')
        self.mock_uuid4.return_value = 'my-uuid'
        self.patch('datetime.datetime', name='mock_datetime')
        self.mock_datetime.now.return_value = 'a-timestamp'
        ev = logging.EventLogger('a-logger')
        self.patch_object(
            ev, '_validate_attrs', name='mock_ev__validate_attrs')
        mock_writer1 = mock.Mock()
        ev._writers = [mock_writer1]
        span = logging.span(ev)

        ev._log(logging.Events.START_TEST, span=span)

        self.mock_datetime.now.assert_called_once_with()
        self.mock_ev__validate_attrs.assert_called_once_with(
            dict(event='start', timestamp='a-timestamp', uuid='my-uuid'))
        mock_writer1.write.assert_called_once_with(
            newline=True, event='start', timestamp='a-timestamp',
            uuid='my-uuid')

    def test__log_with_invalid_event(self):
        self.patch('datetime.datetime', name='mock_datetime')
        self.mock_datetime.now.return_value = 'a-timestamp'
        ev = logging.EventLogger('a-logger')
        self.patch_object(
            ev, '_validate_attrs', name='mock_ev__validate_attrs')
        mock_writer1 = mock.Mock()
        ev._writers = [mock_writer1]

        with self.assertRaises(AssertionError):
            ev._log('not-an-allowed-event')

        self.mock_datetime.now.assert_not_called()
        self.mock_ev__validate_attrs.assert_not_called()
        mock_writer1.write.assert_not_called()

    def test__validate_attrs(self):
        valid_keys = {
            'collection': 'a-collection',
            'timestamp': 'a-timestamp',
            'unit': 'a-unit',
            'comment': 'a-comment',
        }
        invalid_keys = collections.OrderedDict(
            (('not-valid', 'is-not-valid'),
             ('some-key', 'is-not-a-valid-key'),
             ))
        self.patch_object(logging, 'logger', name='mock_logging')
        ev = logging.EventLogger('a-logger')
        ev._validate_attrs(valid_keys)
        self.mock_logging.warning.assert_not_called()

        ev._validate_attrs(invalid_keys)
        self.mock_logging.warning.assert_called_once_with(
            mock.ANY, 'not-valid,some-key', mock.ANY)

        all_kwargs = collections.OrderedDict(valid_keys)
        all_kwargs.update(invalid_keys)
        self.mock_logging.reset_mock()
        ev._validate_attrs(all_kwargs)
        self.mock_logging.warning.assert_called_once_with(
            mock.ANY, 'not-valid,some-key', mock.ANY)

    def test_add_writers(self):
        self.patch_object(logging, 'logger', name='mock_logging')
        mock_writer1 = mock.Mock()
        mock_writer2 = mock.Mock()
        ev = logging.EventLogger('a-logger')

        ev.add_writers(mock_writer1, mock_writer2)

        self.assertEqual(ev._writers, [mock_writer1, mock_writer2])
        self.mock_logging.warning.assert_not_called()

        ev.add_writers(mock_writer1)
        self.assertEqual(ev._writers, [mock_writer1, mock_writer2])
        self.mock_logging.warning.assert_called_once_with(
            mock.ANY, [mock_writer1])

    def test_remove_writer(self):
        self.patch_object(logging, 'logger', name='mock_logging')
        mock_writer1 = mock.Mock()
        mock_writer2 = mock.Mock()
        ev = logging.EventLogger('a-logger')

        ev.add_writers(mock_writer1, mock_writer2)
        ev.remove_writer(mock_writer2)

        self.assertEqual(ev._writers, [mock_writer1])
        self.mock_logging.warning.assert_not_called()

        ev.remove_writer('not-one-of-the-writers')

        self.assertEqual(ev._writers, [mock_writer1])
        self.mock_logging.warning.assert_called_once_with(
            mock.ANY, 'not-one-of-the-writers')


class TestLoggerInstance(tests_utils.BaseTestCase):

    def test_init(self):
        li = logging.LoggerInstance('a-logger', some='thing')
        self.assertEqual(li.event_logger, 'a-logger')
        self.assertEqual(li.prefilled, dict(some='thing'))

    def test__add_in_prefilled(self):
        args = dict(a='1', b='2')
        li = logging.LoggerInstance('a-logger', some='thing')
        prefilled = li._add_in_prefilled(args)
        self.assertEqual(li.prefilled, dict(some='thing'))
        self.assertEqual(prefilled, dict(some='thing', a='1', b='2'))
        # now disrupt args; prefilled should NOT change
        args['b'] = '3'
        self.assertEqual(li.prefilled, dict(some='thing'))
        self.assertEqual(prefilled, dict(some='thing', a='1', b='2'))

    def test_prefill_with(self):
        args = dict(a='1', b='2')
        li = logging.LoggerInstance('a-logger', some='thing')
        li2 = li.prefill_with(**args)
        self.assertEqual(li.prefilled, dict(some='thing'))
        self.assertEqual(li2.prefilled, dict(some='thing', a='1', b='2'))
        self.assertEqual(li.event_logger, li2.event_logger)

    def test_log(self):
        mock_event_logger = mock.Mock()
        args = dict(a='1', b='2')
        li = logging.LoggerInstance(mock_event_logger, some='thing')
        li.log('an-event', **args)
        mock_event_logger._log.assert_called_once_with(
            'an-event', some='thing', a='1', b='2')

    def test_span(self):
        self.patch_object(logging, 'span', name='mock_span')
        self.mock_span.return_value = 'a-span'
        li = logging.LoggerInstance('a-logger', some='thing')
        span = li.span(comment='hello', a='1')
        self.assertEqual(span, 'a-span')
        self.mock_span.assert_called_once_with(li, comment='hello', a='1')


class TestSpanClass(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch('uuid.uuid4', name='mock_uuid4')
        self.mock_uuid4.return_value = 'a-uuid'
        self.mock_event_logger = mock.Mock()

    def test_init(self):
        span = logging.span(self.mock_event_logger, comment='Hello',
                            this='that')
        self.mock_uuid4.assert_called_once_with()
        self.assertEqual(span.event_logger_ref(), self.mock_event_logger)
        self.assertEqual(span.uuid, 'a-uuid')
        self.assertEqual(span.comment, 'Hello')
        self.assertEqual(span.kwargs, dict(this='that'))

    def test__kwargs(self):
        span = logging.span(
            self.mock_event_logger, comment='Hello', this='that')
        self.assertEqual(span._kwargs, dict(uuid='a-uuid', comment='Hello',
                                            this='that'))
        self.assertEqual(span.kwargs, dict(this='that'))

    def test_context_manager(self):
        with logging.span(
                self.mock_event_logger, comment='Hello', this='that'):
            self.mock_event_logger.log.assert_called_once_with(
                logging.Events.COMMENT, comment='Hello', this='that',
                span=logging.Span.BEFORE.value, uuid='a-uuid')
            self.mock_event_logger.reset_mock()

        self.mock_event_logger.log.assert_called_once_with(
            logging.Events.COMMENT, comment='Hello', this='that',
            span=logging.Span.AFTER.value, uuid='a-uuid')

    def test_context_manager_with_exception(self):
        with self.assertRaises(Exception):
            with logging.span(
                    self.mock_event_logger, comment='Hello', this='that'):
                self.mock_event_logger.log.assert_called_once_with(
                    logging.Events.COMMENT, comment='Hello', this='that',
                    span=logging.Span.BEFORE.value, uuid='a-uuid')
                self.mock_event_logger.reset_mock()
                raise Exception('bang')

        self.mock_event_logger.log.assert_called_once_with(
            logging.Events.EXCEPTION, comment='Hello', this='that',
            span=logging.Span.AFTER.value, uuid='a-uuid')


class TestMakeWriter(tests_utils.BaseTestCase):

    def test_make_writer(self):
        self.patch_object(logging, 'WriterCSV', name='mock_WriterCSV')
        self.patch_object(logging, 'WriterDefault', name='mock_WriterDefault')
        self.patch_object(
            logging, 'WriterLineProtocol', name='mock_WriterLineProtocol')

        self.mock_WriterCSV.return_value = 'csv'
        self.mock_WriterDefault.return_value = 'default'
        self.mock_WriterLineProtocol.return_value = 'line-protocol'

        self.assertEqual(
            logging.make_writer(logging.LogFormats.CSV, 'a-handle'), 'csv')
        self.mock_WriterCSV.assert_called_once_with('a-handle')
        self.assertEqual(
            logging.make_writer(logging.LogFormats.LOG, 'a-handle'), 'default')
        self.mock_WriterDefault.assert_called_once_with('a-handle')
        self.assertEqual(
            logging.make_writer(logging.LogFormats.InfluxDB, 'a-handle'),
            'line-protocol')
        self.mock_WriterLineProtocol.assert_called_once_with('a-handle')

        with self.assertRaises(AssertionError):
            logging.make_writer('not-a-log-format', 'a-handle')


class TestWriterFile(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch('atexit.register', name='mock_atexit_register')
        self.patch('os.remove', name='mock_os_remove')
        self.patch_object(logging, '_get_writers_log_dir',
                          name='mock__get_writers_log_dir')
        self.mock__get_writers_log_dir.return_value = '/some/dir'
        self.patch('uuid.uuid4', name='mock_uuid4')
        self.mock_uuid4.return_value = '0123456789' * 4

    def test_writer_file(self):
        with mock.patch('builtins.open') as mock_open:
            mock_handle = mock.Mock()
            mock_open.return_value = mock_handle
            wf = logging.WriterFile('a-writer', delete=True)
            self.assertEqual(wf.writer_, 'a-writer')
            self.assertEqual(wf.filename, '/some/dir/a-writer_23456789.log')
            self.assertEqual(wf.handle, mock_handle)
            self.assertTrue(wf.delete)
            mock_open.assert_called_once_with(
                '/some/dir/a-writer_23456789.log', 'w+t')
            self.mock_atexit_register.assert_called_once_with(wf.close)

            # now call close to make sure it cleans up.
            wf.close()
            mock_handle.flush.assert_called_once_with()
            mock_handle.close.assert_called_once_with()
            self.assertIsNone(wf.handle)
            self.mock_os_remove.assert_called_once_with(
                '/some/dir/a-writer_23456789.log')

    def test_writer_file_no_delete(self):
        with mock.patch('builtins.open') as mock_open:
            mock_handle = mock.Mock()
            mock_open.return_value = mock_handle
            wf = logging.WriterFile('a-writer')

            # now call close to make sure it cleans up.
            wf.close()
            mock_handle.flush.assert_called_once_with()
            mock_handle.close.assert_called_once_with()
            self.assertIsNone(wf.handle)
            self.mock_os_remove.assert_not_called()

    def test_writer_file_delete_doesnt_exist(self):
        with mock.patch('builtins.open') as mock_open:
            mock_handle = mock.Mock()
            mock_open.return_value = mock_handle
            wf = logging.WriterFile('a-writer', delete=True)
            sentinel = mock.Mock()

            def raise_(*args):
                sentinel.raised()
                raise FileNotFoundError('bang')

            self.mock_os_remove.side_effect = raise_

            # now call close to make sure it cleans up.
            wf.close()
            mock_handle.flush.assert_called_once_with()
            mock_handle.close.assert_called_once_with()
            self.assertIsNone(wf.handle)
            sentinel.raised.assert_called_once_with()


class TestGetWritersLogDir(tests_utils.BaseTestCase):

    def test__get_writers_log_dir(self):
        self.patch_object(logging, '_log_dir', name='mock__log_dir', new=None)
        logging._log_dir = None
        self.patch('tempfile.TemporaryDirectory',
                   name='mock_TemporaryDirectory')
        mock_tmp_dir = mock.Mock()
        mock_tmp_dir.name = '/some/dir'
        self.mock_TemporaryDirectory.return_value = mock_tmp_dir
        self.assertEqual(logging._get_writers_log_dir(), '/some/dir')
        self.mock_TemporaryDirectory.reset_mock()
        self.assertEqual(logging._get_writers_log_dir(), '/some/dir')
        self.mock_TemporaryDirectory.assert_not_called()


class TestWriterBase(tests_utils.BaseTestCase):

    def test_write(self):
        wb = logging.WriterBase('a-writer', 'a-handle')
        self.patch_object(wb, 'format', name='mock_wb_format')
        self.patch_object(wb, '_write_to_handle',
                          name='mock_wb__write_to_handle')
        self.mock_wb_format.return_value = 'formatted'

        wb.write(a='1', this='that')

        self.mock_wb_format.assert_called_once_with(a='1', this='that')
        self.mock_wb__write_to_handle.assert_called_once_with(
            'formatted', newline=True)

    def test_write_no_newline(self):
        wb = logging.WriterBase('a-writer', 'a-handle')
        self.patch_object(wb, 'format', name='mock_wb_format')
        self.patch_object(wb, '_write_to_handle',
                          name='mock_wb__write_to_handle')
        self.mock_wb_format.return_value = 'formatted'

        wb.write(a='1', this='that', newline=False)

        self.mock_wb_format.assert_called_once_with(a='1', this='that')
        self.mock_wb__write_to_handle.assert_called_once_with(
            'formatted', newline=False)

    def test_write_already_formatted_timestamp(self):
        wb = logging.WriterBase('a-writer', 'a-handle')
        self.patch_object(wb, 'format', name='mock_wb_format')
        self.patch_object(wb, '_write_to_handle',
                          name='mock_wb__write_to_handle')
        self.mock_wb_format.return_value = 'formatted'

        wb.write(a='1', this='that', timestamp='a-timestamp')

        self.mock_wb_format.assert_called_once_with(
            a='1', this='that', timestamp='a-timestamp')
        self.mock_wb__write_to_handle.assert_called_once_with(
            'formatted', newline=True)

    def test_write_already_timestamp(self):
        wb = logging.WriterBase('a-writer', 'a-handle')
        self.patch_object(wb, 'format', name='mock_wb_format')
        self.patch_object(wb, '_write_to_handle',
                          name='mock_wb__write_to_handle')
        self.mock_wb_format.return_value = 'formatted'
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50)

        wb.write(a='1', this='that', timestamp=ts)

        self.mock_wb_format.assert_called_once_with(
            a='1', this='that', timestamp='2021-01-02T10:21:50')
        self.mock_wb__write_to_handle.assert_called_once_with(
            'formatted', newline=True)

    def test_format(self):
        wb = logging.WriterBase('a-writer', 'a-handle')
        with self.assertRaises(NotImplementedError):
            wb.format(this='that')

    def test__write_to_handle(self):
        mock_handle = mock.Mock()
        wb = logging.WriterBase('a-writer', mock_handle)
        wb._write_to_handle('a message')
        mock_handle.write.assert_has_calls((
            mock.call('a message'),
            mock.call("\n")))

    def test__write_to_handle_included_newline(self):
        mock_handle = mock.Mock()
        wb = logging.WriterBase('a-writer', mock_handle)
        wb._write_to_handle("a message\n", newline=False)
        mock_handle.write.assert_called_once_with("a message\n")

    def test__write_to_handle_no_newline(self):
        mock_handle = mock.Mock()
        wb = logging.WriterBase('a-writer', mock_handle)
        wb._write_to_handle('a message', newline=False)
        mock_handle.write.assert_called_once_with('a message')


class TestWriterCSV(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.mock_handle = mock.Mock()

    def test__format_csv(self):
        w_csv = logging.WriterCSV(self.mock_handle)
        self.assertEqual(w_csv._format_csv('Hello'), '"Hello"')
        self.assertEqual(w_csv._format_csv('Hello "Jim".'), '"Hello ""Jim""."')
        self.assertEqual(w_csv._format_csv('"Hello"'), '"Hello"')

    def test__write_header(self):
        logging.WriterCSV(self.mock_handle)
        self.mock_handle.write.assert_has_calls((
            mock.call('"timestamp","collection","unit","item","event",'
                      '"uuid","comment","tags"'),
            mock.call("\n"),
        ))

    def test_format(self):
        w_csv = logging.WriterCSV(self.mock_handle)
        res = w_csv.format(timestamp='ts', collection='collection', random='r',
                           this='that')
        self.assertEqual(
            res,
            '"ts","collection","","","","","","random=""r"",this=""that"""')

    def test_format_with_tags(self):
        w_csv = logging.WriterCSV(self.mock_handle)
        res = w_csv.format(timestamp='ts', collection='collection', random='r',
                           this='that', tags=dict(a='t'))
        self.assertEqual(
            res,
            '"ts","collection","","","","","",'
            '"a=""t"",random=""r"",this=""that"""')


class TestWriterDefault(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.mock_handle = mock.Mock()

    def test_format(self):
        w_default = logging.WriterDefault(self.mock_handle)
        res = w_default.format(
            timestamp='ts', collection='collection', comment="hello",
            random='r', this='that')
        self.assertEqual(
            res,
            'ts collection "hello" tags=random="r",this="that"')

    def test_format_with_tags(self):
        w_default = logging.WriterDefault(self.mock_handle)
        res = w_default.format(
            timestamp='ts', collection='collection', random='r',
            this='that', tags=dict(a='t'))
        self.assertEqual(
            res,
            'ts collection tags=a="t",random="r",this="that"')


class TestWriterLineProtocol(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.mock_handle = mock.Mock()

    def test_write(self):
        self.patch_object(logging.WriterBase, 'write', name='mock_super_write')
        w_lp = logging.WriterLineProtocol(self.mock_handle)
        w_lp.write(timestamp='ts', collection='a-collection', unit='a-unit',
                   item='an-item', random='r', this='that')
        self.mock_super_write.assert_called_once_with(
            newline=True, fields=dict(unit='a-unit', item='an-item'),
            collection='a-collection', random='r', this='that',
            timestamp='ts')

    def test_write_with_timestamp(self):
        self.patch_object(logging.WriterBase, 'write', name='mock_super_write')
        w_lp = logging.WriterLineProtocol(self.mock_handle)
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50)
        w_lp.write(timestamp=ts, collection='a-collection', unit='a-unit',
                   item='an-item', random='r', this='that')
        self.mock_super_write.assert_called_once_with(
            newline=True, fields=dict(unit='a-unit', item='an-item'),
            collection='a-collection', random='r', this='that',
            timestamp='1609582910000000us')

    def test_write_with_no_timestamp(self):
        self.patch_object(logging.WriterBase, 'write', name='mock_super_write')
        w_lp = logging.WriterLineProtocol(self.mock_handle)
        w_lp.write(collection='a-collection', unit='a-unit',
                   item='an-item', random='r', this='that')
        self.mock_super_write.assert_called_once_with(
            newline=True, fields=dict(unit='a-unit', item='an-item'),
            collection='a-collection', random='r', this='that')

    def test_format(self):
        w_lp = logging.WriterLineProtocol(self.mock_handle)
        res = w_lp.format(
            timestamp='ts', collection='collection', comment="hello",
            fields=dict(unit='u', item='item'),
            random='r', this='that')
        self.assertEqual(
            res,
            'collection,comment=hello,random=r,this=that '
            'item="item",unit="u" ts')


class TestFormatFunctions(tests_utils.BaseTestCase):

    def test_format_value(self):
        self.assertEqual(logging.format_value(1), '"1"')
        self.assertEqual(logging.format_value(1, tag=True), '1')
        self.assertEqual(logging.format_value('this'), '"this"')
        self.assertEqual(logging.format_value('"this"'), '"this"')
        self.assertEqual(logging.format_value('this', tag=True), 'this')
        self.assertEqual(logging.format_value('this one', tag=True),
                         'this-one')

    def test_format_dict(self):
        with self.assertRaises(AssertionError):
            logging.format_dict("this")
        self.assertEqual(logging.format_dict(dict(a="1", b="2")),
                         'a="1",b="2"')
        self.assertEqual(logging.format_dict(dict(b="2", a="1"), tag=True),
                         'a=1,b=2')


class TestHandleToLogging(tests_utils.BaseTestCase):

    def test_write(self):
        mock_logger = mock.Mock()
        htl = logging.HandleToLogging('a-handle', level=logging.logging.INFO,
                                      python_logger=mock_logger)
        htl.write("This is a message\n")
        mock_logger.log.assert_called_once_with(
            logging.logging.INFO, mock.ANY, "This is a message")

    def test_write_module_logger(self):
        self.patch_object(logging, 'logger', name='mock_logger')
        htl = logging.HandleToLogging(
            'a-handle', level=logging.logging.WARNING)
        htl.write("This is a message\n")
        self.mock_logger.log.assert_called_once_with(
            logging.logging.WARNING, mock.ANY, "This is a message")

    def test_write_module_logger_no_message(self):
        self.patch_object(logging, 'logger', name='mock_logger')
        htl = logging.HandleToLogging(
            'a-handle', level=logging.logging.WARNING)
        htl.write("\n")
        self.mock_logger.log.assert_not_called()

    def test_flush(self):
        # HandleToLogging.flush() is a noop; call it for coverage
        htl = logging.HandleToLogging(
            'a-handle', level=logging.logging.WARNING)
        htl.flush()

    def test_close(self):
        # HandleToLogging.close() is a noop; call it for coverage
        htl = logging.HandleToLogging(
            'a-handle', level=logging.logging.WARNING)
        htl.close()
