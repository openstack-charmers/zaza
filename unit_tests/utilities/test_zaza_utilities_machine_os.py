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

import unittest.mock as mock

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

    def test__set_vfio_unsafe_noiommu_mode(self):
        self.patch_object(machine_os_utils.zaza.utilities.juju, 'remote_run')
        self.remote_run.return_value = 'Y'
        unit = mock.MagicMock()
        unit.name = 'aUnit'

        with self.assertRaises(AssertionError):
            machine_os_utils._set_vfio_unsafe_noiommu_mode(unit, False)

        self.remote_run.return_value = 'N'

        with self.assertRaises(AssertionError):
            machine_os_utils._set_vfio_unsafe_noiommu_mode(unit, True)

        self.remote_run.reset_mock()
        self.remote_run.return_value = 'Y\n'
        expect = (
            'echo 1 > /sys/module/vfio/parameters/enable_unsafe_noiommu_mode '
            '&& cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode')
        machine_os_utils._set_vfio_unsafe_noiommu_mode(unit, True)
        self.remote_run.assert_called_once_with(
            'aUnit', expect, model_name=None, fatal=True)

        self.remote_run.reset_mock()
        self.remote_run.return_value = 'N\n'
        expect = (
            'echo 0 > /sys/module/vfio/parameters/enable_unsafe_noiommu_mode '
            '&& cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode')
        machine_os_utils._set_vfio_unsafe_noiommu_mode(unit, False)
        self.remote_run.assert_called_once_with(
            'aUnit', expect, model_name=None, fatal=True)

    def test_enable_vfio_unsafe_noiommu_mode(self):
        self.patch_object(machine_os_utils, '_set_vfio_unsafe_noiommu_mode')
        unit = mock.MagicMock()
        unit.name = 'aUnit'
        machine_os_utils.enable_vfio_unsafe_noiommu_mode(unit,
                                                         model_name='aModel')
        self._set_vfio_unsafe_noiommu_mode.assert_called_once_with(
            unit, True, model_name='aModel')

    def test_disable_vfio_unsafe_noiommu_mode(self):
        self.patch_object(machine_os_utils, '_set_vfio_unsafe_noiommu_mode')
        unit = mock.MagicMock()
        unit.name = 'aUnit'
        machine_os_utils.disable_vfio_unsafe_noiommu_mode(unit,
                                                          model_name='aModel')
        self._set_vfio_unsafe_noiommu_mode.assert_called_once_with(
            unit, False, model_name='aModel')

    def test_get_hv_application(self):
        self.patch_object(machine_os_utils.zaza.charm_lifecycle.utils,
                          'get_config_options')
        self.get_config_options.return_value = {
            machine_os_utils.HV_APPLICATION_KEY: 'someApp'
        }
        self.assertEquals(machine_os_utils.get_hv_application(), 'someApp')

    def test_reboot_hvs(self):
        # No hv_application
        self.patch_object(machine_os_utils, 'get_hv_application')
        self.patch_object(machine_os_utils.zaza.model, 'get_units')
        machine_os_utils.reboot_hvs()
        self.assertFalse(self.get_units.called)

        # No arguments provided to function
        self.get_hv_application.return_value = 'someApp'
        unit = mock.MagicMock()
        unit.name = 'someApp/0'
        self.get_units.return_value = [unit]
        self.patch_object(machine_os_utils.zaza.utilities.generic, 'reboot')
        self.patch_object(machine_os_utils.zaza.model,
                          'block_until_unit_wl_status')
        self.patch_object(machine_os_utils.zaza.charm_lifecycle.utils,
                          'get_charm_config')
        self.get_charm_config.return_value = {
            'target_deploy_status': {'someDeployStatus': None}}
        self.patch_object(machine_os_utils.zaza.model,
                          'wait_for_application_states')
        machine_os_utils.reboot_hvs()
        self.get_units.assert_called_once_with('someApp')
        self.reboot.assert_called_once_with('someApp/0')
        self.wait_for_application_states.assert_called_once_with(
            states={'someDeployStatus': None})

        # Units provided as argument
        self.get_units.reset_mock()
        self.reboot.reset_mock()
        self.wait_for_application_states.reset_mock()
        machine_os_utils.reboot_hvs(units=[unit])
        self.assertFalse(self.get_units.called)
        self.reboot.assert_called_once_with('someApp/0')
        self.wait_for_application_states.assert_called_once_with(
            states={'someDeployStatus': None})

    def test_enable_hugepages(self):
        self.patch_object(machine_os_utils.zaza.utilities.juju, 'remote_run')
        self.remote_run.return_value = '41\n'
        self.patch_object(machine_os_utils, 'reboot_hvs')
        unit = mock.MagicMock()
        unit.name = 'someApp/0'
        with self.assertRaises(AssertionError):
            machine_os_utils.enable_hugepages(unit, 42, model_name='aModel')

        self.remote_run.reset_mock()
        self.reboot_hvs.reset_mock()
        self.remote_run.return_value = '42\n'
        machine_os_utils.enable_hugepages(unit, 42, model_name='aModel')
        self.reboot_hvs.assert_called_once_with([unit])
        self.remote_run.assert_has_calls([
            mock.call(
                'someApp/0',
                'echo \'GRUB_CMDLINE_LINUX_DEFAULT='
                '"default_hugepagesz=1G hugepagesz=1G hugepages=42"\''
                ' > /etc/default/grub.d/99-zaza-hugepages.cfg && update-grub',
                model_name='aModel', fatal=True),
            mock.call(
                'someApp/0',
                'cat /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages'
                '',
                model_name='aModel',
                fatal=True)
        ])

    def test_disable_hugepages(self):
        self.patch_object(machine_os_utils.zaza.utilities.juju, 'remote_run')
        self.remote_run.return_value = '41\n'
        self.patch_object(machine_os_utils, 'reboot_hvs')
        unit = mock.MagicMock()
        unit.name = 'someApp/0'
        with self.assertRaises(AssertionError):
            machine_os_utils.disable_hugepages(unit, model_name='aModel')

        self.remote_run.reset_mock()
        self.reboot_hvs.reset_mock()
        self.remote_run.return_value = '0\n'
        machine_os_utils.disable_hugepages(unit, model_name='aModel')
        self.reboot_hvs.assert_called_once_with([unit])
        self.remote_run.assert_has_calls([
            mock.call(
                'someApp/0',
                'rm /etc/default/grub.d/99-zaza-hugepages.cfg && update-grub',
                model_name='aModel', fatal=True),
            mock.call(
                'someApp/0',
                'cat /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages'
                '',
                model_name='aModel', fatal=True)
        ])
