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

"""Unit tests for zaza.events.notifications."""

import datetime
import mock

import unit_tests.utils as tests_utils


import zaza.charm_lifecycle.utils as lc_utils
import zaza.events.notifications as notifications


class TestEventsPluginInit(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(notifications, 'logger', name='mock_logger')
        self.patch_object(notifications, 'subscribe', name='mock_subscribe')
        self.patch_object(notifications, 'get_option', name='mock_get_option')

    def test_init(self):
        self.patch('tempfile.gettempdir', name='mock_gettempdir')
        self.mock_gettempdir.return_value = '/some/tmp'
        self.patch('tempfile.TemporaryDirectory',
                   name='mock_TemporaryDirectory')
        self.patch_object(notifications, 'Path', name='mock_Path',
                          new=mock.MagicMock())
        self.mock_get_option.return_value = True

        ev = notifications.EventsPlugin('env-deployments')

        self.mock_get_option.assert_called_once_with(
            'zaza-events.keep-logs', False)
        self.mock_Path.assert_called_once_with('/some/tmp/zaza-events')
        self.mock_Path.return_value.mkdir.assert_called_once_with(
            parents=True, exist_ok=True)
        self.mock_TemporaryDirectory.assert_not_called()
        self.mock_subscribe.assert_has_calls((
            mock.call(ev.handle_notifications,
                      event=None,
                      when=notifications.NotifyType.BOTH),
            mock.call(ev.handle_before_bundle,
                      event=notifications.NotifyEvents.BUNDLE,
                      when=notifications.NotifyType.BEFORE),
            mock.call(ev.handle_after_bundle,
                      event=notifications.NotifyEvents.BUNDLE,
                      when=notifications.NotifyType.AFTER),
        ))

    def test_init_dont_keep_logs(self):
        self.patch('tempfile.gettempdir', name='mock_gettempdir')
        self.mock_gettempdir.return_value = '/some/tmp'
        self.patch('tempfile.TemporaryDirectory',
                   name='mock_TemporaryDirectory')
        self.mock_TemporaryDirectory.return_value = '/a/tmp-zaza-events'
        self.patch_object(notifications, 'Path', name='mock_Path',
                          new=mock.MagicMock())
        self.mock_get_option.return_value = False

        ev = notifications.EventsPlugin('env-deployments')

        self.mock_get_option.assert_called_once_with(
            'zaza-events.keep-logs', False)
        self.mock_Path.assert_not_called()
        self.mock_TemporaryDirectory.assert_called_once_with('-zaza-events')
        self.assertEqual(ev.logs_dir_base, '/a/tmp-zaza-events')
        self.mock_subscribe.assert_has_calls((
            mock.call(ev.handle_notifications,
                      event=None,
                      when=notifications.NotifyType.BOTH),
            mock.call(ev.handle_before_bundle,
                      event=notifications.NotifyEvents.BUNDLE,
                      when=notifications.NotifyType.BEFORE),
            mock.call(ev.handle_after_bundle,
                      event=notifications.NotifyEvents.BUNDLE,
                      when=notifications.NotifyType.AFTER),
        ))


class TestEventsPlugin(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(notifications, 'logger', name='mock_logger')
        self.patch_object(notifications, 'subscribe', name='mock_subscribe')
        self.patch_object(notifications, 'get_option', name='mock_get_option')
        self.patch('tempfile.gettempdir', name='mock_gettempdir')
        self.mock_gettempdir.return_value = '/some/tmp'
        self.patch('tempfile.TemporaryDirectory',
                   name='mock_TemporaryDirectory')
        self.mock_TemporaryDirectory.return_value = '/a/tmp-zaza-events'
        self.patch_object(notifications, 'Path', name='mock_Path',
                          new=mock.MagicMock())
        self.ev = notifications.EventsPlugin('env-deployments')
        self._options = {
            'zaza-events.keep-logs': False,
            'zaza-events.log-collection-name': 'some-logs',
            'zaza-events.collection-description': 'nice-description',
            'zaza-events.modules': [],
            'zaza-events.raise-exceptions': False,
        }
        self.mock_get_option.side_effect = self._get_option
        self.patch_object(notifications.utils, 'get_class',
                          name='mock_get_class', new=mock.MagicMock())
        self.mock_collection = mock.Mock()
        self.patch_object(notifications.ze_collection, 'get_collection',
                          name='mock_get_collection')
        self.mock_get_collection.return_value = self.mock_collection
        self.patch_object(notifications, 'get_global_event_logger_instance',
                          name='mock_get_global_event_logger_instance')
        self.mock_events = mock.Mock()
        self.mock_get_global_event_logger_instance.return_value = (
            self.mock_events)
        self.env_deployment = lc_utils.EnvironmentDeploy(
            name='default1',
            model_deploys=[
                lc_utils.ModelDeploy(
                    model_alias='default_alias',
                    model_name='zaza-b9413598c856',
                    bundle='conncheck-focal'
                )
            ],
            run_in_series=True
        )
        self.patch('datetime.datetime', name='mock_datetime',
                   spec=datetime.datetime)
        self.mock_datetime.now().timestamp.return_value = 42

    def _get_option(self, key, default=None):
        try:
            return self._options[key]
        except KeyError:
            pass
        return default

    def test_handle_before_bundle_asserts(self):
        with self.assertRaises(AssertionError):
            self.ev.handle_before_bundle("not-a-real-event", "not-a-when",
                                         env_deployment=self.env_deployment)
        with self.assertRaises(AssertionError):
            self.ev.handle_before_bundle(
                notifications.NotifyEvents.BEFORE_DEPLOY,
                notifications.NotifyType.BEFORE,
                env_deployment=self.env_deployment)
        with self.assertRaises(AssertionError):
            self.ev.handle_before_bundle(
                notifications.NotifyEvents.BEFORE_DEPLOY,
                notifications.NotifyType.AFTER,
                env_deployment=self.env_deployment)
        with self.assertRaises(AssertionError):
            self.ev.handle_before_bundle(
                notifications.NotifyEvents.BUNDLE,
                notifications.NotifyType.AFTER,
                env_deployment=self.env_deployment)

    def test_handle_before_bundle_configures(self):
        self.ev.handle_before_bundle(
            notifications.NotifyEvents.BUNDLE,
            notifications.NotifyType.BEFORE,
            env_deployment=self.env_deployment)
        self.mock_collection.reset.assert_called_once_with()
        self.mock_collection.configure.assert_called_once_with(
            collection='some-logs',
            description='nice-description',
            logs_dir='/a/tmp-zaza-events/conncheck-focal-42000000us')
        self.mock_events.log.assert_called_once_with(
            notifications.Events.START_TEST, comment="Starting some-logs")

    def test_handle_before_bundle_modules_incorrect(self):
        self._options['zaza-events.modules'] = 'some-str'
        self.ev.handle_before_bundle(
            notifications.NotifyEvents.BUNDLE,
            notifications.NotifyType.BEFORE,
            env_deployment=self.env_deployment)
        self.mock_logger.error.assert_called_once_with(
            "Option zaza-events.module isn't a list? %s", 'some-str')

        self.mock_logger.reset_mock()
        self._options['zaza-events.modules'] = None
        self.ev.handle_before_bundle(
            notifications.NotifyEvents.BUNDLE,
            notifications.NotifyType.BEFORE,
            env_deployment=self.env_deployment)
        self.mock_logger.error.assert_called_once_with(
            "Option zaza-events.module isn't a list? %s", None)

    def test_handle_before_bundle_autoconfigure(self):
        config = {
            'key1': 'value1',
            'key2': 'value2',
        }

        self._options['zaza-events.modules'] = [{'some_module': config}]
        self.ev.handle_before_bundle(
            notifications.NotifyEvents.BUNDLE,
            notifications.NotifyType.BEFORE,
            env_deployment=self.env_deployment)
        self.mock_get_class.assert_called_once_with(
            'zaza.events.plugins.some_module.auto_configure_with_collection')
        self.mock_get_class.return_value.assert_called_once_with(
            self.mock_collection, config)

    def test_handle_before_bundle_module_spec_not_dict(self):
        self._options['zaza-events.modules'] = [None]
        self.ev.handle_before_bundle(
            notifications.NotifyEvents.BUNDLE,
            notifications.NotifyType.BEFORE,
            env_deployment=self.env_deployment)
        self.mock_get_class.assert_not_called()
        self.mock_logger.error.assert_called_once_with(mock.ANY, None)

    def test_handle_before_bundle_module_config_not_dict(self):
        self._options['zaza-events.modules'] = [{'some_module': None}]
        self.ev.handle_before_bundle(
            notifications.NotifyEvents.BUNDLE,
            notifications.NotifyType.BEFORE,
            env_deployment=self.env_deployment)
        self.mock_get_class.assert_not_called()
        self.mock_logger.error.assert_called_once_with(
            mock.ANY, 'some_module', None)

    def test_handle_before_bundle_module_multi_keys(self):
        config = {
            'key1': 'value1',
            'key2': 'value2',
        }
        self._options['zaza-events.modules'] = [{'some_module': config,
                                                 'some_other_module': config}]
        self.ev.handle_before_bundle(
            notifications.NotifyEvents.BUNDLE,
            notifications.NotifyType.BEFORE,
            env_deployment=self.env_deployment)
        self.mock_get_class.assert_not_called()
        self.mock_logger.error.assert_called_once_with(
            mock.ANY, {'some_module': config,
                       'some_other_module': config})

    def test_handle_before_bundle_module_spec_is_str(self):
        self._options['zaza-events.modules'] = ['some_module']
        self.ev.handle_before_bundle(
            notifications.NotifyEvents.BUNDLE,
            notifications.NotifyType.BEFORE,
            env_deployment=self.env_deployment)
        self.mock_get_class.assert_called_once_with(
            'zaza.events.plugins.some_module.auto_configure_with_collection')
        self.mock_get_class.return_value.assert_called_once_with(
            self.mock_collection, {})

    def test_handle_before_bundle_autoconfigure_raises_exception(self):
        self._options['zaza-events.modules'] = ['some_module']

        def raise_(*args, **kwargs):
            raise Exception('bang')

        self.mock_get_class.return_value.side_effect = raise_

        self.ev.handle_before_bundle(
            notifications.NotifyEvents.BUNDLE,
            notifications.NotifyType.BEFORE,
            env_deployment=self.env_deployment)
        self.mock_get_class.assert_called_once_with(
            'zaza.events.plugins.some_module.auto_configure_with_collection')
        self.mock_get_class.return_value.assert_called_once_with(
            self.mock_collection, {})
        self.mock_logger.error.assert_called_once_with(
            'Error running autoconfigure for zaza-events %s: %s',
            'zaza.events.plugins.some_module.auto_configure_with_collection',
            'bang')

    def test_handle_before_bundle_autoconfigure_raises_exception_and_raise(
            self):
        self._options['zaza-events.modules'] = ['some_module']
        self._options['zaza-events.raise-exceptions'] = True

        class CustomException(Exception):
            pass

        def raise_(*args, **kwargs):
            raise CustomException('bang')

        self.mock_get_class.return_value.side_effect = raise_

        with self.assertRaises(CustomException):
            self.ev.handle_before_bundle(
                notifications.NotifyEvents.BUNDLE,
                notifications.NotifyType.BEFORE,
                env_deployment=self.env_deployment)
        self.mock_get_class.assert_called_once_with(
            'zaza.events.plugins.some_module.auto_configure_with_collection')
        self.mock_get_class.return_value.assert_called_once_with(
            self.mock_collection, {})
        self.mock_logger.error.assert_called_once_with(
            'Error running autoconfigure for zaza-events %s: %s',
            'zaza.events.plugins.some_module.auto_configure_with_collection',
            'bang')

    def test_handle_after_bundle_asserts(self):
        with self.assertRaises(AssertionError):
            self.ev.handle_after_bundle(
                notifications.NotifyEvents.BUNDLE,
                notifications.NotifyType.BEFORE,
                env_deployment=self.env_deployment)

        with self.assertRaises(AssertionError):
            self.ev.handle_after_bundle(
                notifications.NotifyEvents.BEFORE_DEPLOY,
                notifications.NotifyType.AFTER,
                env_deployment=self.env_deployment)

    def test_handle_after_bundle(self):
        self.patch_object(notifications, 'upload_collection_by_config',
                          name='mock_upload_collection_by_config')
        self.mock_collection.log_files.return_value = (
            ('a-file', 'a-format', 'log1.log'),)
        self.ev.handle_after_bundle(
            notifications.NotifyEvents.BUNDLE,
            notifications.NotifyType.AFTER,
            env_deployment=self.env_deployment)
        self.mock_events.log.assert_called_once_with(
            notifications.Events.END_TEST, comment='Test ended')
        self.mock_logger.debug.assert_called_once_with(
            mock.ANY, 'a-file', 'a-format', 'log1.log')
        self.mock_upload_collection_by_config.assert_called_once_with(
            self.mock_collection,
            context={
                'date': '42000000us',
                'bundle': 'conncheck-focal'
            }
        )

    def test_handle_notifications_checks(self):
        with self.assertRaises(AssertionError):
            self.ev.handle_notifications(
                'some-event', notifications.NotifyType.BEFORE)
        self.ev.handle_notifications(
            notifications.NotifyEvents.BUNDLE,
            notifications.NotifyType.BEFORE)
        self.mock_events.log.assert_not_called()

    def test_handle_notifications(self):
        self.patch_object(notifications, '_convert_notify_into_events',
                          name='mock__convert_notify_into_events')
        self.mock__convert_notify_into_events.return_value = 'mod-event'
        self.patch_object(notifications,
                          '_convert_notify_kwargs_to_events_args',
                          name='mock__convert_notify_kwargs_to_events_args')
        self.mock__convert_notify_kwargs_to_events_args.return_value = (
            {'kwargs': 'new-kwargs'})
        self.ev.handle_notifications(
            notifications.NotifyEvents.BEFORE_DEPLOY,
            notifications.NotifyType.BEFORE,
            this='that', some='random')
        self.mock_events.log.assert_called_once_with(
            'mod-event', kwargs='new-kwargs')
        (self.mock__convert_notify_kwargs_to_events_args
             .assert_called_once_with(
                 dict(this='that', some='random', span='before')))
        self.mock__convert_notify_into_events.assert_called_once_with(
            notifications.NotifyEvents.BEFORE_DEPLOY)

    def test_handle_notifications_span_after(self):
        self.patch_object(notifications, '_convert_notify_into_events',
                          name='mock__convert_notify_into_events')
        self.mock__convert_notify_into_events.return_value = 'mod-event'
        self.patch_object(notifications,
                          '_convert_notify_kwargs_to_events_args',
                          name='mock__convert_notify_kwargs_to_events_args')
        self.mock__convert_notify_kwargs_to_events_args.return_value = (
            {'kwargs': 'new-kwargs'})
        self.ev.handle_notifications(
            notifications.NotifyEvents.BEFORE_DEPLOY,
            notifications.NotifyType.AFTER,
            this='that', some='random')
        self.mock_events.log.assert_called_once_with(
            'mod-event', kwargs='new-kwargs')
        (self.mock__convert_notify_kwargs_to_events_args
             .assert_called_once_with(
                 dict(this='that', some='random', span='after')))
        self.mock__convert_notify_into_events.assert_called_once_with(
            notifications.NotifyEvents.BEFORE_DEPLOY)

    def test_handle_notifications_custom_span(self):
        self.patch_object(notifications, '_convert_notify_into_events',
                          name='mock__convert_notify_into_events')
        self.mock__convert_notify_into_events.return_value = 'mod-event'
        self.patch_object(notifications,
                          '_convert_notify_kwargs_to_events_args',
                          name='mock__convert_notify_kwargs_to_events_args')
        self.mock__convert_notify_kwargs_to_events_args.return_value = (
            {'kwargs': 'new-kwargs'})
        self.ev.handle_notifications(
            notifications.NotifyEvents.BEFORE_DEPLOY,
            notifications.NotifyType.AFTER,
            this='that', some='random', span='custom')
        self.mock_events.log.assert_called_once_with(
            'mod-event', kwargs='new-kwargs')
        (self.mock__convert_notify_kwargs_to_events_args
             .assert_called_once_with(
                 dict(this='that', some='random', span='custom')))
        self.mock__convert_notify_into_events.assert_called_once_with(
            notifications.NotifyEvents.BEFORE_DEPLOY)

    def test__convert_notify_into_events(self):
        self.assertEqual(
            notifications._convert_notify_into_events(
                notifications.NotifyEvents.BUNDLE),
            notifications.Events.BUNDLE)

        with self.assertRaises(ValueError):
            mock_event = mock.Mock()
            mock_event.value = 'unknown'
            notifications._convert_notify_into_events(mock_event)

    def test__convert_notify_kwargs_to_event_args(self):
        kwargs = {
            "model_name": 'a-model',
            "function": 'a-function',
            "bundle": 'a-bundle',
            "model": 'a-model',
            "model_ctxt": 'a-context',
            "force": True,
            "testcase": 'a-test-case',
            "test_name": 'a-test-name',
            'unknown': 'unknown-value',
            'unknown2': 4,
        }
        expected = {
            'item': 'a-test-case',
            'tags': {
                'force': True,
                'function': 'a-function',
                'model': 'a-model',
                'model_name': 'a-model',
                'test_name': 'a-test-name'
            },
            'unknown': 'unknown-value',
            'unknown2': '4',
        }
        self.assertEqual(
            notifications._convert_notify_kwargs_to_events_args(kwargs),
            expected)

    def test_event_context_vars_multiple_deploys(self):
        env_deployment = lc_utils.EnvironmentDeploy(
            name='default1',
            model_deploys=[
                lc_utils.ModelDeploy(
                    model_alias='default_alias',
                    model_name='zaza-b9413598c856',
                    bundle='conncheck-focal'
                ),
                lc_utils.ModelDeploy(
                    model_alias='default_alias2',
                    model_name='zaza-interesting',
                    bundle='conncheck-bionic'
                )
            ],
            run_in_series=True
        )
        self.assertEqual(notifications.event_context_vars(env_deployment),
                         {'bundle': 'default1', 'date': '42000000us'})
