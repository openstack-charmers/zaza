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

"""Configure and manage masakari.

Functions for managing masakari resources and simulating compute node loss
and recovery.
"""

import logging

import zaza.model
import zaza.utilities.openstack as openstack_utils

ROUND_ROBIN = 'round-robin'


def roundrobin_assign_hosts_to_segments(nova_client, masakari_client):
    """Assign hypervisors to segments in a round-robin fashion.

    :param nova_client: Authenticated nova client
    :type nova_client: novaclient.Client
    :param masakari_client: Authenticated masakari client
    :type masakari_client: openstack.instance_ha.v1._proxy.Proxy
    """
    hypervisors = nova_client.hypervisors.list()
    segment_ids = [s.uuid for s in masakari_client.segments()]
    segment_ids = segment_ids * len(hypervisors)
    for hypervisor in hypervisors:
        target_segment = segment_ids.pop()
        hostname = hypervisor.hypervisor_hostname.split('.')[0]
        logging.info('Adding {} to segment {}'.format(hostname,
                                                      target_segment))
        masakari_client.create_host(
            name=hostname,
            segment_id=target_segment,
            recovery_method='auto',
            control_attributes='SSH',
            type='COMPUTE')


HOST_ASSIGNMENT_METHODS = {
    ROUND_ROBIN: roundrobin_assign_hosts_to_segments
}


def create_segments(segment_number=1, host_assignment_method=None):
    """Create a masakari segment and populate it with hypervisors.

    :param segment_number: Number of segments to create
    :type segment_number: int
    :param host_assignment_method: Method to use to assign hypervisors to
                                   segments
    :type host_assignment_method: f()
    """
    host_assignment_method = host_assignment_method or ROUND_ROBIN
    keystone_session = openstack_utils.get_overcloud_keystone_session()
    nova_client = openstack_utils.get_nova_session_client(keystone_session)
    masakari_client = openstack_utils.get_masakari_session_client(
        keystone_session)
    for segment_number in range(0, segment_number):
        segment_name = 'seg{}'.format(segment_number)
        logging.info('Creating segment {}'.format(segment_name))
        masakari_client.create_segment(
            name=segment_name,
            recovery_method='auto',
            service_type='COMPUTE')
    HOST_ASSIGNMENT_METHODS[host_assignment_method](
        nova_client,
        masakari_client)


def enable_hosts(masakari_client=None):
    """Enable all hypervisors within masakari.

    Enable all hosts across all segments within masakari. This does not
    enable the hypervisor from a nova POV.

    :param masakari_client: Authenticated masakari client
    :type masakari_client: openstack.instance_ha.v1._proxy.Proxy
    """
    if not masakari_client:
        keystone_session = openstack_utils.get_overcloud_keystone_session()
        masakari_client = openstack_utils.get_masakari_session_client(
            keystone_session)

    for segment in masakari_client.segments():
        for host in masakari_client.hosts(segment_id=segment.uuid):
            if host.on_maintenance:
                logging.info("Removing maintenance mode from masakari "
                             "host {}".format(host.uuid))
                masakari_client.update_host(
                    host.uuid,
                    segment_id=segment.uuid,
                    **{'on_maintenance': False})


def _svc_control(unit_name, action, services, model_name):
    """Enable/Disable services on a unit.

    This is a simplistic method for controlling services, hence its private.

    :param unit_name: Juju name of unit (app/n)
    :type unit_name: str
    :param action: systemctl action to perform on unit (start/stop etc)
    :type action: str
    :param services: List of services to perform action against
    :type services: []
    :param model_name: Name of model unit_name resides in.
    :type model_name: str
    """
    logging.info('{} {} on {}'.format(action.title(), services, unit_name))
    cmds = []
    for svc in services:
        cmds.append("systemctl {} {}".format(action, svc))
    zaza.model.run_on_unit(
        unit_name, command=';'.join(cmds),
        model_name=model_name)


def simulate_compute_host_failure(unit_name, model_name):
    """Simulate compute node failure from a masakari and nova POV.

    Masakari uses corosync/pacemaker to detect failure and nova check
    nova-compute. Shutting down these services causes masakari and nova to
    mark them as down.

    :param unit_name: Juju name of unit (app/n)
    :type unit_name: str
    :param model_name: Name of model unit_name resides in.
    :type model_name: str
    """
    logging.info('Simulating failure of compute node {}'.format(unit_name))
    _svc_control(
        unit_name,
        'stop',
        ['corosync', 'pacemaker', 'nova-compute'],
        model_name)


def simulate_compute_host_recovery(unit_name, model_name):
    """Simulate compute node recovery from a masakari and nova POV.

    Masakari uses corosync/pacemaker to detect failure and nova check
    nova-compute. Starting these services is a prerequisite to marking
    them as recovered.

    :param unit_name: Juju name of unit (app/n)
    :type unit_name: str
    :param model_name: Name of model unit_name resides in.
    :type model_name: str
    """
    logging.info('Simulating recovery of compute node {}'.format(unit_name))
    _svc_control(
        unit_name,
        'start',
        ['corosync', 'pacemaker', 'nova-compute'],
        model_name)
