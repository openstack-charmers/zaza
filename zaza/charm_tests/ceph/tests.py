# Copyright 2018 Canonical Ltd.
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

"""Ceph-osd Testing."""

import logging
from os import (
    listdir,
    path
)
import tempfile

import zaza.charm_tests.test_utils as test_utils
import zaza.model as zaza_model
import zaza.utilities.ceph as zaza_ceph
import zaza.utilities.exceptions as zaza_exceptions
import zaza.utilities.generic as zaza_utils
import zaza.utilities.juju as zaza_juju
import zaza.utilities.openstack as zaza_openstack


class CephLowLevelTest(test_utils.OpenStackBaseTest):
    """Ceph Low Level Test Class."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running ceph low level tests."""
        super(CephLowLevelTest, cls).setUpClass()

    def test_processes(self):
        """Verify Ceph processes.

        Verify that the expected service processes are running
        on each ceph unit.
        """
        logging.info('Checking ceph-mon and ceph-osd processes...')
        # Process name and quantity of processes to expect on each unit
        ceph_mon_processes = {
            'ceph-mon': 1,
        }

        ceph_osd_processes = {
            'ceph-osd': [2, 3]
        }

        # Units with process names and PID quantities expected
        expected_processes = {
            'ceph-mon/0': ceph_mon_processes,
            'ceph-mon/1': ceph_mon_processes,
            'ceph-mon/2': ceph_mon_processes,
            'ceph-osd/0': ceph_osd_processes,
            'ceph-osd/1': ceph_osd_processes,
            'ceph-osd/2': ceph_osd_processes
        }

        actual_pids = zaza_utils.get_unit_process_ids(expected_processes)
        ret = zaza_utils.validate_unit_process_ids(expected_processes,
                                                   actual_pids)
        self.assertTrue(ret)

    def test_services(self):
        """Verify the ceph services.

        Verify the expected services are running on the service units.
        """
        logging.info('Checking ceph-osd and ceph-mon services...')
        services = {}
        ceph_services = ['ceph-mon']
        services['ceph-osd/0'] = ['ceph-osd']

        services['ceph-mon/0'] = ceph_services
        services['ceph-mon/1'] = ceph_services
        services['ceph-mon/2'] = ceph_services

        for unit_name, unit_services in services.items():
            zaza_model.block_until_service_status(
                unit_name=unit_name,
                services=unit_services,
                target_status='running'
            )


class CephRelationTest(test_utils.OpenStackBaseTest):
    """Ceph's relations test class."""

    @classmethod
    def setUpClass(cls):
        """Run the ceph's relations class setup."""
        super(CephRelationTest, cls).setUpClass()

    def test_ceph_osd_ceph_relation_address(self):
        """Verify the ceph-osd to ceph relation data."""
        logging.info('Checking ceph-osd:ceph-mon relation data...')
        unit_name = 'ceph-osd/0'
        remote_unit_name = 'ceph-mon/0'
        relation_name = 'osd'
        remote_unit = zaza_model.get_unit_from_name(remote_unit_name)
        remote_ip = remote_unit.public_address
        relation = zaza_juju.get_relation_from_unit(
            unit_name,
            remote_unit_name,
            relation_name
        )
        # Get private-address in relation
        rel_private_ip = relation.get('private-address')
        # The private address in relation should match ceph-mon/0 address
        self.assertEqual(rel_private_ip, remote_ip)

    def _ceph_to_ceph_osd_relation(self, remote_unit_name):
        """Verify the cephX to ceph-osd relation data.

        Helper function to test the relation.
        """
        logging.info('Checking {}:ceph-osd mon relation data...'.
                     format(remote_unit_name))
        unit_name = 'ceph-osd/0'
        relation_name = 'osd'
        remote_unit = zaza_model.get_unit_from_name(remote_unit_name)
        remote_ip = remote_unit.public_address
        cmd = 'leader-get fsid'
        result = zaza_model.run_on_unit(remote_unit_name, cmd)
        fsid = result.get('Stdout').strip()
        expected = {
            'private-address': remote_ip,
            'auth': 'none',
            'ceph-public-address': remote_ip,
            'fsid': fsid,
        }
        relation = zaza_juju.get_relation_from_unit(
            unit_name,
            remote_unit_name,
            relation_name
        )
        for e_key, e_value in expected.items():
            a_value = relation[e_key]
            self.assertEqual(e_value, a_value)
        self.assertTrue(relation['osd_bootstrap_key'] is not None)

    def test_ceph0_to_ceph_osd_relation(self):
        """Verify the ceph0 to ceph-osd relation data."""
        remote_unit_name = 'ceph-mon/0'
        self._ceph_to_ceph_osd_relation(remote_unit_name)

    def test_ceph1_to_ceph_osd_relation(self):
        """Verify the ceph1 to ceph-osd relation data."""
        remote_unit_name = 'ceph-mon/1'
        self._ceph_to_ceph_osd_relation(remote_unit_name)

    def test_ceph2_to_ceph_osd_relation(self):
        """Verify the ceph2 to ceph-osd relation data."""
        remote_unit_name = 'ceph-mon/2'
        self._ceph_to_ceph_osd_relation(remote_unit_name)


class CephTest(test_utils.OpenStackBaseTest):
    """Ceph common functional tests."""

    @classmethod
    def setUpClass(cls):
        """Run the ceph's common class setup."""
        super(CephTest, cls).setUpClass()

    def osd_out_in(self, services):
        """Run OSD out and OSD in tests.

        Remove OSDs and then add them back in on a unit checking that services
        are in the required state after each action

        :param services: Services expected to be restarted when config_file is
                         changed.
        :type services: list
        """
        zaza_model.block_until_service_status(
            self.lead_unit,
            services,
            'running',
            model_name=self.model_name)
        zaza_model.block_until_unit_wl_status(
            self.lead_unit,
            'active',
            model_name=self.model_name)
        zaza_model.run_action(
            self.lead_unit,
            'osd-out',
            model_name=self.model_name)
        zaza_model.block_until_unit_wl_status(
            self.lead_unit,
            'maintenance',
            model_name=self.model_name)
        zaza_model.block_until_all_units_idle(model_name=self.model_name)
        zaza_model.run_action(
            self.lead_unit,
            'osd-in',
            model_name=self.model_name)
        zaza_model.block_until_unit_wl_status(
            self.lead_unit,
            'active',
            model_name=self.model_name)
        zaza_model.block_until_all_units_idle(model_name=self.model_name)
        zaza_model.block_until_service_status(
            self.lead_unit,
            services,
            'running',
            model_name=self.model_name)

    def test_ceph_check_osd_pools(self):
        """Check OSD pools.

        Check osd pools on all ceph units, expect them to be
        identical, and expect specific pools to be present.
        """
        logging.info('Checking pools on ceph units...')

        expected_pools = zaza_ceph.get_expected_pools()
        results = []
        unit_name = 'ceph-mon/0'

        # Check for presence of expected pools on each unit
        logging.debug('Expected pools: {}'.format(expected_pools))
        pools = zaza_ceph.get_ceph_pools(unit_name)
        results.append(pools)

        for expected_pool in expected_pools:
            if expected_pool not in pools:
                msg = ('{} does not have pool: '
                       '{}'.format(unit_name, expected_pool))
                raise zaza_exceptions.CephPoolNotFound(msg)
        logging.debug('{} has (at least) the expected '
                      'pools.'.format(unit_name))

        # Check that all units returned the same pool name:id data
        for i, result in enumerate(results):
            for other in results[i+1:]:
                logging.debug('result: {}, other: {}'.format(result, other))
                self.assertEqual(result, other)

    def test_ceph_pool_creation_with_text_file(self):
        """Check the creation of a pool and a text file.

        Create a pool, add a text file to it and retrieve its content.
        Verify that the content matches the original file.
        """
        unit_name = 'ceph-mon/0'
        cmd = 'sudo ceph osd pool create test 128; \
               echo 123456789 > /tmp/input.txt; \
               rados put -p test test_input /tmp/input.txt; \
               rados get -p test test_input /dev/stdout'
        logging.debug('Creating test pool and putting test file in pool...')
        result = zaza_model.run_on_unit(unit_name, cmd)
        code = result.get('Code')
        if code != '0':
            raise zaza_model.CommandRunFailed(cmd, result)
        output = result.get('Stdout').strip()
        logging.debug('Output received: {}'.format(output))
        self.assertEqual(output, '123456789')

    def test_ceph_encryption(self):
        """Test Ceph encryption.

        Verify that the new disk is added with encryption by checking for
        Ceph's encryption keys directory.
        """
        current_release = zaza_openstack.get_os_release()
        trusty_mitaka = zaza_openstack.get_os_release('trusty_mitaka')
        if current_release >= trusty_mitaka:
            logging.warn("Skipping encryption test for Mitaka and higher")
            return
        unit_name = 'ceph-osd/0'
        set_default = {
            'osd-encrypt': 'False',
            'osd-devices': '/dev/vdb /srv/ceph',
        }
        set_alternate = {
            'osd-encrypt': 'True',
            'osd-devices': '/dev/vdb /srv/ceph /srv/ceph_encrypted',
        }
        juju_service = 'ceph-osd'
        logging.info('Making config change on {}...'.format(juju_service))
        mtime = zaza_model.get_unit_time(unit_name)

        file_mtime = None

        folder_name = '/etc/ceph/dmcrypt-keys/'
        with self.config_change(set_default, set_alternate,
                                application_name=juju_service):
            with tempfile.TemporaryDirectory() as tempdir:
                # Creating a temp dir to copy keys
                temp_folder = '/tmp/dmcrypt-keys'
                cmd = 'mkdir {}'.format(temp_folder)
                ret = zaza_model.run_on_unit(unit_name, cmd)
                logging.debug('Ret for cmd {} is {}'.format(cmd, ret))
                # Copy keys from /etc to /tmp
                cmd = 'sudo cp {}* {}'.format(folder_name, temp_folder)
                ret = zaza_model.run_on_unit(unit_name, cmd)
                logging.debug('Ret for cmd {} is {}'.format(cmd, ret))
                # Changing permissions to be able to SCP the files
                cmd = 'sudo chown -R ubuntu:ubuntu {}'.format(temp_folder)
                ret = zaza_model.run_on_unit(unit_name, cmd)
                logging.debug('Ret for cmd {} is {}'.format(cmd, ret))
                # SCP to retrieve all files in folder
                # -p: preserve timestamps
                source = '/tmp/dmcrypt-keys/*'
                zaza_model.scp_from_unit(unit_name=unit_name,
                                         source=source,
                                         destination=tempdir,
                                         scp_opts='-p')
                for elt in listdir(tempdir):
                    file_path = '/'.join([tempdir, elt])
                    if path.isfile(file_path):
                        file_mtime = path.getmtime(file_path)
                        if file_mtime:
                            break

        if not file_mtime:
            logging.warn('Could not determine mtime, assuming '
                         'folder does not exist')
            raise FileNotFoundError('folder does not exist')

        if file_mtime >= mtime:
            logging.info('Folder mtime is newer than provided mtime '
                         '(%s >= %s) on %s (OK)' % (file_mtime,
                                                    mtime, unit_name))
        else:
            logging.warn('Folder mtime is older than provided mtime'
                         '(%s < on %s) on %s' % (file_mtime,
                                                 mtime, unit_name))
            raise Exception('Folder mtime is older than provided mtime')

    def test_blocked_when_non_pristine_disk_appears(self):
        """Test blocked state with non-pristine disk.

        Validate that charm goes into blocked state when it is presented with
        new block devices that have foreign data on them.
        Instances used in UOSCI has a flavour with ephemeral storage in
        addition to the bootable instance storage.  The ephemeral storage
        device is partitioned, formatted and mounted early in the boot process
        by cloud-init.
        As long as the device is mounted the charm will not attempt to use it.
        If we unmount it and trigger the config-changed hook the block device
        will appear as a new and previously untouched device for the charm.
        One of the first steps of device eligibility checks should be to make
        sure we are seeing a pristine and empty device before doing any
        further processing.
        As the ephemeral device will have data on it we can use it to validate
        that these checks work as intended.
        """
        logging.info('Checking behaviour when non-pristine disks appear...')
        logging.info('Configuring ephemeral-unmount...')
        alternate_conf = {
            'ephemeral-unmount': '/mnt',
            'osd-devices': '/dev/vdb'
        }
        juju_service = 'ceph-osd'
        zaza_model.set_application_config(juju_service, alternate_conf)
        ceph_osd_states = {
            'ceph-osd': {
                'workload-status': 'blocked',
                'workload-status-message': 'Non-pristine'
            }
        }
        zaza_model.wait_for_application_states(states=ceph_osd_states)
        logging.info('Units now in blocked state, running zap-disk action...')
        unit_names = ['ceph-osd/0', 'ceph-osd/1', 'ceph-osd/2']
        for unit_name in unit_names:
            zap_disk_params = {
                'devices': '/dev/vdb',
                'i-really-mean-it': True,
            }
            action_obj = zaza_model.run_action(
                unit_name=unit_name,
                action_name='zap-disk',
                action_params=zap_disk_params
            )
            logging.debug('Result of action: {}'.format(action_obj))

        logging.info('Running add-disk action...')
        for unit_name in unit_names:
            add_disk_params = {
                'osd-devices': '/dev/vdb',
            }
            action_obj = zaza_model.run_action(
                unit_name=unit_name,
                action_name='add-disk',
                action_params=add_disk_params
            )
            logging.debug('Result of action: {}'.format(action_obj))

        logging.info('Wait for idle/ready status...')
        zaza_model.wait_for_application_states()

        logging.info('OK')

        set_default = {
            'ephemeral-unmount': '',
            'osd-devices': '/dev/vdb /srv/ceph',
        }

        logging.info('Restoring to default configuration...')
        zaza_model.set_application_config(juju_service, set_default)

        zaza_model.wait_for_application_states()

    def test_pause_and_resume(self):
        """The services can be paused and resumed."""
        logging.info('Checking pause and resume actions...')
        self.pause_resume(['ceph-osd'])

    def test_blacklist(self):
        """Check the blacklist action.

        The blacklist actions execute and behave as expected.
        """
        logging.info('Checking blacklist-add-disk and'
                     'blacklist-remove-disk actions...')
        unit_name = 'ceph-osd/0'

        zaza_model.block_until_unit_wl_status(
            unit_name,
            'active'
        )

        # Attempt to add device with non-absolute path should fail
        action_obj = zaza_model.run_action(
            unit_name=unit_name,
            action_name='blacklist-add-disk',
            action_params={'osd-devices': 'vda'}
        )
        self.assertTrue(action_obj.status != 'completed')
        zaza_model.block_until_unit_wl_status(
            unit_name,
            'active'
        )

        # Attempt to add device with non-existent path should fail
        action_obj = zaza_model.run_action(
            unit_name=unit_name,
            action_name='blacklist-add-disk',
            action_params={'osd-devices': '/non-existent'}
        )
        self.assertTrue(action_obj.status != 'completed')
        zaza_model.block_until_unit_wl_status(
            unit_name,
            'active'
        )

        # Attempt to add device with existent path should succeed
        action_obj = zaza_model.run_action(
            unit_name=unit_name,
            action_name='blacklist-add-disk',
            action_params={'osd-devices': '/dev/vda'}
        )
        self.assertEqual('completed', action_obj.status)
        zaza_model.block_until_unit_wl_status(
            unit_name,
            'active'
        )

        # Attempt to remove listed device should always succeed
        action_obj = zaza_model.run_action(
            unit_name=unit_name,
            action_name='blacklist-remove-disk',
            action_params={'osd-devices': '/dev/vda'}
        )
        self.assertEqual('completed', action_obj.status)
        zaza_model.block_until_unit_wl_status(
            unit_name,
            'active'
        )
        logging.debug('OK')

    def test_list_disks(self):
        """Test the list-disks action.

        The list-disks action execute.
        """
        logging.info('Checking list-disks action...')
        unit_name = 'ceph-osd/0'

        zaza_model.block_until_unit_wl_status(
            unit_name,
            'active'
        )

        action_obj = zaza_model.run_action(
            unit_name=unit_name,
            action_name='list-disks',
        )
        self.assertEqual('completed', action_obj.status)
        zaza_model.block_until_unit_wl_status(
            unit_name,
            'active'
        )
        logging.debug('OK')


class CephRGWDaemonTest(test_utils.OpenStackBaseTest):
    """Ceph RADOS Gateway Daemons Test Class."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running ceph low level tests."""
        super(CephRGWDaemonTest, cls).setUpClass()

    def test_processes(self):
        """Verify Ceph processes.

        Verify that the expected service processes are running
        on each ceph unit.
        """
        logging.info('Checking radosgw processes...')
        # Process name and quantity of processes to expect on each unit
        ceph_radosgw_processes = {
            'radosgw': 1,
        }

        # Units with process names and PID quantities expected
        expected_processes = {
            'ceph-radosgw/0': ceph_radosgw_processes,
        }

        actual_pids = zaza_utils.get_unit_process_ids(expected_processes)
        ret = zaza_utils.validate_unit_process_ids(expected_processes,
                                                   actual_pids)
        self.assertTrue(ret)

    def test_services(self):
        """Verify the ceph services.

        Verify the expected services are running on the service units.
        """
        logging.info('Checking radosgw services...')
        current_release = zaza_openstack.get_os_release()
        xenial_mitaka = zaza_openstack.get_os_release('xenial_mitaka')
        for unit in zaza_model.get_units('ceph-radosgw'):
            if current_release >= xenial_mitaka:
                result = zaza_model.run_on_unit(unit.entity_id, 'hostname')
                hostname = result['Stdout'].rstrip()
                services = ['ceph-radosgw@rgw.{hostname}'.format(hostname),
                            'haproxy']
            else:
                services = ['radosgw', 'haproxy']
            zaza_model.block_until_service_status(
                unit_name=unit.entity_id,
                services=services,
                target_status='running'
            )
