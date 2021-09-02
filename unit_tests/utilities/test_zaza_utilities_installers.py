# Copyright 2021 Canonical Ltd.
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

"""Unit tests for zaza.utilities.installers."""

import mock
import subprocess

import unit_tests.utils as tests_utils


import zaza.utilities.installers as installers


class TestInstallFunctions(tests_utils.BaseTestCase):

    def test_install_module_on_juju_unit(self):
        self.patch_object(installers, 'install_module_in_venv')
        self.patch_object(installers, 'make_juju_scp_fn', return_value="scp")
        self.patch_object(installers, 'make_juju_ssh_fn', return_value="ssh")

        installers.install_module_on_juju_unit(
            "a-unit", "a-source", "a-destination", model="a-model",
            install_virtualenv=False, run_user="a-user")

        self.make_juju_scp_fn.assert_called_once_with(
            'a-unit', model='a-model')
        self.make_juju_ssh_fn.assert_called_once_with(
            'a-unit', model='a-model')
        self.install_module_in_venv.assert_called_with(
            'a-source', 'a-destination', 'scp', 'ssh',
            install_virtualenv=False, run_user='a-user')

    def test_install_module_instance(self):
        self.patch_object(installers, 'install_module_in_venv')
        self.patch_object(installers, 'make_scp_fn', return_value="scp")
        self.patch_object(installers, 'make_ssh_fn', return_value="ssh")

        installers.install_module_instance(
            "a-target", "a-source", "a-destination", key_file="key_file",
            user="a-user", install_virtualenv=False, run_user="a-user")

        self.make_scp_fn.assert_called_once_with(
            'a-target', key_file='key_file', user='a-user')
        self.make_ssh_fn.assert_called_once_with(
            'a-target', key_file='key_file', user='a-user')
        self.install_module_in_venv.assert_called_with(
            'a-source', 'a-destination', 'scp', 'ssh',
            install_virtualenv=False, run_user='a-user')

    def test_user_directory(self):
        mock_ssh_fn = mock.Mock(return_value='   some-result   ')

        self.assertEqual(installers.user_directory(mock_ssh_fn), 'some-result')
        mock_ssh_fn.assert_called_once_with(["echo", "$HOME"])

        mock_ssh_fn.reset_mock()
        self.assertEqual(installers.user_directory(mock_ssh_fn, name='user'),
                         'some-result')
        mock_ssh_fn.assert_called_once_with(["echo", "~user"])

    def test_install_module_in_venv__file_source(self):
        self.patch_object(installers, "user_directory",
                          return_value="/home/ubuntu")
        self.patch("uuid.uuid4", name="uuid4", return_value="0123456789" * 4)
        mock_ssh_fn = mock.Mock()
        mock_scp_fn = mock.Mock()

        installers.install_module_in_venv(
            "file:thing", "destination", mock_scp_fn, mock_ssh_fn)
        dest_source = "/home/ubuntu/tmp-890123456789"

        expected_ssh_calls = [
            mock.call(["test", "-d", "destination"]),
            mock.call(["test", "-d", "destination/.venv"]),
            mock.call(["destination/.venv/bin/pip", "install", dest_source])]
        expected_scp_calls = [
            mock.call("thing", dest_source)]

        mock_ssh_fn.assert_has_calls(expected_ssh_calls)
        mock_scp_fn.assert_has_calls(expected_scp_calls)

    def test_install_module_in_venv__module(self):
        mock_ssh_fn = mock.Mock()
        mock_scp_fn = mock.Mock()

        installers.install_module_in_venv(
            "thing", "destination", mock_scp_fn, mock_ssh_fn)

        expected_ssh_calls = [
            mock.call(["test", "-d", "destination"]),
            mock.call(["test", "-d", "destination/.venv"]),
            mock.call(["destination/.venv/bin/pip", "install", "thing"])]

        mock_ssh_fn.assert_has_calls(expected_ssh_calls)
        mock_scp_fn.assert_not_called()

    def test_install_module_in_venv__install_venv(self):
        mock_scp_fn = mock.Mock()

        ssh_calls = []

        def mock_ssh_fn(cmd):
            ssh_calls.append(cmd)
            if cmd == ["test", "-d", "destination/.venv"]:
                raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

        installers.install_module_in_venv(
            "thing", "destination", mock_scp_fn, mock_ssh_fn)

        expected_ssh_calls = [
            ["test", "-d", "destination"],
            ["test", "-d", "destination/.venv"],
            "which virtualenv",
            ["virtualenv", "-p", "`which python3`", "destination/.venv"],
            ["destination/.venv/bin/pip", "install", "thing"]]

        self.assertEqual(ssh_calls, expected_ssh_calls)
        mock_scp_fn.assert_not_called()

    def test_install_module_in_venv__mising_virtualenv(self):
        mock_scp_fn = mock.Mock()

        ssh_calls = []

        def mock_ssh_fn(cmd):
            ssh_calls.append(cmd)
            if cmd in (["test", "-d", "destination/.venv"],
                       "which virtualenv"):
                raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

        installers.install_module_in_venv(
            "thing", "destination", mock_scp_fn, mock_ssh_fn)

        expected_ssh_calls = [
            ["test", "-d", "destination"],
            ["test", "-d", "destination/.venv"],
            "which virtualenv",
            "sudo apt install -y virtualenv",
            ["virtualenv", "-p", "`which python3`", "destination/.venv"],
            ["destination/.venv/bin/pip", "install", "thing"]]

        self.assertEqual(ssh_calls, expected_ssh_calls)
        mock_scp_fn.assert_not_called()

    def test_install_module_in_venv__no_install_virtualenv(self):
        mock_scp_fn = mock.Mock()

        ssh_calls = []

        def mock_ssh_fn(cmd):
            ssh_calls.append(cmd)
            if cmd in (["test", "-d", "destination/.venv"],
                       "which virtualenv"):
                raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

        with self.assertRaises(RuntimeError):
            installers.install_module_in_venv(
                "thing", "destination", mock_scp_fn, mock_ssh_fn,
                install_virtualenv=False)

        expected_ssh_calls = [
            ["test", "-d", "destination"],
            ["test", "-d", "destination/.venv"],
            "which virtualenv"]

        self.assertEqual(ssh_calls, expected_ssh_calls)
        mock_scp_fn.assert_not_called()

    def test_make_juju_ssh_fn(self):
        self.patch_object(installers, '_run_via_juju_ssh')

        fn = installers.make_juju_ssh_fn("a-unit", sudo=True, model="a-model")
        fn("a-command")
        self._run_via_juju_ssh.assert_called_once_with(
            "a-unit", "a-command", sudo=True, model="a-model")

    def test__run_via_juju_ssh(self):
        self.patch('subprocess.check_output', name='mock_check_output',
                   return_value=b"check_output_return_value")
        self.patch_object(installers, 'logging', name="mock_logging")

        self.assertEqual(
            installers._run_via_juju_ssh(
                "a-unit", "some command", sudo=True, model="a-model"),
            "check_output_return_value")
        self.mock_check_output.assert_called_once_with(
            ["juju", "ssh", "--model=a-model", "a-unit",
             "-o", "LogLevel=QUIET", "--", "sudo", "some", "command"])

    def test_make_juju_scp_fn__copy_to(self):
        self.patch('zaza.model.scp_to_unit', name='mock_scp_to_unit',
                   return_value='return_from_mock_scp_to_unit')
        self.patch_object(installers, 'logging', name="mock_logging")

        fn = installers.make_juju_scp_fn(
            'a-unit', model='a-model', proxy=True)

        self.assertEqual(
            fn('source', 'destination'), 'return_from_mock_scp_to_unit')

        self.mock_scp_to_unit.assert_called_once_with(
            'a-unit', 'source', 'destination',
            model_name='a-model', user='ubuntu',
            proxy=True, scp_opts='-r')

    def test_make_juju_scp_fn__copy_from(self):
        self.patch('zaza.model.scp_from_unit', name='mock_scp_from_unit',
                   return_value='return_from_mock_scp_from_unit')
        self.patch_object(installers, 'logging', name="mock_logging")

        fn = installers.make_juju_scp_fn(
            'a-unit', user='a-user', model='a-model')

        self.assertEqual(
            fn('source', 'destination', recursive=False, copy_from=True),
            'return_from_mock_scp_from_unit')

        self.mock_scp_from_unit.assert_called_once_with(
            'a-unit', 'source', 'destination',
            model_name='a-model', user='a-user',
            proxy=False, scp_opts='')

    def test_make_ssh_fn(self):
        self.patch('subprocess.check_output', name='mock_check_output',
                   return_value=b'check_output_return_value')
        self.patch_object(installers, 'logging', name="mock_logging")

        fn = installers.make_ssh_fn(
            'a-target', key_file='a-key-file', user='a-user')
        self.assertEqual(fn('some command'), 'check_output_return_value')
        self.mock_check_output.assert_called_once_with(
            ['ssh', '-i', 'a-key-file',
             '-o', 'StrictHostKeyChecking=no', '-q',
             'a-user@a-target', '--',
             'some', 'command'])

        # and without the user
        self.mock_check_output.reset_mock()
        fn = installers.make_ssh_fn(
            'a-target', key_file='a-key-file')
        self.assertEqual(fn('some command'), 'check_output_return_value')
        self.mock_check_output.assert_called_once_with(
            ['ssh', '-i', 'a-key-file',
             '-o', 'StrictHostKeyChecking=no', '-q',
             'a-target', '--',
             'some', 'command'])

    def test_make_scp_fn__copy_to(self):
        self.patch('subprocess.check_call', name='mock_check_call')
        self.patch_object(installers, 'logging', name="mock_logging")

        fn = installers.make_scp_fn(
            'a-target', key_file='a-key-file', user='a-user')
        fn('source', 'destination')

        self.mock_check_call.assert_called_once_with(
            ['scp', '-i', 'a-key-file',
             '-o', 'StrictHostKeyChecking=no', '-q', '-B',
             '-r',
             'source', 'a-user@a-target:destination'])

    def test_make_scp_fn__copy_from(self):
        self.patch('subprocess.check_call', name='mock_check_call')
        self.patch_object(installers, 'logging', name="mock_logging")

        fn = installers.make_scp_fn('a-target', key_file='a-key-file')
        fn('source', 'destination', recursive=False, copy_from=True)

        self.mock_check_call.assert_called_once_with(
            ['scp', '-i', 'a-key-file',
             '-o', 'StrictHostKeyChecking=no', '-q', '-B',
             'a-target:destination', 'source'])


class TestUserFunctions(tests_utils.BaseTestCase):

    def test_create_user(self):
        ssh_fn = mock.Mock()
        dir_ = installers.create_user(ssh_fn, 'a-name')
        ssh_fn.assert_called_once_with(
            ['sudo', 'useradd', '-r', '-s', '/bin/false', '-d',
             '/var/lib/a-name', '-m', 'a-name'])
        self.assertEqual(dir_, '/var/lib/a-name')

    def test_user_exists(self):
        ssh_fn = mock.Mock()

        def raise_():
            raise Exception('an exception')

        self.assertEqual(installers.user_exists(ssh_fn, 'a-name'), True)
        ssh_fn.assert_called_once_with(
            ['grep', '-c', '^a-name:', '/etc/passwd'])

        ssh_fn.side_effect = raise_

        self.assertEqual(installers.user_exists(ssh_fn, 'a-name'), False)

    def test_user_directory(self):
        ssh_fn = mock.Mock(return_value='   some-value   ')

        self.assertEqual(installers.user_directory(ssh_fn), 'some-value')
        ssh_fn.assert_called_once_with(['echo', '$HOME'])

        ssh_fn.reset_mock()
        self.assertEqual(installers.user_directory(ssh_fn, 'aname'),
                         'some-value')
        ssh_fn.assert_called_once_with(['echo', '~aname'])


class TestSystemdControl(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(installers, "logging")
        self.mock_ssh_fn = mock.Mock(return_value="   /home/ubuntu\n")
        self.mock_scp_fn = mock.Mock()
        self.sc = installers.SystemdControl(
            self.mock_ssh_fn, self.mock_scp_fn, 'aname', 'aexec')
        # force sc._home_var so we can avoid the ssh_fn call
        self.sc._home_var = '/some/home'

    def test__home(self):
        # unforce sc._home_var so we get the ssh_fn call
        self.sc._home_var = None
        self.assertEqual(self.sc._home, "/home/ubuntu")
        self.assertEqual(self.sc._home_var, "/home/ubuntu")
        self.mock_ssh_fn.assert_called_once_with("echo $HOME")

    def test_install(self):
        mock_ttr = mock.Mock()
        self.patch('tempfile.TemporaryDirectory', name="mock_tt",
                   return_value=mock_ttr)
        mock_ttr.__enter__ = mock.Mock(return_value='/some/tempdir/')
        mock_ttr.__exit__ = mock.Mock(return_value=False)

        with tests_utils.patch_open() as (mock_open, mock_file):
            self.sc.install()

            mock_open.assert_called_once_with('/some/tempdir/control', 'wt')
            file = installers.SystemdControl.SYSTEMD_FILE.format(
                name='aname', exec_start='aexec')
            mock_file.write.assert_called_once_with(file)
            self.mock_scp_fn.assert_called_once_with(
                '/some/tempdir/control', '/some/home/aname.service')
            self.mock_ssh_fn.assert_has_calls((
                mock.call(['sudo', 'mv', '/some/home/aname.service',
                           '/etc/systemd/system/aname.service']),
                mock.call(['sudo', 'systemctl', 'daemon-reload'])))
            self.assertTrue(self.sc._installed)

    def test__systemctl(self):
        self.sc._systemctl("some-command")
        self.mock_ssh_fn.assert_called_once_with(
            ['sudo', 'systemctl', 'some-command', 'aname'])

    def test_enable(self):
        self.patch_object(self.sc, '_systemctl', name='mock__systemctl')
        self.patch_object(self.sc, 'install', name='mock_install')
        # test enable() calls install.
        self.sc.enable()
        self.assertTrue(self.sc._enabled)
        self.mock__systemctl.assert_called_once_with('enable')
        self.mock_install.assert_called_once_with()
        # now test install is not called.
        self.sc._installed = True
        self.mock_install.reset_mock()
        self.mock__systemctl.reset_mock()
        self.sc.enable()
        self.mock__systemctl.assert_called_once_with('enable')
        self.mock_install.assert_not_called()

    def test_disable(self):
        self.patch_object(self.sc, '_systemctl', name='mock__systemctl')
        self.sc._enabled = True
        self.sc.disable()
        self.assertFalse(self.sc._enabled)
        self.mock__systemctl.assert_called_once_with('disable')

    def test_is_running(self):
        self.sc._installed = False
        self.sc._stopped = True
        self.assertFalse(self.sc.is_running())
        self.mock_ssh_fn.assert_not_called()
        self.sc._installed = True
        self.assertFalse(self.sc.is_running())
        self.mock_ssh_fn.assert_not_called()
        # now verify actual is_running call to systemctl
        self.sc._stopped = False
        self.mock_ssh_fn.return_value = "yep, I'm running okay."
        self.assertTrue(self.sc.is_running())
        self.assertFalse(self.sc._stopped)
        self.mock_ssh_fn.assert_called_once_with(
            ['sudo', 'systemctl', 'show', '-p', 'SubState',
             '--value', '--no-pager', 'aname'])
        # now verify that the called proc error results in stopped.
        self.mock_ssh_fn.reset_mock()

        def _raise(cmd):
            raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

        self.mock_ssh_fn.side_effect = _raise
        self.assertFalse(self.sc.is_running())
        self.assertTrue(self.sc._stopped)
        self.mock_ssh_fn.assert_called_once_with(
            ['sudo', 'systemctl', 'show', '-p', 'SubState',
             '--value', '--no-pager', 'aname'])

    def test_start(self):
        self.patch_object(self.sc, '_systemctl', name='mock__systemctl')
        self.patch_object(self.sc, 'install', name='mock_install')
        self.patch_object(self.sc, 'enable', name='mock_enable')
        self.patch_object(self.sc, 'is_running', name='mock_is_running',
                          return_value=False)

        self.sc.start()
        self.mock_install.assert_called_once_with()
        self.mock_enable.assert_called_once_with()
        self.mock__systemctl.assert_called_once_with('start')
        self.assertFalse(self.sc._stopped)

    def test_stop(self):
        self.patch_object(self.sc, '_systemctl', name='mock__systemctl')
        self.patch_object(self.sc, 'is_running', name='mock_is_running',
                          return_value=False)
        # start off not installed and stopped
        self.sc._installed = False
        self.sc._stopped = True
        self.sc.stop()
        self.mock_is_running.assert_not_called()
        self.mock__systemctl.assert_not_called()
        # now be installed but already stopped.
        self.sc._installed = True
        self.sc.stop()
        self.mock_is_running.assert_not_called()
        self.mock__systemctl.assert_not_called()
        # now think we are running, but check
        self.sc._stopped = False
        self.sc.stop()
        self.mock_is_running.assert_called_once_with()
        self.mock__systemctl.assert_not_called()
        # now think we are running, and check, and check says we are
        self.mock_is_running.reset_mock()
        self.mock_is_running.return_value = True
        self.sc.stop()
        self.mock_is_running.assert_called_once_with()
        self.mock__systemctl.assert_called_once_with('stop')
        self.assertTrue(self.sc._stopped)

    def test_restart(self):
        self.patch_object(self.sc, '_systemctl', name='mock__systemctl')
        self.patch_object(self.sc, 'is_running', name='mock_is_running',
                          return_value=False)
        self.sc._installed = False
        self.sc.restart()
        self.mock_is_running.assert_not_called()
        self.mock__systemctl.assert_not_called()
        # now set to installed and do a start.
        self.sc._installed = True
        self.sc._stopped = True
        self.sc.restart()
        self.mock_is_running.assert_called_once_with()
        self.mock__systemctl.assert_called_once_with('start')
        self.assertFalse(self.sc._stopped)
        # and now set to running so restart is called.
        self.mock_is_running.reset_mock()
        self.mock__systemctl.reset_mock()
        self.mock_is_running.return_value = True
        self.sc.restart()
        self.mock_is_running.assert_called_once_with()
        self.mock__systemctl.assert_called_once_with('restart')

    def test_remove(self):
        self.patch_object(self.sc, 'stop', name='mock_stop')
        self.patch_object(self.sc, 'disable', name='mock_disable')
        # start off without being installed
        self.sc._installed = False
        self.sc.remove()
        self.mock_stop.assert_not_called()
        self.mock_disable.assert_not_called()
        self.mock_ssh_fn.assert_not_called()
        # now be installed to ensure that it gets stopped.
        self.sc._installed = True
        self.sc.remove()
        self.mock_stop.assert_called_once_with()
        self.mock_disable.assert_called_once_with()
        self.mock_ssh_fn.assert_called_once_with(
            ['sudo', 'rm', '/etc/systemd/system/aname.service'])
