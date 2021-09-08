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

"""Unit tests for zaza.events.collection."""

import datetime
import mock
import os
import tempfile

import unit_tests.utils as tests_utils


import zaza.events.collection as collection


class TestEventsGetCollection(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(collection, 'get_option', name='mock_get_option')
        self.patch_object(collection, '_collections', name='mock__collections',
                          new={})
        self.patch_object(collection, 'Collection', name='mock_Collection')

    def test_get_collection_param_name_is_none(self):
        self.mock_get_option.return_value = 'collection-name'
        self.mock__collections['collection-name'] = 'a-collection'

        self.assertEqual(collection.get_collection(), 'a-collection')
        self.mock_get_option.assert_called_once_with(
            'zaza-events.collection-name', 'DEFAULT')
        self.mock_Collection.assert_not_called()

    def test_get_colection_param_name_is_not_none(self):
        self.mock_get_option.return_value = 'collection-name'
        self.mock__collections['mine'] = 'a-collection2'

        self.assertEqual(collection.get_collection('mine'), 'a-collection2')
        self.mock_get_option.assert_not_called()
        self.mock_Collection.assert_not_called()

    def test_get_collection_new_collection_needed(self):
        self.mock_get_option.return_value = 'collection-name'
        self.mock_Collection.return_value = 'new-collection'

        self.assertEqual(collection.get_collection(), 'new-collection')
        self.mock_get_option.assert_called_once_with(
            'zaza-events.collection-name', 'DEFAULT')
        self.mock_Collection.assert_called_once_with(name='collection-name')
        self.assertEqual(self.mock__collections,
                         {'collection-name': 'new-collection'})


class TestCollectionClass(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch('tempfile.mkdtemp', name='mock_mkdtemp')

    def test_collection_init(self):
        c = collection.Collection(
            name='a-name',
            collection='a-collection',
            description='a-description',
            logs_dir='logs',
            log_format=None)
        self.assertEqual(c.name, 'a-name')
        self.assertEqual(c.collection, 'a-collection')
        self.assertEqual(c.description, 'a-description')
        self.assertEqual(c.logs_dir, 'logs')
        self.assertEqual(c.log_format, collection.LogFormats.InfluxDB)

    def test__ensure_logs_dir_is_not_none(self):
        self.mock_mkdtemp.return_value = "temp-logs"
        c = collection.Collection(logs_dir='logs')
        c._ensure_logs_dir()
        self.assertEqual(c.logs_dir, 'logs')
        self.mock_mkdtemp.assert_not_called()

    def test__ensure_logs_dir_is_none(self):
        self.mock_mkdtemp.return_value = 'temp-logs'
        c = collection.Collection()
        c._ensure_logs_dir()
        self.assertEqual(c.logs_dir, 'temp-logs')
        self.mock_mkdtemp.assert_called_once_with()

    def test_add_logging_manager(self):
        self.mock_mkdtemp.return_value = 'temp-logs'
        manager = mock.Mock()
        c = collection.Collection()
        c.log_format = None
        c.add_logging_manager(manager)

        self.assertIn(manager, c._event_managers)
        self.assertEqual(c.log_format, collection.LogFormats.InfluxDB)
        manager.configure.assert_called_once_with(collection_object=c)
        self.assertEqual(c.logs_dir, 'temp-logs')
        manager.configure_plugin.assert_called_once_with()

        # add it again to ensure that it doesn't get added again.
        manager.reset_mock()
        c.add_logging_manager(manager)
        manager.configure.assert_not_called()
        self.assertEqual(c.logs_dir, 'temp-logs')
        manager.configure_plugin.assert_not_called()
        self.assertEqual(len(c._event_managers), 1)

    def test_finalise(self):
        manager1 = mock.Mock()
        manager2 = mock.Mock()
        c = collection.Collection()
        c.add_logging_manager(manager1)
        c.add_logging_manager(manager2)

        c.finalise()
        manager1.finalise.assert_called_once_with()
        manager2.finalise.assert_called_once_with()

    def test_log_files(self):
        manager1 = mock.Mock()
        manager2 = mock.Mock()

        def iter1():
            for x in ('log1', 'log2'):
                yield x

        def iter2():
            for y in ('log3', 'log4', 'log5'):
                yield y

        manager1.log_files.return_value = iter1()
        manager2.log_files.return_value = iter2()

        c = collection.Collection()
        c.add_logging_manager(manager1)
        c.add_logging_manager(manager2)

        self.assertEqual(list(c.log_files()),
                         ['log1', 'log2', 'log3', 'log4', 'log5'])

    def test_events_valid(self):
        self.patch_object(collection, 'Streamer', name='mock_Streamer')
        manager1 = mock.Mock()
        manager2 = mock.Mock()

        def iter1():
            for x in (
                    ('log1', collection.LogFormats.InfluxDB, 'log1.txt'),
                    ('log2', collection.LogFormats.InfluxDB, 'log2.txt')):
                yield x

        def iter2():
            for x in (
                    ('log3', collection.LogFormats.InfluxDB, 'log3.txt'),):
                yield x

        manager1.log_files.return_value = iter1()
        manager2.log_files.return_value = iter2()

        c = collection.Collection()
        c.add_logging_manager(manager1)
        c.add_logging_manager(manager2)

        self.mock_Streamer.return_value = 'a-streamer'

        self.assertEqual(c.events(), 'a-streamer')
        self.mock_Streamer.assert_called_once_with(
            ['log1.txt', 'log2.txt', 'log3.txt'],
            collection.LogFormats.InfluxDB,
            sort=True,
            precision='us',
            strip_precision=True)

    def test_events_no_log_files(self):
        self.patch_object(collection, 'Streamer', name='mock_Streamer')
        manager1 = mock.Mock()
        manager2 = mock.Mock()

        def iter1():
            for x in []:
                yield x

        def iter2():
            for x in []:
                yield x

        manager1.log_files.return_value = iter1()
        manager2.log_files.return_value = iter2()

        c = collection.Collection()
        c.add_logging_manager(manager1)
        c.add_logging_manager(manager2)

        self.mock_Streamer.return_value = 'a-streamer'

        self.assertEqual(c.events(), 'a-streamer')
        self.mock_Streamer.assert_called_once_with(
            [],
            collection.LogFormats.InfluxDB)

    def test_events_inconsistent_log_formats(self):
        manager1 = mock.Mock()
        manager2 = mock.Mock()

        def iter1():
            for x in (
                    ('log1', collection.LogFormats.InfluxDB, 'log1.txt'),
                    ('log2', collection.LogFormats.InfluxDB, 'log2.txt')):
                yield x

        def iter2():
            for x in (
                    ('log3', collection.LogFormats.CSV, 'log3.txt'),):
                yield x

        manager1.log_files.return_value = iter1()
        manager2.log_files.return_value = iter2()

        c = collection.Collection()
        c.add_logging_manager(manager1)
        c.add_logging_manager(manager2)

        with self.assertRaises(AssertionError):
            self.assertEqual(c.events(), 'a-streamer')

    def test_clean_up(self):
        manager1 = mock.Mock()
        manager2 = mock.Mock()
        c = collection.Collection()
        c.add_logging_manager(manager1)
        c.add_logging_manager(manager2)

        c.clean_up()
        manager1.clean_up.assert_called_once_with()
        manager2.clean_up.assert_called_once_with()

    def test_reset(self):
        manager1 = mock.Mock()
        manager2 = mock.Mock()
        c = collection.Collection(
            name='a-name',
            collection='a-collection',
            description='a-description',
            logs_dir='logs',
            log_format=None)
        c.add_logging_manager(manager1)
        c.add_logging_manager(manager2)

        c.reset()
        manager1.reset.assert_called_once_with()
        manager2.reset.assert_called_once_with()
        self.assertIsNone(c.collection)
        self.assertIsNone(c.description)
        self.assertIsNone(c.logs_dir)
        self.assertIsNone(c.log_format)
        self.assertEqual(len(c._event_managers), 0)
        self.assertIsNone(manager1.collection_object)
        self.assertIsNone(manager2.collection_object)


class TestStreamerClass(tests_utils.BaseTestCase):
    """The Streamer class is tricky to test.

    It takes a bunch of log files and then produces an iterator which is a
    sorted list of the contents of those logs files (which all need to be the
    same format.

    The easiest thing to do is to actually create some simple log files
    (generatively) and then stream them.
    """

    def setUp(self):
        super().setUp()
        self.patch_object(collection, 'logger', name='mock_logger')

    @staticmethod
    def _write_influxdb_lines(f, event_prefix, count, offset, spacing):
        for x in range(0, count):
            f.write("abc event={prefix}{x} {t}s\n".format(
                prefix=event_prefix,
                x=x,
                t=offset + x * spacing))

    def test_steamer_two_files_no_sort(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            log1 = os.path.join(tmpdirname, 'log1')
            log2 = os.path.join(tmpdirname, 'log2')
            with open(log1, 'wt') as f:
                self._write_influxdb_lines(
                    f, 'aa-', 10, 0, 1)
            with open(log2, 'wt') as f:
                self._write_influxdb_lines(
                    f, 'bb-', 3, 1, 3)
            sorted_logs = [(os.path.join(tmpdirname, f), l) for (f, l) in [
                ('log1', 'abc event=aa-0 0'),
                ('log1', 'abc event=aa-1 1'),
                ('log1', 'abc event=aa-2 2'),
                ('log1', 'abc event=aa-3 3'),
                ('log1', 'abc event=aa-4 4'),
                ('log1', 'abc event=aa-5 5'),
                ('log1', 'abc event=aa-6 6'),
                ('log1', 'abc event=aa-7 7'),
                ('log1', 'abc event=aa-8 8'),
                ('log1', 'abc event=aa-9 9'),
                ('log2', 'abc event=bb-0 1'),
                ('log2', 'abc event=bb-1 4'),
                ('log2', 'abc event=bb-2 7')]]

            with collection.Streamer(
                    [log1, log2], collection.LogFormats.InfluxDB,
                    precision='s', sort=False) as events:
                all_events = list(events)
                self.assertEqual(all_events, sorted_logs)

    def test_steamer_two_files(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            log1 = os.path.join(tmpdirname, 'log1')
            log2 = os.path.join(tmpdirname, 'log2')
            with open(log1, 'wt') as f:
                self._write_influxdb_lines(
                    f, 'aa-', 10, 0, 1)
            with open(log2, 'wt') as f:
                self._write_influxdb_lines(
                    f, 'bb-', 3, 1, 3)
            sorted_logs = [(os.path.join(tmpdirname, f), l) for (f, l) in [
                ('log1', 'abc event=aa-0 0'),
                ('log2', 'abc event=bb-0 1'),
                ('log1', 'abc event=aa-1 1'),
                ('log1', 'abc event=aa-2 2'),
                ('log1', 'abc event=aa-3 3'),
                ('log2', 'abc event=bb-1 4'),
                ('log1', 'abc event=aa-4 4'),
                ('log1', 'abc event=aa-5 5'),
                ('log1', 'abc event=aa-6 6'),
                ('log2', 'abc event=bb-2 7'),
                ('log1', 'abc event=aa-7 7'),
                ('log1', 'abc event=aa-8 8'),
                ('log1', 'abc event=aa-9 9')]]

            with collection.Streamer(
                    [log1, log2], collection.LogFormats.InfluxDB,
                    precision='s') as events:
                all_events = list(events)
                self.assertEqual(all_events, sorted_logs)

    def test_steamer_two_files_earliest_after(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            log1 = os.path.join(tmpdirname, 'log1')
            log2 = os.path.join(tmpdirname, 'log2')
            with open(log1, 'wt') as f:
                self._write_influxdb_lines(
                    f, 'aa-', 10, 0, 1)
            with open(log2, 'wt') as f:
                self._write_influxdb_lines(
                    f, 'bb-', 3, 1, 3)
            sorted_logs = [(os.path.join(tmpdirname, f), l) for (f, l) in [
                ('log1', 'abc event=aa-0 0'),
                ('log2', 'abc event=bb-0 1'),
                ('log1', 'abc event=aa-1 1'),
                ('log1', 'abc event=aa-2 2'),
                ('log1', 'abc event=aa-3 3'),
                ('log2', 'abc event=bb-1 4'),
                ('log1', 'abc event=aa-4 4'),
                ('log1', 'abc event=aa-5 5'),
                ('log1', 'abc event=aa-6 6'),
                ('log2', 'abc event=bb-2 7'),
                ('log1', 'abc event=aa-7 7'),
                ('log1', 'abc event=aa-8 8'),
                ('log1', 'abc event=aa-9 9')]]

            with collection.Streamer(
                    [log2, log1], collection.LogFormats.InfluxDB,
                    precision='s') as events:
                all_events = list(events)
                self.assertEqual(all_events, sorted_logs)

    def test_steamer_two_files_singles(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            log1 = os.path.join(tmpdirname, 'log1')
            log2 = os.path.join(tmpdirname, 'log2')
            with open(log1, 'wt') as f:
                self._write_influxdb_lines(
                    f, 'aa-', 1, 0, 1)
            with open(log2, 'wt') as f:
                self._write_influxdb_lines(
                    f, 'bb-', 1, 1, 3)
            sorted_logs = [(os.path.join(tmpdirname, f), l) for (f, l) in [
                ('log1', 'abc event=aa-0 0'),
                ('log2', 'abc event=bb-0 1')]]

            with collection.Streamer(
                    [log1, log2], collection.LogFormats.InfluxDB,
                    precision='s') as events:
                all_events = list(events)
                self.assertEqual(all_events, sorted_logs)

    def test_stream_two_files_one_empty(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            log1 = os.path.join(tmpdirname, 'log1')
            log2 = os.path.join(tmpdirname, 'log2')
            with open(log1, 'wt') as f:
                self._write_influxdb_lines(
                    f, 'aa-', 1, 0, 1)
            with open(log2, 'wt') as f:
                pass
            sorted_logs = [(os.path.join(tmpdirname, f), l) for (f, l) in [
                ('log1', 'abc event=aa-0 0')]]

            with collection.Streamer(
                    [log1, log2], collection.LogFormats.InfluxDB,
                    precision='s') as events:
                all_events = list(events)
                self.assertEqual(all_events, sorted_logs)

    def test_stream_cant_open_file(self):

        def raise_(_):
            raise FileNotFoundError("bang")

        with mock.patch('builtins.open') as mock_open:
            mock_open.side_effect = raise_
            streamer = collection.Streamer(
                ['log1'], collection.LogFormats.InfluxDB,
                precision='s')
            streamer.__enter__()
            mock_open.assert_called_once_with('log1')
            self.assertEqual(len(streamer.handles), 0)

    def test_stream_exit_closes_files(self):

        def raise_():
            raise FileNotFoundError("bang")

        mock_h1 = mock.Mock()
        mock_h2 = mock.Mock()
        mock_h1.close.side_effect = raise_

        streamer = collection.Streamer(
            ['log1'], collection.LogFormats.InfluxDB,
            precision='s')

        # patch handles so that we can test __exit__ function
        streamer.handles = {'h1': mock_h1, 'h2': mock_h2}

        self.assertFalse(streamer.__exit__('a', 'b', 'c'))

        mock_h1.close.assert_called_once_with()
        mock_h2.close.assert_called_once_with()

        self.mock_logger.warning.assert_called_once_with(
            mock.ANY, 'h1', 'bang')

    def test__iterator_cant_read_from_file(self):
        mock_raise = mock.Mock()

        def raise_():
            mock_raise('bang')
            raise OSError("bang")

        mock_h1 = mock.Mock()
        mock_h1.readline.side_effect = raise_

        streamer = collection.Streamer(
            ['log1'], collection.LogFormats.InfluxDB,
            precision='s')

        # patch handles so that we can test the _iterator function directly
        streamer.handles = {'h1': mock_h1}

        list(streamer._iterator())

        self.assertEqual(len(streamer.handles), 0)
        mock_raise.assert_called_once_with('bang')

    def test_iterator_cant_read_after_first_line(self):
        mock_raise = mock.Mock()

        def raise_(__count=[0]):
            __count[0] += 1
            print("raise_", __count)
            if __count[0] == 2:
                mock_raise('bang')
                raise OSError("bang")
            return "abc event=3 1s\n"

        mock_h1 = mock.Mock()
        mock_h1.readline.side_effect = raise_

        streamer = collection.Streamer(
            ['log1'], collection.LogFormats.InfluxDB,
            precision='s')

        # patch handles so that we can test the _iterator function directly
        streamer.handles = {'h1': mock_h1}

        list(streamer._iterator())

        self.assertEqual(len(streamer.handles), 0)
        mock_raise.assert_called_once_with('bang')


class TestPrecisionConversions(tests_utils.BaseTestCase):

    def _assert_precision(self, time, from_precision, to_precision, expected):
        event_format = "abc event=hello {}{}"
        result = collection._re_precision_timestamp_influxdb(
            event_format.format(time, from_precision), to_precision)
        print(result)
        self.assertEqual(str(expected), result.split(" ")[-1])

    def test__re_precision_timestamp_influxdb(self):
        # seconds
        self._assert_precision(10, 's', 's', 10)
        self._assert_precision(10, 's', 'ms', 10000)
        self._assert_precision(10, 's', 'us', 10000000)
        self._assert_precision(10, 's', 'ns', 10000000000)

        # ms
        self._assert_precision(10001, 'ms', 's', 10)
        self._assert_precision(10001, 'ms', 'ms', 10001)
        self._assert_precision(10001, 'ms', 'us', 10001000)
        self._assert_precision(10001, 'ms', 'ns', 10001000000)

        # us
        self._assert_precision(10000001, 'us', 's', 10)
        self._assert_precision(10000001, 'us', 'ms', 10000)
        self._assert_precision(10000001, 'us', 'us', 10000001)
        self._assert_precision(10000001, 'us', 'ns', 10000001000)

        # ns
        self._assert_precision(10000000001, 'ns', 's', 10)
        self._assert_precision(10000000001, 'ns', 'ms', 10000)
        self._assert_precision(10000000001, 'ns', 'us', 10000000)
        self._assert_precision(10000000001, 'ns', 'ns', 10000000001)

        # ns, no precision marker, defaults to ns
        self._assert_precision(10000000001, '', 's', 10)
        self._assert_precision(10000000001, '', 'ms', 10000)
        self._assert_precision(10000000001, '', 'us', 10000000)
        self._assert_precision(10000000001, '', 'ns', 10000000001)

    def _assert_precision_strip(
            self, time, from_precision, to_precision, expected):
        event_format = "abc event=hello {}{}"
        result = collection._re_precision_timestamp_influxdb(
            event_format.format(time, from_precision), to_precision,
            strip_precision=False)
        print(result)
        self.assertEqual(str(expected), result.split(" ")[-1])

    def test__re_precision_timestamp_influxdb_strip(self):
        # seconds
        self._assert_precision_strip(10, 's', 's', '10s')
        self._assert_precision_strip(10, 's', 'ms', '10000ms')
        self._assert_precision_strip(10, 's', 'us', '10000000us')
        self._assert_precision_strip(10, 's', 'ns', '10000000000ns')


class TestParseDate(tests_utils.BaseTestCase):
    """Test date parsing of known log formats.

    Parsing dates is required to enable sorting of events by date.
    """

    def test__parse_date_influxdb_s(self):
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50)
        influxdb_ts = int(ts.timestamp())

        event = "abc event=hello {}s".format(influxdb_ts)

        dt = collection._parse_date(collection.LogFormats.InfluxDB, event)
        self.assertEqual(ts, dt)

    def test__parse_date_influxdb_ms(self):
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50)
        influxdb_ts = int(ts.timestamp() * 1e3)

        event = "abc event=hello {}ms".format(influxdb_ts)

        dt = collection._parse_date(collection.LogFormats.InfluxDB, event)
        self.assertEqual(ts, dt)

    def test__parse_date_influxdb_us(self):
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50, 150)
        influxdb_ts = int(ts.timestamp() * 1e6)

        event = "abc event=hello {}us".format(influxdb_ts)

        dt = collection._parse_date(collection.LogFormats.InfluxDB, event)
        self.assertEqual(ts, dt)

    def test__parse_date_influxdb_ns(self):
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50, 150)
        influxdb_ts = int(ts.timestamp() * 1e9)

        event = "abc event=hello {}ns".format(influxdb_ts)

        dt = collection._parse_date(collection.LogFormats.InfluxDB, event)
        self.assertEqual(ts, dt)

    def test__parse_date_CSV(self):
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50, 150)
        event = '"{}","some-event","other-thing"'.format(ts.isoformat())

        dt = collection._parse_date(collection.LogFormats.CSV, event)
        self.assertEqual(ts, dt)

    def test__parse_date_LOG(self):
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50, 150)
        event = '{} some-event "other-thing"'.format(ts.isoformat())

        dt = collection._parse_date(collection.LogFormats.LOG, event)
        self.assertEqual(ts, dt)


class TestFromISOFormat(tests_utils.BaseTestCase):

    def test__fromisoformat36(self):
        self.patch('sys.version_info', name='mock_version_info')
        self.mock_version_info.major = 3
        self.mock_version_info.minor = 6
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50)
        s = ts.isoformat()
        res = collection._fromisoformat(s)
        self.assertEqual(ts, res)

    def test__fromisoformat36_float(self):
        self.patch('sys.version_info', name='mock_version_info')
        self.mock_version_info.major = 3
        self.mock_version_info.minor = 6
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50, 150)
        s = ts.isoformat()
        res = collection._fromisoformat(s)
        self.assertEqual(ts, res)

    def test__fromisoformat37plus(self):
        self.patch('sys.version_info', name='mock_version_info')
        self.mock_version_info.major = 3
        self.mock_version_info.minor = 7
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50)
        s = ts.isoformat()
        res = collection._fromisoformat(s)
        self.assertEqual(ts, res)

    def test__fromisoformat37plus_float(self):
        self.patch('sys.version_info', name='mock_version_info')
        self.mock_version_info.major = 3
        self.mock_version_info.minor = 8
        ts = datetime.datetime(2021, 1, 2, 10, 21, 50, 150)
        s = ts.isoformat()
        res = collection._fromisoformat(s)
        self.assertEqual(ts, res)
