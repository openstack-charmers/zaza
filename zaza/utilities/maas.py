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
"""Module for interacting with MAAS."""

import collections

from async_generator import async_generator, yield_

import maas.client
import maas.client.enum

# Re-export the LinkMode enum to save our consumers the trouble of figuring out
# the python-libmaas internal module path to it.
from maas.client.enum import LinkMode  # noqa

import zaza


def get_maas_client_from_juju_cloud_data(cloud_data):
    """Get a connected MAAS client from Juju Cloud data.

    :param cloud_data: Juju Cloud and Credential data
    :type cloud_data: zaza.model.CloudData
    :returns: Connected MAAS client.
    :rtpye: maas.client.facade.Client object.
    :raises: AssertionError
    """
    assert cloud_data.cloud.type_ == 'maas', "cloud_data not for MAAS cloud."
    maas_url = cloud_data.cloud['endpoint']
    apikey = cloud_data.credential['attrs']['maas-oauth']
    return get_maas_client(maas_url, apikey)


async def async_get_maas_client(maas_url, apikey):
    """Get a connected MAAS client.

    :param maas_url: URL to MAAS API.
    :type maas_url: str
    :param apikey: MAAS API Key for authentication.
    :type apikey: str
    :returns: Connected MAAS client.
    :rtpye: maas.client.facade.Client object.
    """
    return await maas.client.connect(maas_url, apikey=apikey)

get_maas_client = zaza.sync_wrapper(async_get_maas_client)


@async_generator
async def async_get_machine_interfaces(maas_client, machine_id=None,
                                       link_mode=None, cidr=None):
    """Get machine and interface objects, optionally apply filters.

    :param maas_client: MAAS Client object.
    :type maas_client: maas.client.facade.Client
    :param machine_id: ID of a specific machine to get information on.
    :type machine_id: Optional[str]
    :param link_mode: Only return interfaces with this link_mode.
    :type link_mode: Optional[LinkMode]
    :param cidr: Only return interfaces connected this CIDR.
    :type cidr: Optional[str]
    :returns: Async generator object
    :rtype: async Iterator[maas.client.viscera.machines.Machine,
                           maas.client.viscera.interfaces.Interface]
    """
    if machine_id:
        machines = [await maas_client.machines.get(machine_id)]
    else:
        machines = await maas_client.machines.list()
    for machine in machines:
        for interface in machine.interfaces:
            for link in interface.links:
                if link_mode and link.mode != link_mode:
                    continue
                if cidr and (link.subnet is None or link.subnet.cidr != cidr):
                    continue
                await yield_((machine, interface))


MachineInterfaceMac = collections.namedtuple(
    'MachineInterfaceMac',
    ['machine_id', 'ifname', 'mac', 'cidr', 'link_mode'])


async def async_get_macs_from_cidr(maas_client, cidr, machine_id=None,
                                   link_mode=None):
    """Get interface mac addresses from machines connected to cidr.

    :param maas_client: MAAS Client object.
    :type maas_client: maas.client.facade.Client
    :param cidr: Only return interfaces connected this CIDR.
    :type cidr: str
    :param machine_id: ID of a specific machine to get information on.
    :type machine_id: Optional[str]
    :param link_mode: Only return interfaces with this link_mode.
    :type link_mode: Optional[LinkMode]
    :returns: List of MachineInterfaceMac tuples.
    :rtype: List[MachineInterfaceMac[str,str,str,str,LinkMode]]
    """
    # We build a list and return that as async generators are a bit too much to
    # spring on a causal consumer of this module.
    result = []
    async for machine, interface in async_get_machine_interfaces(
            maas_client, machine_id=machine_id,
            link_mode=link_mode, cidr=cidr):
        for link in interface.links:
            result.append(MachineInterfaceMac(
                machine.system_id, interface.name, interface.mac_address,
                link.subnet.cidr, link.mode))
    return result

get_macs_from_cidr = zaza.sync_wrapper(async_get_macs_from_cidr)
