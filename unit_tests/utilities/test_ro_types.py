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

"""Unit tets for read-only Dictionaries and Lists."""

import collections
import unittest

import zaza.utilities.ro_types as ro_types


class TestResolveValue(unittest.TestCase):

    def test_resolve_immutable(self):
        self.assertEqual(ro_types.resolve_immutable(5), 5)
        self.assertTrue(isinstance(ro_types.resolve_immutable({}),
                                   ro_types.ReadOnlyDict))
        self.assertEqual(ro_types.resolve_immutable("hello"), "hello")
        self.assertTrue(isinstance(ro_types.resolve_immutable([]),
                                   ro_types.ReadOnlyList))
        self.assertTrue(isinstance(ro_types.resolve_immutable(tuple()),
                                   ro_types.ReadOnlyList))


class TestReadOnlyDict(unittest.TestCase):

    def test_init(self):
        # should only allow things that can be mapped (e.g. dictionary)
        # and that have a copy() function
        with self.assertRaises(AssertionError):
            x = ro_types.ReadOnlyDict([])
        # should work with a dictionary
        x = ro_types.ReadOnlyDict({'a': 1, 'b': 2})
        # should work with an OrderedDict
        x = ro_types.ReadOnlyDict(collections
                                  .OrderedDict([('a', 1), ('b', 2)]))
        # check that the data is copied
        b = {'a': 1}
        x = ro_types.ReadOnlyDict(b)
        b['a'] = 2
        self.assertEqual(x['a'], 1)

    def test_getitem(self):
        x = ro_types.ReadOnlyDict({'a': 1, 'b': 5})
        self.assertEqual(x['a'], 1)
        self.assertEqual(x['b'], 5)
        with self.assertRaises(KeyError):
            x['c']

    def test_getattr(self):
        x = ro_types.ReadOnlyDict({'a': 1, 'b': 5})
        self.assertEqual(x.a, 1)
        self.assertEqual(x.b, 5)
        with self.assertRaises(KeyError):
            x.c

    def test_setattr(self):
        x = ro_types.ReadOnlyDict({'a': 1, 'b': 5})
        with self.assertRaises(TypeError):
            x.c = 1

    def test_setitem(self):
        x = ro_types.ReadOnlyDict({'a': 1, 'b': 5})
        with self.assertRaises(TypeError):
            x['c'] = 1

    def test_iter(self):
        x = ro_types.ReadOnlyDict(collections
                                  .OrderedDict([('a', 1), ('b', 5)]))
        self.assertEqual(list(iter(x)), ['a', 'b'])

    def test_serialize(self):
        x = ro_types.ReadOnlyDict({'a': 1})
        self.assertEqual(x.__serialize__(), {'a': 1})


class TestReadOnlyList(unittest.TestCase):

    def test_create_new_tuple(self):
        x = ro_types.ReadOnlyList([1, 2, 3])
        self.assertEqual(x[0], 1)
        self.assertEqual(x[1], 2)
        self.assertEqual(x[2], 3)
        self.assertEqual(len(x), 3)
        # also check that the dicts and lists become readonly
        x = ro_types.ReadOnlyList([[], {}, 1])
        self.assertTrue(isinstance(x[0], ro_types.ReadOnlyList))
        self.assertTrue(isinstance(x[1], ro_types.ReadOnlyDict))
        # note that it becomes 1, because it was a lambda
        self.assertEqual(x[2], 1)

    def test_iter(self):
        x = ro_types.ReadOnlyList([1, 2, 3])
        self.assertEqual(list(iter(x)), [1, 2, 3])

    def test_repr(self):
        x = ro_types.ReadOnlyList([1, 2, 3])
        self.assertEqual(repr(x), "ReadOnlyList((1, 2, 3))")

    def test_str(self):
        x = ro_types.ReadOnlyList([1, 2, 3])
        self.assertEqual(str(x), "(1, 2, 3)")

    def test_serialize(self):
        x = ro_types.ReadOnlyList([1, 2, 3])
        self.assertEqual(x.__serialize__(), [1, 2, 3])

    def test_is_readonly(self):
        x = ro_types.ReadOnlyList([1, 2, 3])
        with self.assertRaises(TypeError):
            x[0] = 2
        with self.assertRaises(TypeError):
            x.hello = 4
