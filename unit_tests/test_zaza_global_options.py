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

"""Unit tests for global options."""

import collections

import unit_tests.utils as ut_utils

import zaza.utilities.ro_types as ro_types
import zaza.global_options as g


class TestGetRawOptions(ut_utils.BaseTestCase):

    def test_get_raw_options(self):
        self.patch_object(g, '_options', new={})
        self.assertEqual(g.get_raw_options(), self._options)
        g._options = {"hello": "there"}
        self.assertEqual(g.get_raw_options(), {"hello": "there"})


class TestGetOptions(ut_utils.BaseTestCase):

    def test_get_options(self):
        self.patch_object(g, 'get_raw_options', return_value={})
        options = g.get_options()
        self.assertIsInstance(options, ro_types.ReadOnlyDict)
        self.assertEqual(len(options.keys()), 0)
        self.get_raw_options.return_value = {"hello": "there"}
        options = g.get_options()
        self.assertEqual(options['hello'], "there")


class TestResetOptions(ut_utils.BaseTestCase):

    def test_reset_options(self):
        self.patch_object(g, '_options')
        self.assertIs(g._options, self._options)
        g.reset_options()
        self.assertIsNot(g._options, self._options)


class TestHelpers(ut_utils.BaseTestCase):

    def test__keys_to_level_types(self):
        keys = ["this", "is", "0", "1", "and"]
        result = [g.LevelType.DICT, g.LevelType.DICT, g.LevelType.LIST,
                  g.LevelType.LIST, g.LevelType.DICT]
        self.assertEqual(g._keys_to_level_types(keys), result)
        self.assertEqual(g._keys_to_level_types(keys, use_list=False),
                         [g.LevelType.DICT] * len(keys))

        with self.assertRaises(AssertionError):
            g._keys_to_level_types(None)
        with self.assertRaises(AssertionError):
            g._keys_to_level_types([None])

    def test__ref_to_level_type(self):
        self.assertEqual(g._ref_to_level_type({}), g.LevelType.DICT)
        self.assertEqual(g._ref_to_level_type(collections.OrderedDict()),
                         g.LevelType.DICT)
        self.assertEqual(g._ref_to_level_type([]), g.LevelType.LIST)
        self.assertEqual(g._ref_to_level_type((1,)), g.LevelType.LIST)
        self.assertEqual(g._ref_to_level_type(None), g.LevelType.LEAF)
        self.assertEqual(g._ref_to_level_type(1), g.LevelType.LEAF)
        self.assertEqual(g._ref_to_level_type("hello"), g.LevelType.LEAF)
        self.assertEqual(g._ref_to_level_type(object), g.LevelType.LEAF)

    def test__collection_for_type(self):
        self.assertIsInstance(g._collection_for_type(g.LevelType.DICT),
                              collections.OrderedDict)
        self.assertIsInstance(g._collection_for_type(g.LevelType.LIST),
                              list)
        with self.assertRaises(RuntimeError):
            g._collection_for_type(g.LevelType.LEAF)

    def test__convert_key_type(self):
        self.assertIsInstance(g._convert_key_type("hello", g.LevelType.DICT),
                              str)
        self.assertIsInstance(g._convert_key_type("0", g.LevelType.LIST), int)
        self.assertIsInstance(g._convert_key_type("0", g.LevelType.DICT), str)
        with self.assertRaises(AssertionError):
            g._convert_key_type("hello", g.LevelType.LEAF)
        with self.assertRaises(AssertionError):
            g._convert_key_type(None, g.LevelType.DICT)
        with self.assertRaises(AssertionError):
            g._convert_key_type(object, g.LevelType.DICT)


class TestSetOption(ut_utils.BaseTestCase):

    def test_set_option(self):
        self.patch_object(g, '_options', new={})
        g.set_option("this.interesting.key", 1)
        self.assertEqual(g._options['this']['interesting']['key'], 1)
        g.set_option("this.other.thing", 2)
        self.assertEqual(g._options['this']['interesting']['key'], 1)
        self.assertEqual(g._options['this']['other']['thing'], 2)
        g.set_option("this.list.1", 3)
        self.assertEqual(g._options['this']['list'][1], 3)
        self.assertEqual(g._options['this']['list'][0], None)
        g.set_option("this.list.1", "goodbye")
        self.assertEqual(g._options['this']['list'][1], "goodbye")
        # re-write an option type
        g.set_option("this.list.is", "on", override=True)
        self.assertEqual(g._options['this']['list']['is'], "on")

    def test_get_option(self):
        options = {
            'key1': 'value1',
            'key2': 2,
            'key3': {
                'key3-1': 3,
                'key3-2': 4,
            },
            'key4': ['a', 'b', 'c', {"key4-3-1": 5}],
        }
        self.patch_object(g, '_options', new=options)
        self.assertEqual(g.get_option("key1"), "value1")
        self.assertEqual(g.get_option("key2"), 2)
        self.assertEqual(g.get_option("key3.key3-1"), 3)
        self.assertEqual(g.get_option("key3.key3-2"), 4)
        self.assertEqual(g.get_option("key4.3.key4-3-1"), 5)

    def test_get_options(self):
        options = {
            'key1': 'value1',
            'key2': 2,
            'key3': {
                'key3-1': 3,
                'key3-2': 4,
            },
            'key4': ['a', 'b', 'c', {"key4-3-1": 5}],
        }
        self.patch_object(g, '_options', new=options)
        o = g.get_options()
        self.assertEqual(o.key1, "value1")
        self.assertEqual(o.key2, 2)
        self.assertEqual(o.key3.key3_1, 3)
        self.assertEqual(o.key3.key3_2, 4)
        self.assertEqual(o.key4[3].key4_3_1, 5)

    def test_merge_to_None(self):
        options = {
            'key1': 'value1',
            'key2': 2,
            'key3': {
                'key3-1': 3,
                'key3-2': 4,
            },
            'key4': ['a', 'b', 'c', {"key4-3-1": 5}],
        }
        self.patch_object(g, '_options', new={})
        g.merge(options)
        o = g.get_options()
        self.assertEqual(o.key1, "value1")
        self.assertEqual(o.key2, 2)
        self.assertEqual(o.key3.key3_1, 3)
        self.assertEqual(o.key3.key3_2, 4)
        self.assertEqual(o.key4[3].key4_3_1, 5)

    def test_merge_no_override(self):
        start_options = {
            'key1': 'value0',
            'key5': 'value5',
        }
        options = {
            'key1': 'value1',
            'key2': 2,
            'key3': {
                'key3-1': 3,
                'key3-2': 4,
            },
            'key4': ['a', 'b', 'c', {"key4-3-1": 5}],
        }
        self.patch_object(g, '_options', new=start_options)
        g.merge(options)
        o = g.get_options()
        self.assertEqual(o.key1, "value1")
        self.assertEqual(o.key2, 2)
        self.assertEqual(o.key3.key3_1, 3)
        self.assertEqual(o.key3.key3_2, 4)
        self.assertEqual(o.key4[3].key4_3_1, 5)
        self.assertEqual(o.key5, "value5")

    def test_merge_override(self):
        start_options = {
            'key1': 'value0',
            'key5': 'value5',
        }
        options = {
            'key1': [0, 1, 2, 3, 4],
        }
        self.patch_object(g, '_options', new=start_options)
        with self.assertRaises(KeyError):
            g.merge(options)
        g.merge(options, override=True)
        o = g.get_options()
        self.assertEqual(o.key1[3], 3)
