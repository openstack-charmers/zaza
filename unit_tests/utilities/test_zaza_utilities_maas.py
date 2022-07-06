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

import unittest.mock as mock

import zaza
import zaza.utilities.maas as maas
import unit_tests.utils as ut_utils


class TestUtilitiesMaas(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestUtilitiesMaas, self).setUp()
        self.m1_interface1 = mock.MagicMock()
        self.m1_link1 = mock.MagicMock()
        self.m1_link1.subnet.cidr = '192.0.2.0/24'
        self.m1_link1.mode = maas.LinkMode.LINK_UP
        self.m1_interface2 = mock.MagicMock()
        self.m1_link2 = mock.MagicMock()
        self.m1_link2.subnet.cidr = '198.51.100.0/24'
        self.m1_link2.mode = maas.LinkMode.AUTO
        self.m1_interface2.links.__iter__.return_value = [self.m1_link2]
        self.m1_interface1.links.__iter__.return_value = [self.m1_link1]
        self.machine1 = mock.MagicMock()
        self.machine1.interfaces.__iter__.return_value = [
            self.m1_interface1,
            self.m1_interface2,
        ]

        self.m2_interface1 = mock.MagicMock()
        self.m2_link1 = mock.MagicMock()
        self.m2_link1.subnet.cidr = '192.0.2.0/24'
        self.m2_link1.mode = maas.LinkMode.AUTO
        self.m2_interface2 = mock.MagicMock()
        self.m2_link2 = mock.MagicMock()
        self.m2_link2.subnet.cidr = '198.51.100.0/24'
        self.m2_link2.mode = maas.LinkMode.LINK_UP
        self.m2_interface2.links.__iter__.return_value = [self.m2_link2]
        self.m2_interface1.links.__iter__.return_value = [self.m2_link1]
        self.machine2 = mock.MagicMock()
        self.machine2.interfaces.__iter__.return_value = [
            self.m2_interface1,
            self.m2_interface2,
        ]

        async def f():
            return [self.machine1, self.machine2]
        self.maas_client = mock.MagicMock()
        self.maas_client.machines.list.side_effect = f

    def test_get_maas_client(self):

        async def f(*args, **kwargs):
            pass

        self.patch_object(maas.maas.client, 'connect')
        self.connect.side_effect = f
        try:
            maas.get_maas_client('FakeURL', 'FakeAPIKey')
        finally:
            zaza.clean_up_libjuju_thread()
        self.connect.assert_called_once_with('FakeURL', apikey='FakeAPIKey')

    def test_get_machine_interfaces(self):
        async def af():
            async for machine, interface in maas.async_get_machine_interfaces(
                    self.maas_client):
                if machine == self.machine1:
                    self.assertIn(
                        interface, (self.m1_interface1, self.m1_interface2))
                elif machine == self.machine2:
                    self.assertIn(
                        interface, (self.m2_interface1, self.m2_interface2))
                else:
                    self.assertIn(machine, (self.machine1, self.machine2))
        f = zaza.sync_wrapper(af)
        try:
            f()
        finally:
            zaza.clean_up_libjuju_thread()

    def test_get_macs_from_cidr(self):
        try:
            self.maxDiff = None
            self.assertEquals(
                maas.get_macs_from_cidr(self.maas_client, '192.0.2.0/24'),
                [
                    maas.MachineInterfaceMac(
                        self.machine1.system_id,
                        self.m1_interface1.name,
                        self.m1_interface1.mac_address,
                        '192.0.2.0/24',
                        mock.ANY),
                    maas.MachineInterfaceMac(
                        self.machine2.system_id,
                        self.m2_interface1.name,
                        self.m2_interface1.mac_address,
                        '192.0.2.0/24',
                        mock.ANY),
                ])
            self.assertEquals(
                maas.get_macs_from_cidr(self.maas_client, '192.0.2.0/24',
                                        link_mode=maas.LinkMode.LINK_UP),
                [
                    maas.MachineInterfaceMac(
                        self.machine1.system_id,
                        self.m1_interface1.name,
                        self.m1_interface1.mac_address,
                        '192.0.2.0/24',
                        maas.LinkMode.LINK_UP),
                ])
            self.assertEquals(
                maas.get_macs_from_cidr(self.maas_client, '192.0.2.0/24',
                                        link_mode=maas.LinkMode.AUTO),
                [
                    maas.MachineInterfaceMac(
                        self.machine2.system_id,
                        self.m2_interface1.name,
                        self.m2_interface1.mac_address,
                        '192.0.2.0/24',
                        maas.LinkMode.AUTO),
                ])
            self.assertEquals(
                maas.get_macs_from_cidr(self.maas_client, '198.51.100.0/24'),
                [
                    maas.MachineInterfaceMac(
                        self.machine1.system_id,
                        self.m1_interface2.name,
                        self.m1_interface2.mac_address,
                        '198.51.100.0/24',
                        mock.ANY),
                    maas.MachineInterfaceMac(
                        self.machine2.system_id,
                        self.m2_interface2.name,
                        self.m2_interface2.mac_address,
                        '198.51.100.0/24',
                        mock.ANY),
                ])

            async def fget(*args):
                return self.machine2
            self.maas_client.machines.get.side_effect = fget
            self.assertEquals(
                maas.get_macs_from_cidr(self.maas_client, '198.51.100.0/24',
                                        machine_id=self.machine2.system_id),
                [
                    maas.MachineInterfaceMac(
                        self.machine2.system_id,
                        self.m2_interface2.name,
                        self.m2_interface2.mac_address,
                        '198.51.100.0/24',
                        mock.ANY),
                ])
        finally:
            zaza.clean_up_libjuju_thread()
