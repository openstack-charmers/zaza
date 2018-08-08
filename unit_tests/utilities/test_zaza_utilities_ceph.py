# import mock
import unit_tests.utils as ut_utils
import zaza.utilities.ceph as ceph_utils


class TestCephUtils(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestCephUtils, self).setUp()

    def test_get_ceph_osd_id_cmd(self):
        osd_id = 1
        expected = ("`initctl list | grep 'ceph-osd ' | "
                    "awk 'NR=={} {{ print $2 }}' | "
                    "grep -o '[0-9]*'`".format(osd_id + 1))
        actual = ceph_utils.get_ceph_osd_id_cmd(osd_id)
        self.assertEqual(expected, actual)
