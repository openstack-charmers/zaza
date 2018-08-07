"""Ceph-osd Testing."""

import zaza.charm_tests.test_utils as test_utils
import zaza.utilities.generic as zaza_utils


class CephOsdLowLevelTest(test_utils.OpenStackBaseTest):
    """Ceph-OSD Test Class."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running ceph-osd tests."""
        super(CephOsdLowLevelTest, cls).setUpClass()

    def test_ceph_processes(self):
        """Verify Ceph processes.

        Verify that the expected service processes are running
        on each ceph unit.
        """
        # Process name and quantity of processes to expect on each unit
        ceph_mon_processes = {
            'ceph-mon': 1,
        }

        ceph_osd_processes = {
            "ceph-osd": [2, 3]
        }

        # Units with process names and PID quantities expected
        expected_processes = {
            "ceph-mon/0": ceph_mon_processes,
            "ceph-mon/1": ceph_mon_processes,
            "ceph-mon/2": ceph_mon_processes,
            "ceph-osd/0": ceph_osd_processes,
            "ceph-osd/1": ceph_osd_processes,
            "ceph-osd/2": ceph_osd_processes
        }

        actual_pids = zaza_utils.get_unit_process_ids(expected_processes)
        ret = zaza_utils.validate_unit_process_ids(expected_processes,
                                                   actual_pids)
        self.assertTrue(ret)
