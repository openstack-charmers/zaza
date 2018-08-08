"""Ceph-osd Testing."""

import zaza.charm_tests.test_utils as test_utils
import zaza.utilities.ceph as zaza_ceph
import zaza.utilities.generic as zaza_utils
import zaza.utilities.openstack as zaza_openstack
import zaza.model as model


class CephOsdLowLevelTest(test_utils.OpenStackBaseTest):
    """Ceph-OSD Test Class."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running ceph-osd tests."""
        super(CephOsdLowLevelTest, cls).setUpClass()

    def test_processes(self):
        """Verify Ceph processes.

        Verify that the expected service processes are running
        on each ceph unit.
        """
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
            model.block_until_service_status(
                unit_name=unit_name,
                services=unit_services,
                target_status='running'
            )
