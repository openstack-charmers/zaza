# Copyright 2021 Canonical
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

import unit_tests.utils as ut_utils
import zaza.utilities.machine_os as machine_os_utils

import zaza.model


class TestUtils(ut_utils.BaseTestCase):

    def test_install_modules_extra(self):
        self.patch_object(machine_os_utils.zaza.utilities.juju, 'remote_run')
        machine_os_utils.install_modules_extra('unit', 'model')
        self.remote_run.assert_called_once_with(
            'unit', 'apt -y install linux-modules-extra-$(uname -r)',
            model_name='model')

    def test_load_kernel_module(self):
        self.patch_object(machine_os_utils.zaza.utilities.juju, 'remote_run')
        machine_os_utils.load_kernel_module(
            'unit', 'module', module_arguments='modarg', model_name='model')
        self.remote_run.assert_called_once_with(
            'unit', 'modprobe module modarg', model_name='model')

    def test_is_container(self):
        self.patch_object(machine_os_utils.zaza.utilities.juju, 'remote_run')

        def _raise_exception(*_, **__):
            raise zaza.model.CommandRunFailed(
                '', {'Code': '0', 'Stdout': '', 'Stderr': ''})
        self.remote_run.side_effect = _raise_exception
        self.assertFalse(
            machine_os_utils.is_container('unit', model_name='model'))
        self.remote_run.assert_called_once_with(
            'unit', 'systemd-detect-virt --container', model_name='model')
        self.remote_run.side_effect = None
        self.assertTrue(
            machine_os_utils.is_container('unit', model_name='model'))

    def test_is_vm(self):
        self.patch_object(machine_os_utils.zaza.utilities.juju, 'remote_run')

        def _raise_exception(*_, **__):
            raise zaza.model.CommandRunFailed(
                '', {'Code': '0', 'Stdout': '', 'Stderr': ''})
        self.remote_run.side_effect = _raise_exception
        self.assertFalse(
            machine_os_utils.is_vm('unit', model_name='model'))
        self.remote_run.assert_called_once_with(
            'unit', 'systemd-detect-virt --vm', model_name='model')
        self.remote_run.side_effect = None
        self.assertTrue(
            machine_os_utils.is_container('unit', model_name='model'))

    def test_add_netdevsim(self):
        self.patch_object(machine_os_utils, 'install_modules_extra')
        self.patch_object(machine_os_utils, 'load_kernel_module')
        self.patch_object(machine_os_utils.zaza.utilities.juju, 'remote_run')
        result = machine_os_utils.add_netdevsim(
            'unit', 10, 2, model_name='model')
        self.assertEquals(result, ['eni10np1', 'eni10np2'])
        self.install_modules_extra.assert_called_once_with(
            'unit', model_name='model')
        self.load_kernel_module.assert_called_once_with(
            'unit', 'netdevsim', model_name='model')
        cmd = (
            'test -d /sys/devices/netdevsim10 || '
            'echo "10 2" > /sys/bus/netdevsim/new_device')
        self.remote_run.assert_called_once_with(
            'unit', cmd, model_name='model')
