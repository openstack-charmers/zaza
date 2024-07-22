# Copyright 2020 Canonical Ltd.
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

import unittest
import zaza.utilities.networking as network_utils


class TestUtils(unittest.TestCase):

    def test_format_addr(self):
        self.assertEqual('1.2.3.4', network_utils.format_addr('1.2.3.4'))
        self.assertEqual(
            '[2001:db8::42]', network_utils.format_addr('2001:db8::42'))
        with self.assertRaises(ValueError):
            network_utils.format_addr('999.999.999.999')
        with self.assertRaises(ValueError):
            network_utils.format_addr('2001:db8::g')
