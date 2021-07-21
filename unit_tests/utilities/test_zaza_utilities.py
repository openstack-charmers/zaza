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

"""Unit tests for the __init__.py functions."""

import collections
import unittest

import zaza.utilities


class TestConfigurableMixin(unittest.TestCase):

    def test_sets_attributes(self):

        class A(zaza.utilities.ConfigurableMixin):

            def __init__(self, **kwargs):
                self.a = None
                self.b = 1
                self.configure(**kwargs)

        a = A(a=4)
        self.assertEqual(a.a, 4)
        self.assertEqual(a.b, 1)
        a.configure(b=9)
        self.assertEqual(a.b, 9)

    def test_doesnt_instantiate_attributes(self):

        class A(zaza.utilities.ConfigurableMixin):

            def __init__(self, **kwargs):
                self.a = None
                self.configure(**kwargs)

        with self.assertRaises(AttributeError):
            a = A(a=5, b=10)

    def test_cant_set_hidden(self):

        class A(zaza.utilities.ConfigurableMixin):

            def __init__(self, **kwargs):
                self.a = None
                self._b = 3
                self.configure(**kwargs)

        with self.assertRaises(AttributeError):
            a = A(_b=4)
        a = A()
        a.configure(a=10)
        self.assertEqual(a.a, 10)
        with self.assertRaises(AttributeError):
            a.configure(_b=8)

    def test_cant_set_properties(self):

        class A(zaza.utilities.ConfigurableMixin):

            def __init__(self):
                self.a = 10

            @property
            def b():
                return 5

        a = A()
        a.configure(a=5)
        with self.assertRaises(AttributeError):
            a.configure(a=3, b=10)


    def test_cant_set_methods(self):

        class A(zaza.utilities.ConfigurableMixin):

            def __init__(self):
                self.a = 10

            def b():
                return 5

        a = A()
        a.configure(a=5)
        with self.assertRaises(AttributeError):
            a.configure(a=3, b=10)
