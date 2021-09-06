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

"""Unit tests for zaza.notifications."""

import copy
from collections.abc import Iterable
import mock

import unit_tests.utils as tests_utils


import zaza.notifications as notifications
from zaza.notifications import NotifyEvents, NotifyType


class TestNotifications(tests_utils.BaseTestCase):

    NOTIFY_MAP_TYPES = (NotifyType.BEFORE,
                        NotifyType.AFTER,
                        NotifyType.EXCEPTION)

    def setUp(self):
        super().setUp()
        self._notify_map_copy = copy.deepcopy(notifications._notify_map)

        def f():
            pass

        self.f = f
        self.patterns = set()
        self.patch_object(notifications, 'logger')

    def tearDown(self):
        notifications._notify_map = self._notify_map_copy
        super().tearDown()

    def test_subscribe_this(self):
        self.patch_object(notifications, 'subscribe', name='mock_subscribe')

        @notifications.subscribe_this(
            event=NotifyEvents.BEFORE_DEPLOY,
            when=NotifyType.AFTER)
        def some_function():
            pass

        self.mock_subscribe.assert_called_once_with(
            some_function, NotifyEvents.BEFORE_DEPLOY, NotifyType.AFTER)

    def _add_pattern(self, event, when):
        if event == NotifyEvents:
            event = list(NotifyEvents)
        if when == NotifyType:
            when = self.NOTIFY_MAP_TYPES
        if not isinstance(event, Iterable):
            event = (event, )
        if not isinstance(when, Iterable):
            when = (when, )
        for e in event:
            for w in when:
                self.patterns.add((e, w))

    def _asserts(self, what):
        for t in self.NOTIFY_MAP_TYPES:
            for e in NotifyEvents:
                if (e, t) in self.patterns:
                    self.assertIn(
                        what,
                        notifications._notify_map[t][e],
                        "Event: {}, When: {}".format(e, t))
                else:
                    self.assertNotIn(
                        self.f,
                        notifications._notify_map[t][e],
                        "Event: {}, When: {}".format(e, t))

    def test_subscribe_all(self):
        notifications.subscribe(self.f)
        self._add_pattern(NotifyEvents, NotifyType.BEFORE)
        self._asserts(self.f)

    def test_subscribe_all_BEFORE(self):
        notifications.subscribe(self.f, when=NotifyType.BEFORE)
        # same as _all above)
        self._add_pattern(NotifyEvents, NotifyType.BEFORE)
        self._asserts(self.f)

    def test_subscribe_one_event_one_when(self):
        notifications.subscribe(self.f,
                                event=NotifyEvents.BUNDLE,
                                when=NotifyType.BEFORE)
        self._add_pattern(NotifyEvents.BUNDLE, NotifyType.BEFORE)
        self._asserts(self.f)

    def test_subscribe_one_event_both_when(self):
        notifications.subscribe(self.f,
                                event=NotifyEvents.BUNDLE,
                                when=NotifyType.BOTH)
        self._add_pattern(NotifyEvents.BUNDLE, NotifyType.BEFORE)
        self._add_pattern(NotifyEvents.BUNDLE, NotifyType.AFTER)
        self._asserts(self.f)

    def test_subscribe_multiple_event_one_when(self):
        notifications.subscribe(self.f,
                                event=(NotifyEvents.BUNDLE,
                                       NotifyEvents.ENV_DEPLOYMENT),
                                when=NotifyType.BEFORE)
        self._add_pattern(NotifyEvents.BUNDLE, NotifyType.BEFORE)
        self._add_pattern(NotifyEvents.ENV_DEPLOYMENT, NotifyType.BEFORE)
        self._asserts(self.f)

    def test_subscribe_one_event_all_when(self):
        notifications.subscribe(self.f,
                                event=NotifyEvents.BUNDLE,
                                when=NotifyType.ALL)
        self._add_pattern(NotifyEvents.BUNDLE, NotifyType.BEFORE)
        self._add_pattern(NotifyEvents.BUNDLE, NotifyType.AFTER)
        self._add_pattern(NotifyEvents.BUNDLE, NotifyType.EXCEPTION)
        self._asserts(self.f)

    def test_unsubscribe_all(self):
        notifications.subscribe(self.f)
        notifications.unsubscribe(self.f)
        self._asserts(self.f)

    def test_unsubscribe_all_BEFORE(self):
        notifications.subscribe(self.f, when=NotifyType.BEFORE)
        notifications.unsubscribe(self.f, when=NotifyType.BEFORE)
        self._asserts(self.f)

    def test_unsubscribe_one_event_one_when(self):
        notifications.subscribe(self.f,
                                event=NotifyEvents.BUNDLE,
                                when=NotifyType.BEFORE)
        notifications.unsubscribe(self.f,
                                  event=NotifyEvents.BUNDLE,
                                  when=NotifyType.BEFORE)
        self._asserts(self.f)

    def test_unsubscribe_one_event_both_when(self):
        notifications.subscribe(self.f,
                                event=NotifyEvents.BUNDLE,
                                when=NotifyType.BOTH)
        notifications.unsubscribe(self.f,
                                  event=NotifyEvents.BUNDLE,
                                  when=NotifyType.BOTH)
        self._asserts(self.f)

    def test_unsubscribe_multiple_event_one_when(self):
        notifications.subscribe(self.f,
                                event=(NotifyEvents.BUNDLE,
                                       NotifyEvents.ENV_DEPLOYMENT),
                                when=NotifyType.BEFORE)
        notifications.unsubscribe(self.f,
                                  event=(NotifyEvents.BUNDLE,
                                         NotifyEvents.ENV_DEPLOYMENT),
                                  when=NotifyType.BEFORE)
        self._asserts(self.f)

    def test_unsubscribe_one_event_multiple_when(self):
        notifications.subscribe(self.f,
                                event=NotifyEvents.BUNDLE,
                                when=(NotifyType.BEFORE, NotifyType.AFTER))
        notifications.unsubscribe(self.f,
                                  event=NotifyEvents.BUNDLE,
                                  when=(NotifyType.BEFORE, NotifyType.AFTER))
        self._asserts(self.f)

    def test_unsubscribe_one_event_all_when(self):
        notifications.subscribe(self.f,
                                event=NotifyEvents.BUNDLE,
                                when=NotifyType.ALL)
        notifications.unsubscribe(self.f,
                                  event=NotifyEvents.BUNDLE,
                                  when=NotifyType.ALL)
        self._asserts(self.f)

    def test_notify_single(self):
        f = mock.Mock()
        notifications.subscribe(f, event=NotifyEvents.BUNDLE,
                                when=NotifyType.BEFORE)
        notifications.notify(NotifyEvents.BUNDLE, "hello",
                             when=NotifyType.BEFORE, thing="thing")
        f.assert_called_once_with(
            NotifyEvents.BUNDLE, NotifyType.BEFORE, "hello", thing="thing")

    def test_notify_single_different_type(self):
        f = mock.Mock()
        notifications.subscribe(f, event=NotifyEvents.BUNDLE,
                                when=NotifyType.BEFORE)
        notifications.notify(NotifyEvents.BUNDLE, "hello",
                             when=NotifyType.AFTER, thing="thing")
        f.assert_not_called()

    def test_notify_single_different_event(self):
        f = mock.Mock()
        notifications.subscribe(f, event=NotifyEvents.BUNDLE,
                                when=NotifyType.BEFORE)
        notifications.notify(NotifyEvents.ENV_DEPLOYMENT, "hello",
                             when=NotifyType.BEFORE, thing="thing")
        f.assert_not_called()

    def test_notify_subscribe_both(self):
        f = mock.Mock()
        notifications.subscribe(f, event=NotifyEvents.BUNDLE,
                                when=NotifyType.BOTH)
        notifications.notify(NotifyEvents.BUNDLE, "hello",
                             when=NotifyType.BEFORE, thing="thing")
        f.assert_called_once_with(
            NotifyEvents.BUNDLE, NotifyType.BEFORE, "hello", thing="thing")
        f.reset_mock()
        notifications.notify(NotifyEvents.BUNDLE, "hello",
                             when=NotifyType.AFTER, thing="thing")
        f.assert_called_once_with(
            NotifyEvents.BUNDLE, NotifyType.AFTER, "hello", thing="thing")

    def test_notify_subscribe_both_not_exception(self):
        f = mock.Mock()
        notifications.subscribe(f, event=NotifyEvents.BUNDLE,
                                when=NotifyType.BOTH)
        notifications.notify(NotifyEvents.BUNDLE, "hello",
                             when=NotifyType.EXCEPTION, thing="thing")
        f.assert_not_called()

    def test_notify_subscribe_all(self):
        f = mock.Mock()
        notifications.subscribe(f, event=NotifyEvents.BUNDLE,
                                when=NotifyType.ALL)
        notifications.notify(NotifyEvents.BUNDLE, "hello",
                             when=NotifyType.BEFORE, thing="thing")
        f.assert_called_once_with(
            NotifyEvents.BUNDLE, NotifyType.BEFORE, "hello", thing="thing")
        f.reset_mock()
        notifications.notify(NotifyEvents.BUNDLE, "hello",
                             when=NotifyType.AFTER, thing="thing")
        f.assert_called_once_with(
            NotifyEvents.BUNDLE, NotifyType.AFTER, "hello", thing="thing")
        f.reset_mock()
        notifications.notify(NotifyEvents.BUNDLE, "hello",
                             when=NotifyType.EXCEPTION, thing="thing")
        f.assert_called_once_with(
            NotifyEvents.BUNDLE, NotifyType.EXCEPTION, "hello", thing="thing")

    def test_notify_subscribe_all_events(self):
        f = mock.Mock()
        notifications.subscribe(f, when=NotifyType.ALL)
        notifications.notify(NotifyEvents.BUNDLE, "hello",
                             when=NotifyType.BEFORE, thing="thing")
        f.assert_called_once_with(
            NotifyEvents.BUNDLE, NotifyType.BEFORE, "hello", thing="thing")
        f.reset_mock()
        notifications.notify(NotifyEvents.BUNDLE, "hello",
                             when=NotifyType.AFTER, thing="thing")
        f.assert_called_once_with(
            NotifyEvents.BUNDLE, NotifyType.AFTER, "hello", thing="thing")
        f.reset_mock()
        notifications.notify(NotifyEvents.BUNDLE, "hello",
                             when=NotifyType.EXCEPTION, thing="thing")
        f.assert_called_once_with(
            NotifyEvents.BUNDLE, NotifyType.EXCEPTION, "hello", thing="thing")

    def test_notify_function_raises(self):
        f = mock.Mock()

        class ExceptionTest(Exception):
            pass

        def raise_(*args, **kwargs):
            raise ExceptionTest("bang")

        f.side_effect = raise_

        notifications.subscribe(f, event=NotifyEvents.BUNDLE,
                                when=NotifyType.BEFORE)

        with self.assertRaises(ExceptionTest):
            notifications.notify(NotifyEvents.BUNDLE, "hello",
                                 when=NotifyType.BEFORE, thing="thing")
        f.assert_called_once_with(
            NotifyEvents.BUNDLE, NotifyType.BEFORE, "hello", thing="thing")

    def test_noitify_around(self):
        f = mock.Mock()
        notifications.subscribe(f, event=NotifyEvents.BUNDLE,
                                when=NotifyType.BOTH)

        @notifications.notify_around(NotifyEvents.BUNDLE)
        def target():
            pass

        target()

        f.assert_has_calls((
            mock.call(NotifyEvents.BUNDLE, NotifyType.BEFORE, uuid=mock.ANY),
            mock.call(NotifyEvents.BUNDLE, NotifyType.AFTER, uuid=mock.ANY)))

    def test_noitify_around_with_exception(self):
        f = mock.Mock()

        notifications.subscribe(f, event=NotifyEvents.BUNDLE,
                                when=NotifyType.ALL)

        class ExceptionTest(Exception):
            pass

        @notifications.notify_around(NotifyEvents.BUNDLE, "hello", this="that")
        def target():
            raise ExceptionTest('bang')

        with self.assertRaises(ExceptionTest):
            target()

        f.assert_has_calls((
            mock.call(NotifyEvents.BUNDLE, NotifyType.BEFORE, "hello",
                      this="that", uuid=mock.ANY),
            mock.call(NotifyEvents.BUNDLE, NotifyType.EXCEPTION, "hello",
                      this="that", uuid=mock.ANY)))
