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
import zaza.openstack.utilities.openstack as openstack_utils

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


def _svc_set_systemd_restart_mode(unit_name, service_name, mode, model_name):
    """Update the restart mode of the given systemd service.

    :param unit_name: Juju name of unit (app/n)
    :type unit_name: str
    :param service_name: Name of systemd service to update
    :type service_name: str
    :param mode: Restart mode to switch to eg 'no', 'on-success', 'on-failure',
                 'on-abort' or 'always'
    :type mode: str
    :param model_name: Name of model unit_name resides in.
    :type model_name: str
    """
    # Restart options include: no, on-success, on-failure, on-abort or always
    logging.info('Setting systemd restart mode for {} to {}'.format(
        service_name,
        mode))
    cmds = [
        ("sed -i -e 's/^Restart=.*/Restart={}/g' "
         "/lib/systemd/system/{}.service'").format(mode, service_name),
        'systemctl daemon-reload']
    logging.info('Running {} on {}'.format(cmds, unit_name))
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
    _svc_set_systemd_restart_mode(
        unit_name,
        'pacemaker_remote',
        'no',
        model_name)
    _svc_control(
        unit_name,
        'stop',
        ['corosync', 'nova-compute'],
        model_name)
    logging.info('Sending pacemaker_remoted a SIGTERM')
    zaza.model.run_on_unit(
        unit_name,
        'pkill -9 -f /usr/sbin/pacemaker_remoted',
        model_name=model_name)


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
    _svc_set_systemd_restart_mode(
        unit_name,
        'pacemaker_remote',
        'on-failure',
        model_name)
    _svc_control(
        unit_name,
        'start',
        ['corosync', 'pacemaker_remote', 'nova-compute'],
        model_name)


def simulate_guest_crash(guest_pid, compute_unit_name, model_name):
    """Simulate a guest crashing.

    :param guest_pid: PID of running qemu provess for guest.
    :type guest_pid: str
    :param compute_unit_name: Juju name of hypervisor hosting guest (app/n)
    :type compute_unit_name: str
    :param model_name: Name of model unit_name resides in.
    :type model_name: str
    """
    pid_kill_cmd = 'kill -9 {}'
    zaza.model.run_on_unit(
        compute_unit_name,
        pid_kill_cmd.format(guest_pid),
        model_name=model_name)
