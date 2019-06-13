# Copyright 2019 Canonical Ltd.
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
import zaza.utilities.run_report as run_report


class TestUtilitiesRunReport(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestUtilitiesRunReport, self).setUp()
        run_report.clear_run_data()

    def test_register_event(self):
        run_report.register_event(
            'Deploy Bundle',
            run_report.EventStates.START,
            timestamp=10)
        run_report.register_event(
            'Deploy Bundle',
            run_report.EventStates.FINISH,
            timestamp=12)
        self.assertEqual(
            run_report.get_copy_of_events(),
            {
                'Deploy Bundle': {
                    run_report.EventStates.FINISH: 12,
                    run_report.EventStates.START: 10}})

    def test_register_metadata(self):
        run_report.register_metadata(
            cloud_name='cloud1',
            model_name='model2',
            target_bundle='precise-essex')
        self.assertEqual(
            run_report.get_copy_of_metadata(),
            {
                'cloud_name': 'cloud1',
                'model_name': 'model2',
                'target_bundle': 'precise-essex'})

    def test_get_events_start_stop_time(self):
        events = {
            'event1': {
                run_report.EventStates.START: 12,
                run_report.EventStates.FINISH: 18},
            'event2': {
                run_report.EventStates.START: 10,
                run_report.EventStates.FINISH: 15},
            'event3': {
                run_report.EventStates.START: 15,
                run_report.EventStates.FINISH: 28}}
        self.assertEqual(
            run_report.get_events_start_stop_time(events),
            (10, 28))

    def test_get_event_report(self):
        run_report.register_metadata(
            cloud_name='cloud1',
            model_name='model2',
            target_bundle='precise-essex')
        run_report.register_event(
            'Deploy Bundle',
            run_report.EventStates.START,
            timestamp=10)
        run_report.register_event(
            'Deploy Bundle',
            run_report.EventStates.FINISH,
            timestamp=12)
        self.maxDiff = None
        self.assertEqual(
            run_report.get_event_report(),
            {
                run_report.ReportKeys.EVENTS: {
                    'Deploy Bundle': {
                        run_report.ReportKeys.ELAPSED_TIME: 2,
                        run_report.EventStates.FINISH: 12,
                        run_report.ReportKeys.PCT_OF_RUNTIME: 100,
                        run_report.EventStates.START: 10}},
                run_report.ReportKeys.METADATA: {
                    'cloud_name': 'cloud1',
                    'model_name': 'model2',
                    'target_bundle': 'precise-essex'}})

    def test_get_yaml_event_report(self):
        self.patch_object(
            run_report,
            'get_event_report',
            return_value={'myreport': 'thereport'})
        self.assertEqual(
            run_report.get_yaml_event_report(),
            'myreport: thereport\n')

    def test_output_event_report(self):
        self.patch_object(
            run_report,
            'get_yaml_event_report',
            return_value='myreport: thereport')
        self.patch_object(run_report, 'write_event_report')
        self.patch_object(run_report, 'log_event_report')
        run_report.output_event_report()
        self.assertFalse(self.write_event_report.called)
        self.log_event_report.assert_called_once_with(
            'myreport: thereport')

    def test_output_event_report_output_file(self):
        self.patch_object(
            run_report,
            'get_yaml_event_report',
            return_value='myreport: thereport')
        self.patch_object(run_report, 'write_event_report')
        self.patch_object(run_report, 'log_event_report')
        run_report.output_event_report(output_file='/tmp/a.yaml')
        self.write_event_report.assert_called_once_with(
            'myreport: thereport',
            '/tmp/a.yaml')
        self.log_event_report.assert_called_once_with(
            'myreport: thereport')

    def test_write_event_report(self):
        open_mock = mock.mock_open()
        with mock.patch('zaza.utilities.run_report.open', open_mock,
                        create=False):
            run_report.write_event_report(
                'myreport: thereport',
                '/tmp/a.yaml')
        open_mock.assert_called_once_with('/tmp/a.yaml', 'w')
        handle = open_mock()
        handle.write.assert_called_once_with('myreport: thereport')

    def test_log_event_report(self):
        self.patch_object(run_report.logging, 'info')
        run_report.log_event_report(
            'myreport: thereport')
        self.info.assert_called_once_with(
            'myreport: thereport')

    def test_get_run_data(self):
        run_report.register_event(
            'Deploy Bundle',
            run_report.EventStates.START,
            timestamp=10)
        self.assertEqual(
            run_report.get_run_data(),
            run_report._run_data)

    def test_clear_run_data(self):
        run_report.register_event(
            'Deploy Bundle',
            run_report.EventStates.START,
            timestamp=10)
        run_report.clear_run_data()
        self.assertEqual(
            run_report.get_run_data(),
            {
                run_report.ReportKeys.METADATA: {},
                run_report.ReportKeys.EVENTS: {}})
