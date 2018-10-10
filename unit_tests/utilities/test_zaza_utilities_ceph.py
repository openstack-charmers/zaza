import unit_tests.utils as ut_utils
import zaza.model as model
import zaza.utilities.ceph as ceph_utils
import zaza.utilities.openstack as openstack_utils


class TestCephUtils(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestCephUtils, self).setUp()

    def _test_expected_pools(self,
                             os_release_pair,
                             expected_pools,
                             radosgw=False):
        self.get_current_os_release_pair.return_value = os_release_pair
        actual_pools = ceph_utils.get_expected_pools(radosgw)
        self.assertEqual(expected_pools, actual_pools)

    def test_get_expected_pools(self):
        self.patch_object(openstack_utils, 'get_current_os_release_pair')

        # Trusty Icehouse
        os_release_pair = 'trusty_icehouse'
        self.get_current_os_release_pair.return_value = 'trusty_icehouse'
        expected_pools = [
            'data',
            'metadata',
            'rbd',
            'cinder-ceph',
            'glance'
        ]
        self._test_expected_pools(os_release_pair, expected_pools)

        # Xenial Ocata
        os_release_pair = 'xenial_ocata'
        expected_pools = [
            'rbd',
            'cinder-ceph',
            'glance'
        ]
        self._test_expected_pools(os_release_pair, expected_pools)

        # Xenial Queens
        os_release_pair = 'xenial_queens'
        expected_pools = [
            'cinder-ceph',
            'glance'
        ]
        self._test_expected_pools(os_release_pair, expected_pools)

        # Xenial Queens with radosgw
        os_release_pair = 'xenial_queens'
        expected_pools = [
            'cinder-ceph',
            'glance',
            '.rgw.root',
            '.rgw.control',
            '.rgw',
            '.rgw.gc',
            '.users.uid'
        ]
        self._test_expected_pools(os_release_pair, expected_pools, True)

    def test_get_ceph_pools(self):
        self.patch_object(model, 'run_on_unit')

        # Bad return code
        result = {
            'Code': '1',
            'Stdout': '',
            'Stderr': 'something went wrong',
        }
        self.run_on_unit.return_value = result
        with self.assertRaises(model.CommandRunFailed):
            ceph_utils.get_ceph_pools('ceph-mon/0')

        # Xenial Queens output
        result = {
            'Code': '0',
            'Stdout': '1 cinder-ceph,2 glance,',
            'Stderr': ''
        }
        self.run_on_unit.return_value = result
        expected = {
            'cinder-ceph': 1,
            'glance': 2
        }
        actual = ceph_utils.get_ceph_pools('ceph-mon/0')
        self.assertEqual(expected, actual)
        # Bionic Queens output
        result = {
            'Code': '0',
            'Stdout': '1 cinder-ceph\n2 glance',
            'Stderr': ''
        }
        self.run_on_unit.return_value = result
        expected = {
            'cinder-ceph': 1,
            'glance': 2
        }
        actual = ceph_utils.get_ceph_pools('ceph-mon/0')
        self.assertEqual(expected, actual)
