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
        logging.debug('Checking ceph-mon and ceph-osd processes...')
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
        logging.debug('Checking ceph-osd and ceph-mon services...')
        services = {}
        current_release = zaza_openstack.get_os_release()

        xenial_mitaka = zaza_openstack.get_os_release('xenial_mitaka')

        if current_release < xenial_mitaka:
            # For upstart systems only.  Ceph services under systemd
            # are checked by process name instead.
            ceph_services = [
                'ceph-mon-all',
                'ceph-mon id=`hostname`',
            ]
            services['ceph-osd/0'] = [
                'ceph-osd-all',
                'ceph-osd id={}'.format(zaza_ceph.get_ceph_osd_id_cmd(0)),
                'ceph-osd id={}'.format(zaza_ceph.get_ceph_osd_id_cmd(1))
            ]
        else:
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
        logging.debug('Checking ceph-osd:ceph-mon relation data...')
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
        logging.debug('Checking {}:ceph-osd mon relation data...'.
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

    def test_ceph_check_osd_pools(self):
        """Check OSD pools.

        Check osd pools on all ceph units, expect them to be
        identical, and expect specific pools to be present.
        """
        logging.debug('Checking pools on ceph units...')

        expected_pools = zaza_ceph.get_expected_pools()
        results = []
        unit_names = [
            'ceph-osd/0',
            'ceph-mon/0',
            'ceph-mon/1',
            'ceph-mon/2'
        ]

        # Check for presence of expected pools on each unit
        logging.debug('Expected pools: {}'.format(expected_pools))
        for unit_name in unit_names:
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
