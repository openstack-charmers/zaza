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

import zaza.charm_lifecycle.destroy as lc_destroy
import unit_tests.utils as ut_utils


class TestCharmLifecycleDestroy(ut_utils.BaseTestCase):

    def test_destroy(self):
        self.patch_object(lc_destroy.zaza.controller, 'destroy_model')
        self.patch_object(lc_destroy.model, 'get_status',
                          return_value={'machines': "the-machines"})
        self.patch_object(lc_destroy.juju_utils, 'get_provider_type',
                          return_value="maas")
        self.patch("zaza.utilities.openstack_provider.clean_up_instances",
                   name='clean_up_instances')
        lc_destroy.destroy('doomed')
        self.destroy_model.assert_called_once_with('doomed')
        self.clean_up_instances.assert_not_called()

    def test_destroy_on_openstack_provider(self):
        self.patch_object(lc_destroy.zaza.controller, 'destroy_model')
        self.patch_object(lc_destroy.model, 'get_status',
                          return_value={'machines': "the-machines"})
        self.patch_object(lc_destroy.juju_utils, 'get_provider_type',
                          return_value="openstack")
        self.patch("zaza.utilities.openstack_provider.report_machine_errors",
                   name='report_machine_errors')
        self.patch("zaza.utilities.openstack_provider.clean_up_instances",
                   name='clean_up_instances')
        lc_destroy.destroy('doomed')
        self.destroy_model.assert_called_once_with('doomed')
        self.report_machine_errors.assert_called_once_with(
            'doomed', 'the-machines')
        self.clean_up_instances.assert_called_once_with(
            'doomed', 'the-machines')

    def test_parser(self):
        args = lc_destroy.parse_args(['-m', 'doomed'])
        self.assertEqual(args.model_name, 'doomed')

    def test_parser_logging(self):
        # Using defaults
        args = lc_destroy.parse_args(['-m', 'doomed'])
        self.assertEqual(args.loglevel, 'INFO')
        # Using args
        args = lc_destroy.parse_args(['-m', 'doomed', '--log', 'DEBUG'])
        self.assertEqual(args.loglevel, 'DEBUG')
