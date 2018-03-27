import os
import tempfile
import yaml

import zaza.charm_lifecycle.utils as lc_utils
import unit_tests.utils as ut_utils


class TestCharmLifecycleUtils(ut_utils.BaseTestCase):

    def test_get_charm_config(self):
        f = tempfile.NamedTemporaryFile(delete=False, mode='w')
        f.write(yaml.dump({'test_config': 'someconfig'}))
        f.close()
        charm_config = lc_utils.get_charm_config(yaml_file=f.name)
        os.unlink(f.name)
        self.assertEqual(charm_config, {'test_config': 'someconfig'})

    def test_get_class(self):
        self.assertEqual(
            type(lc_utils.get_class('unit_tests.'
                                    'test_zaza_charm_lifecycle_utils.'
                                    'TestCharmLifecycleUtils')()),
            type(self))
