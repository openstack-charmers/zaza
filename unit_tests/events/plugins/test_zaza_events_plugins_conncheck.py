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

"""Unit tests for zaza.events.plugins.conncheck.py."""

import mock
import subprocess

import unit_tests.utils as tests_utils


import zaza.events.plugins.conncheck as conncheck


class TestAutoConfigureFunction(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(conncheck, 'logger', name='mock_logger')
        self.patch_object(
            conncheck, 'get_plugin_manager', name='mock_get_plugin_manager')
        self.mock_collection = mock.Mock()
        self.mock_conncheck_manager = mock.Mock()

    def test_autoconfigure_no_config(self):
        self.mock_get_plugin_manager.return_value = self.mock_conncheck_manager
        conncheck.auto_configure_with_collection(self.mock_collection)
        self.mock_get_plugin_manager.assert_called_once_with('DEFAULT')
        self.mock_collection.add_logging_manager.assert_called_once_with(
            self.mock_conncheck_manager)

    def test_autoconfigure_with_config(self):
        self.mock_get_plugin_manager.return_value = self.mock_conncheck_manager
        config = {
            'manager-name': 'a-manager',
            'source': 'a-source',
        }
        conncheck.auto_configure_with_collection(self.mock_collection,
                                                 config=config)
        self.mock_get_plugin_manager.assert_called_once_with('a-manager')
        self.mock_collection.add_logging_manager.assert_called_once_with(
            self.mock_conncheck_manager)
        self.mock_conncheck_manager.configure.assert_called_once_with(
            module_source='a-source')


class TestGetConncheckManager(tests_utils.BaseTestCase):

    def test_get_conncheck_manager(self):
        self.patch_object(conncheck, 'get_option', name='mock_get_option')
        self.mock_get_option.return_value = 'a-name'
        self.patch_object(conncheck, 'get_plugin_manager',
                          name='mock_get_plugin_manager')
        self.mock_get_plugin_manager.return_value = 'a-manager'
        self.assertEqual(conncheck.get_conncheck_manager(), 'a-manager')
        self.mock_get_option.assert_called_once_with(
            'zaza-events.modules.conncheck.manager-name', 'DEFAULT')
        self.mock_get_plugin_manager.assert_called_once_with('a-name')


class TestGetPluginManager(tests_utils.BaseTestCase):

    def test_get_plugin_manager(self):
        self.patch_object(conncheck, '_conncheck_plugin_managers', new={})
        self.patch_object(conncheck, 'ConnCheckPluginManager',
                          name='mock_ConnCheckPluginManager')
        self.mock_ConnCheckPluginManager.return_value = 'a-manager'
        self.assertEqual(conncheck.get_plugin_manager(), 'a-manager')
        self.mock_ConnCheckPluginManager.assert_called_once_with(
            managed_name='DEFAULT')

    def test_get_plugin_manager_non_default(self):
        self.patch_object(conncheck, '_conncheck_plugin_managers', new={})
        self.patch_object(conncheck, 'ConnCheckPluginManager',
                          name='mock_ConnCheckPluginManager')
        self.mock_ConnCheckPluginManager.return_value = 'a-manager'
        self.assertEqual(conncheck.get_plugin_manager('a-name'), 'a-manager')
        self.mock_ConnCheckPluginManager.assert_called_once_with(
            managed_name='a-name')

    def test_get_plugin_manager_check_caches(self):
        self.patch_object(conncheck, '_conncheck_plugin_managers', new={},
                          name='mock__conncheck_plugin_managers')
        self.mock__conncheck_plugin_managers['a-name'] = 'a-manager'
        self.patch_object(conncheck, 'ConnCheckPluginManager',
                          name='mock_ConnCheckPluginManager')
        self.mock_ConnCheckPluginManager.return_value = 'the-manager'
        self.assertEqual(conncheck.get_plugin_manager('a-name'), 'a-manager')
        self.mock_ConnCheckPluginManager.assert_not_called()


class TestConnCheckPluginManager(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(conncheck, 'ConnCheckManager',
                          name='mock_ConnCheckManager')
        self.mock_conncheck_manager = mock.Mock()
        self.mock_ConnCheckManager.return_value = self.mock_conncheck_manager
        self.mock_collection_object = mock.Mock()
        self.mock_collection_object.logs_dir = "a-logs-dir"
        self.mock_collection_object.log_format = conncheck.LogFormats.InfluxDB
        self.mock_collection_object.collection = 'a-collection'

    def test_init(self):
        cpm = conncheck.ConnCheckPluginManager()
        self.assertEqual(cpm.managed_name, 'DEFAULT')
        self.assertEqual(cpm._conncheck_manager, self.mock_conncheck_manager)

        cpm = conncheck.ConnCheckPluginManager(managed_name='a-manager')
        self.assertEqual(cpm.managed_name, 'a-manager')

    def test_configure(self):
        cpm = conncheck.ConnCheckPluginManager()
        self.patch_object(
            cpm, 'configure_plugin', name='mock_cpm_configure_plugin')
        cpm.configure(collection_object=self.mock_collection_object)
        self.mock_cpm_configure_plugin.assert_called_once_with()

    def test_configure_plugin(self):
        cpm = conncheck.ConnCheckPluginManager(
            module_source='a-source', tags='abc')
        cpm.configure(collection_object=self.mock_collection_object)
        self.mock_conncheck_manager.configure.assert_called_once_with(
            collection='a-collection',
            logs_dir='a-logs-dir',
            module_source='a-source',
            tags='abc')

    def test_manager_property(self):
        cpm = conncheck.ConnCheckPluginManager(
            module_source='a-source', tags='abc')
        self.assertEqual(cpm.manager, self.mock_conncheck_manager)
        cpm._conncheck_manager = None
        with self.assertRaises(AssertionError):
            cpm.manager

    def test_add_instance(self):
        cpm = conncheck.ConnCheckPluginManager(
            module_source='a-source', tags='abc')
        cpm.add_instance('a-spec', this='that')
        self.mock_conncheck_manager.add_instance.assert_called_once_with(
            'a-spec', this='that')

    def test_get_instance(self):
        cpm = conncheck.ConnCheckPluginManager(
            module_source='a-source', tags='abc')
        self.mock_conncheck_manager.get_instance.return_value = 'an-instance'
        self.assertEqual(cpm.get_instance('a-spec'), 'an-instance')
        self.mock_conncheck_manager.get_instance.assert_called_once_with(
            'a-spec')

    def test_start(self):
        cpm = conncheck.ConnCheckPluginManager(
            module_source='a-source', tags='abc')
        cpm.start('a-spec')
        self.mock_conncheck_manager.start.assert_called_once_with('a-spec')

    def test_stop(self):
        cpm = conncheck.ConnCheckPluginManager(
            module_source='a-source', tags='abc')
        cpm.stop('a-spec')
        self.mock_conncheck_manager.stop.assert_called_once_with('a-spec')

    def test_finalise(self):
        cpm = conncheck.ConnCheckPluginManager(
            module_source='a-source', tags='abc')
        cpm.finalise()
        self.mock_conncheck_manager.finalise.assert_called_once_with()

    def test_log_files(self):
        cpm = conncheck.ConnCheckPluginManager(
            module_source='a-source', tags='abc')
        cpm.log_files()
        self.mock_conncheck_manager.log_files.assert_called_once_with()

    def test_clean_up(self):
        cpm = conncheck.ConnCheckPluginManager(
            module_source='a-source', tags='abc')
        cpm.clean_up()
        self.mock_conncheck_manager.clean_up.assert_called_once_with()

    def test_reset(self):
        cpm = conncheck.ConnCheckPluginManager(
            module_source='a-source', tags='abc')
        cpm.reset()
        self.mock_conncheck_manager.clean_up.assert_called_once_with()
        self.assertIsNone(cpm._conncheck_manager)


class TestConnCheckManager(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.c = conncheck.ConnCheckManager(
            collection='a-collection',
            logs_dir='/some/dir',
            tags=['tag1'])

    def test_init(self):
        self.assertEqual(self.c.collection, 'a-collection')
        self.assertEqual(self.c.logs_dir, '/some/dir')
        self.assertEqual(self.c.tags, ['tag1'])

    def test_add_instance(self):
        self.patch_object(self.c, 'make_instance_with',
                          name='mock_make_instance_with')
        self.mock_make_instance_with.return_value = 'an-instance'
        self.c.add_instance('juju:0', this='that', some='thing')
        self.mock_make_instance_with.assert_called_once_with(
            'juju:0', this='that', some='thing', module_source='conncheck',
            collection='a-collection')
        self.assertIn('juju:0', self.c._instances)
        self.assertEqual(self.c._instances['juju:0'], 'an-instance')

        # add again to check for error
        with self.assertRaises(RuntimeError):
            self.c.add_instance('juju:0', this='that', some='thing')

    def test_get_instance(self):
        self.c._instances['juju:0'] = 'an-instance'
        self.assertEqual(self.c.get_instance('juju:0'), 'an-instance')

    def test_start(self):
        mock_instance1 = mock.Mock()
        mock_instance2 = mock.Mock()
        self.c._instances = {'i1': mock_instance1,
                             'i2': mock_instance2}
        self.c.start('i1')
        mock_instance1.start.assert_called_once_with()
        mock_instance2.start.assert_not_called()

        mock_instance1.reset_mock()
        self.c.start()
        mock_instance1.start.assert_called_once_with()
        mock_instance2.start.assert_called_once_with()

    def test_stop(self):
        mock_instance1 = mock.Mock()
        mock_instance2 = mock.Mock()
        self.c._instances = {'i1': mock_instance1,
                             'i2': mock_instance2}
        self.c.stop('i1')
        mock_instance1.stop.assert_called_once_with()
        mock_instance2.stop.assert_not_called()

        mock_instance1.reset_mock()
        self.c.stop()
        mock_instance1.stop.assert_called_once_with()
        mock_instance2.stop.assert_called_once_with()

    def test_finalise(self):
        mock_instance1 = mock.Mock()
        mock_instance2 = mock.Mock()
        self.c._instances = {'i1': mock_instance1,
                             'i2': mock_instance2}
        self.c.finalise()
        mock_instance1.finalise.assert_called_once_with()
        mock_instance2.finalise.assert_called_once_with()
        mock_instance1.stop.assert_called_once_with()
        mock_instance2.stop.assert_called_once_with()

        mock_instance1.reset_mock()
        mock_instance2.reset_mock()
        self.c.finalise()
        mock_instance1.stop.assert_not_called()
        mock_instance2.stop.assert_not_called()
        mock_instance1.finalise.assert_not_called()
        mock_instance2.finalise.assert_not_called()

    def test_log_files(self):
        mock_instance1 = mock.Mock()
        mock_instance2 = mock.Mock()
        self.c._instances = {'i1': mock_instance1,
                             'i2': mock_instance2}
        mock_instance1.get_logfile_to_local.return_value = 'i1.log'
        mock_instance1.log_format = 'f'
        mock_instance2.get_logfile_to_local.return_value = 'i2.log'
        mock_instance2.log_format = 'f'

        log_specs = list(self.c.log_files())
        mock_instance1.finalise.assert_called_once_with()
        mock_instance2.finalise.assert_called_once_with()
        mock_instance1.get_logfile_to_local.assert_called_once_with(
            '/some/dir')
        mock_instance2.get_logfile_to_local.assert_called_once_with(
            '/some/dir')
        self.assertEqual(
            log_specs,
            [('i1', 'f', 'i1.log'),
             ('i2', 'f', 'i2.log')])

        mock_instance1.get_logfile_to_local.reset_mock()
        mock_instance2.get_logfile_to_local.reset_mock()
        log_specs = list(self.c.log_files())
        mock_instance1.get_logfile_to_local.assert_not_called()
        mock_instance2.get_logfile_to_local.assert_not_called()
        self.assertEqual(
            log_specs,
            [('i1', 'f', 'i1.log'),
             ('i2', 'f', 'i2.log')])

    def test_clean_up(self):
        self.patch_object(self.c, 'finalise', name='mock_finalise')
        self.c.clean_up()
        self.mock_finalise.assert_called_once_with()

    def test_register_spec_handler(self):
        self.patch_object(conncheck.ConnCheckManager,
                          '_spec_handlers',
                          name='mock_cls__spec_handlers',
                          new={})

        def handler():
            pass

        conncheck.ConnCheckManager.register_spec_handler('juju', handler)

        self.assertIn('juju', conncheck.ConnCheckManager._spec_handlers)
        self.assertEqual(conncheck.ConnCheckManager._spec_handlers['juju'],
                         handler)
        # verify can't be added twice.
        with self.assertRaises(RuntimeError):
            conncheck.ConnCheckManager.register_spec_handler('juju', handler)

    def test_make_instance_with(self):
        mock_handler = mock.Mock()
        mock_handler.return_value = 'an-instance'
        self.patch_object(conncheck.ConnCheckManager,
                          '_spec_handlers',
                          name='mock_cls__spec_handlers',
                          new={})
        conncheck.ConnCheckManager.register_spec_handler('juju', mock_handler)
        # first check for ':' in spec
        with self.assertRaises(ValueError):
            self.c.make_instance_with('i')
        # Now check for unhandled spec
        with self.assertRaises(KeyError):
            self.c.make_instance_with('some:thing')
        # finally make one with juju
        self.assertEqual(
            self.c.make_instance_with('juju:0', this='that', some='thing'),
            'an-instance')
        mock_handler.assert_called_once_with('0', this='that', some='thing')


class TestConnCheckInstanceBase(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.c = conncheck.ConnCheckInstanceBase(
            name='base',
            module_source='/some/source',
            collection='a-collection')

    def test_init(self):
        c = conncheck.ConnCheckInstanceBase(
            name='a-name',
            log_format=conncheck.LogFormats.CSV,
            config_file='thing.yaml',
            install_dir='/opt',
            module_source='/some/other/source',
            install_user='a-user')
        self.assertEqual(c.name, 'a-name')
        self.assertEqual(c.log_format, conncheck.LogFormats.CSV)
        self.assertEqual(c.config_file, 'thing.yaml')
        self.assertEqual(c.install_dir, '/opt')
        self.assertEqual(c.module_source, '/some/other/source')
        self.assertEqual(c.install_user, 'a-user')

        self.assertEqual(self.c.name, 'base')
        self.assertEqual(self.c.log_format, conncheck.LogFormats.InfluxDB)
        self.assertEqual(self.c.config_file, 'config.yaml')
        self.assertEqual(self.c.install_dir, '.')
        self.assertEqual(self.c.module_source, '/some/source')
        self.assertEqual(self.c.install_user, 'conncheck')

    def test__validate_not_existing_listener(self):
        with self.assertRaises(AssertionError):
            self.c._validate_not_existing_listener('thing', 1024)
        self.c._validate_not_existing_listener('udp', 1024)
        self.c._listeners = {('udp', 1024): None}
        with self.assertRaises(RuntimeError):
            self.c._validate_not_existing_listener('udp', 1024)
        self.c._validate_not_existing_listener('udp', 1023)

    def test_add_listener(self):
        with self.assertRaises(NotImplementedError):
            self.c.add_listener()

    def test_add_listener_spec(self):
        self.patch_object(self.c, 'write_configuration',
                          name='mock_c_write_configuration')
        self.c.add_listener_spec('udp', 1024, '0.0.0.0', reply_size=50)
        self.assertIn(('udp', 1024), self.c._listeners)
        self.assertEqual(self.c._listeners[('udp', 1024)],
                         {'name': 'base:listen:udp:0.0.0.0:1024',
                          'ipv4': '0.0.0.0',
                          'port': 1024,
                          'protocol': 'udp',
                          'reply-size': 50})
        self.mock_c_write_configuration.assert_called_once_with()

    def test_add_speaker(self):
        self.patch_object(self.c, '_get_remote_address',
                          name='mock__get_remote_address')
        self.mock__get_remote_address.return_value = '1.2.3.4'
        self.patch_object(self.c, 'add_speaker_spec',
                          name='mock_add_speaker_spec')
        self.c.add_speaker('udp', 1024, instance='an-instance', address=None,
                           wait=10, interval=20, send_size=5)
        self.mock__get_remote_address.assert_called_once_with(
            'an-instance', 'udp', 1024)
        self.mock_add_speaker_spec.assert_called_once_with(
            'udp', 1024, '1.2.3.4', wait=10, interval=20, send_size=5)

    def test__validate_not_existing_speaker(self):
        with self.assertRaises(AssertionError):
            self.c._validate_not_existing_speaker('thing', '1.2.3.4', 1024)
        self.c._validate_not_existing_speaker('udp', '1.2.3.4', 1024)
        self.c._speakers = {('udp', '1.2.3.4', 1024): None}
        with self.assertRaises(RuntimeError):
            self.c._validate_not_existing_speaker('udp', '1.2.3.4', 1024)
        self.c._validate_not_existing_speaker('udp', '1.2.3.4', 1023)

    def test_add_speaker_spec(self):
        self.patch_object(self.c, 'write_configuration',
                          name='mock_c_write_configuration')
        self.c.add_speaker_spec('udp', 1024, '1.2.3.4', send_size=50)
        self.assertIn(('udp', '1.2.3.4', 1024), self.c._speakers)
        self.assertEqual(self.c._speakers[('udp', '1.2.3.4', 1024)],
                         {'name': 'base:send:udp:1.2.3.4:1024',
                          'ipv4': '1.2.3.4',
                          'port': 1024,
                          'protocol': 'udp',
                          'send-size': 50,
                          'wait': 5,
                          'interval': 10})
        self.mock_c_write_configuration.assert_called_once_with()
        self.mock_c_write_configuration.reset_mock()

        self.c.add_speaker_spec('http', 1024, '1.2.3.4', send_size=50)
        self.assertIn(('http', '1.2.3.4', 1024), self.c._speakers)
        self.assertEqual(self.c._speakers[('http', '1.2.3.4', 1024)],
                         {'name': 'base:request:http:1.2.3.4:1024',
                          'url': 'http://1.2.3.4:1024/{uuid}',
                          'protocol': 'http',
                          'wait': 5,
                          'interval': 10})
        self.mock_c_write_configuration.assert_called_once_with()
        self.mock_c_write_configuration.reset_mock()

        with self.assertRaises(AssertionError):
            self.c.add_speaker_spec('thing', 1024, '1.2.3.4', send_size=50)

    def test__get_remote_address(self):
        mock_instance = mock.Mock()
        mock_instance._listeners = {('udp', 1024): {'ipv4': '1.2.3.4'}}
        self.assertEqual(
            self.c._get_remote_address(mock_instance, 'udp', 1024), '1.2.3.4')

    def test__conncheck_home_dir(self):
        self.patch('zaza.utilities.installers.user_directory',
                   name='mock_user_directory')
        self.mock_user_directory.return_value = '/some/dir'
        self.assertEqual(self.c._conncheck_home_dir, '/some/dir')
        self.mock_user_directory.assert_called_once_with(
            None, 'conncheck')
        self.mock_user_directory.reset_mock()
        # check property caches
        self.assertEqual(self.c._conncheck_home_dir, '/some/dir')
        self.mock_user_directory.assert_not_called()

    def test_install_no_user_relative_homedir(self):
        self.patch('zaza.utilities.installers.user_directory',
                   name='mock_user_directory')
        self.mock_user_directory.return_value = '/some/dir'
        self.patch('zaza.utilities.installers.user_exists',
                   name='mock_user_exists')
        self.patch('zaza.utilities.installers.create_user',
                   name='mock_create_user')
        self.mock_create_user.return_value = '/home/conncheck'
        self.patch('zaza.utilities.installers.install_module_in_venv',
                   name='mock_install_module_in_venv')
        self.patch('zaza.utilities.installers.SystemdControl',
                   name='mock_SystemdControl')
        mock__systemd = mock.Mock()
        self.mock_SystemdControl.return_value = mock__systemd
        self.c._ssh_fn = 'ssh-fn'
        self.c._scp_fn = 'scp-fn'
        self.mock_user_exists.return_value = False

        self.c.install()
        self.mock_user_exists.assert_called_once_with('ssh-fn', 'conncheck')
        self.mock_create_user.assert_called_once_with('ssh-fn', 'conncheck')
        self.mock_install_module_in_venv.assert_called_once_with(
            '/some/source', '/home/conncheck/.', 'scp-fn', 'ssh-fn',
            run_user='conncheck')
        mock__systemd.install.assert_called_once_with()
        self.assertTrue(self.c._installed)

    def test_install_user_exists_absolute_homedir(self):
        self.patch('zaza.utilities.installers.user_directory',
                   name='mock_user_directory')
        self.mock_user_directory.return_value = '/some/dir'
        self.patch('zaza.utilities.installers.user_exists',
                   name='mock_user_exists')
        self.patch('zaza.utilities.installers.create_user',
                   name='mock_create_user')
        self.mock_create_user.return_value = '/home/conncheck'
        self.patch('zaza.utilities.installers.install_module_in_venv',
                   name='mock_install_module_in_venv')
        self.patch('zaza.utilities.installers.SystemdControl',
                   name='mock_SystemdControl')
        mock__systemd = mock.Mock()
        self.mock_SystemdControl.return_value = mock__systemd
        self.c._ssh_fn = 'ssh-fn'
        self.c._scp_fn = 'scp-fn'
        self.mock_user_exists.return_value = True
        self.c.install_dir = '/fixed'

        self.c.install()
        self.mock_user_exists.assert_called_once_with('ssh-fn', 'conncheck')
        self.mock_create_user.assert_not_called()
        self.mock_install_module_in_venv.assert_called_once_with(
            '/some/source', '/fixed', 'scp-fn', 'ssh-fn',
            run_user='conncheck')
        mock__systemd.install.assert_called_once_with()
        self.assertTrue(self.c._installed)

    def test__verify_systemd_not_none(self):
        self.c._systemd = 'thing'
        self.c._verify_systemd_not_none()
        self.c._systemd = None
        with self.assertRaises(AssertionError):
            self.c._verify_systemd_not_none()

    def test_remote_log_filename_property(self):
        self.patch('zaza.utilities.installers.user_directory',
                   name='mock_user_directory')
        self.mock_user_directory.return_value = '/some/dir'
        self.assertEqual(self.c.remote_log_filename, '/some/dir/conncheck.log')

    def test_local_log_filename_property(self):
        with self.assertRaises(NotImplementedError):
            self.c.local_log_filename

    def test_get_logfile_to_local(self):
        self.patch('zaza.utilities.installers.user_directory',
                   name='mock_user_directory')
        self.mock_user_directory.return_value = '/some/dir'
        mock_scp_fn = mock.Mock()
        self.c._scp_fn = mock_scp_fn
        with mock.patch.object(
                conncheck.ConnCheckInstanceBase, 'local_log_filename',
                new_callable=mock.PropertyMock) as mock_local_log_filename:
            mock_local_log_filename.return_value = 'some-filename'
            self.assertEqual(self.c.get_logfile_to_local('/a/dir'),
                             '/a/dir/some-filename')
        mock_scp_fn.assert_called_once_with('/some/dir/conncheck.log',
                                            '/a/dir/some-filename',
                                            copy_from=True)

    def test_write_configuration_not_installed_not_running(self):
        self.patch('zaza.utilities.installers.user_directory',
                   name='mock_user_directory')
        self.mock_user_directory.return_value = '/some/dir'
        self.patch_object(self.c, 'install', name='mock_c_install')
        self.patch_object(self.c, 'is_running', name='mock_c_is_running')
        self.mock_c_is_running.return_value = False
        self.patch_object(self.c, 'restart', name='mock_c_restart')
        mock_scp_fn = mock.Mock()
        self.c._scp_fn = mock_scp_fn
        mock_ssh_fn = mock.Mock()
        self.c._ssh_fn = mock_ssh_fn
        self.patch('yaml.dump', name='mock_yaml_dump')
        self.patch('tempfile.TemporaryDirectory',
                   name='mock_TemporaryDirectory')
        mock_td = mock.MagicMock()
        mock_td.__enter__.return_value = '/target'
        self.mock_TemporaryDirectory.return_value = mock_td

        with tests_utils.patch_open() as (mock_open, mock_file):
            self.c.write_configuration()

        self.mock_c_install.assert_called_once_with()
        mock_open.assert_called_once_with('/target/config.yaml', 'wt')
        expected_config = {
            'name': 'base',
            'file-log-path': '/some/dir/conncheck.log',
            'collection': 'a-collection',
            'log-format': 'InfluxDB',
            'listeners': [],
            'speakers': []
        }
        self.mock_yaml_dump.assert_called_once_with(expected_config, mock_file)
        mock_scp_fn.assert_called_once_with('/target/config.yaml',
                                            'config.yaml')
        mock_ssh_fn.assert_called_once_with(
            ['sudo', 'mv', 'config.yaml', '/some/dir/config.yaml'])
        self.mock_c_is_running.assert_called_once_with()
        self.mock_c_restart.assert_not_called()

    def test_write_configuration_installed_and_running(self):
        self.patch('zaza.utilities.installers.user_directory',
                   name='mock_user_directory')
        self.mock_user_directory.return_value = '/some/dir'
        self.patch_object(self.c, 'install', name='mock_c_install')
        self.patch_object(self.c, 'is_running', name='mock_c_is_running')
        self.mock_c_is_running.return_value = True
        self.patch_object(self.c, 'restart', name='mock_c_restart')
        mock_scp_fn = mock.Mock()
        self.c._scp_fn = mock_scp_fn
        mock_ssh_fn = mock.Mock()
        self.c._ssh_fn = mock_ssh_fn
        self.patch('yaml.dump', name='mock_yaml_dump')
        self.patch('tempfile.TemporaryDirectory',
                   name='mock_TemporaryDirectory')
        mock_td = mock.MagicMock()
        mock_td.__enter__.return_value = '/target'
        self.mock_TemporaryDirectory.return_value = mock_td
        self.c._installed = True

        with tests_utils.patch_open() as (mock_open, mock_file):
            self.c.write_configuration()

        self.mock_c_install.assert_not_called()
        mock_open.assert_called_once_with('/target/config.yaml', 'wt')
        expected_config = {
            'name': 'base',
            'file-log-path': '/some/dir/conncheck.log',
            'collection': 'a-collection',
            'log-format': 'InfluxDB',
            'listeners': [],
            'speakers': []
        }
        self.mock_yaml_dump.assert_called_once_with(expected_config, mock_file)
        mock_scp_fn.assert_called_once_with('/target/config.yaml',
                                            'config.yaml')
        mock_ssh_fn.assert_called_once_with(
            ['sudo', 'mv', 'config.yaml', '/some/dir/config.yaml'])
        self.mock_c_is_running.assert_called_once_with()
        self.mock_c_restart.assert_called_once_with()

    def test_is_running(self):
        self.patch_object(self.c, '_verify_systemd_not_none',
                          name='mock__verify_systemd_not_none')
        mock__systemd = mock.Mock()
        mock__systemd.is_running.return_value = False
        self.c._systemd = mock__systemd
        self.assertFalse(self.c.is_running())
        self.mock__verify_systemd_not_none.assert_called_once_with()
        mock__systemd.is_running.assert_called_once_with()

    def test_start(self):
        self.patch_object(self.c, '_verify_systemd_not_none',
                          name='mock__verify_systemd_not_none')
        mock__systemd = mock.Mock()
        self.c._systemd = mock__systemd
        self.c.start()
        self.mock__verify_systemd_not_none.assert_called_once_with()
        mock__systemd.start.assert_called_once_with()

    def test_stop(self):
        self.patch_object(conncheck, 'logger', name='mock_logger')
        self.c._systemd = None
        self.c.stop()
        self.mock_logger.debug.assert_called_once_with(mock.ANY, self.c)

        mock__systemd = mock.Mock()
        self.c._systemd = mock__systemd
        self.mock_logger.reset_mock()

        self.c.stop()
        mock__systemd.stop.assert_called_once_with()

    def test_restart(self):
        self.patch_object(self.c, '_verify_systemd_not_none',
                          name='mock__verify_systemd_not_none')
        mock__systemd = mock.Mock()
        self.c._systemd = mock__systemd
        self.c.restart()
        self.mock__verify_systemd_not_none.assert_called_once_with()
        mock__systemd.restart.assert_called_once_with()

    def test_finalise(self):
        self.c._installed = False
        mock__systemd = mock.Mock()
        self.c._systemd = mock__systemd
        self.patch_object(self.c, 'stop', name='mock_c_stop')

        self.c.finalise()
        self.mock_c_stop.assert_not_called()
        mock__systemd.disable.assert_not_called()

        self.c._installed = True
        self.c.finalise()
        self.mock_c_stop.assert_called_once_with()
        mock__systemd.disable.assert_called_once_with()

    def test_clean_up(self):
        self.c._installed = False
        mock__systemd = mock.Mock()
        self.c._systemd = mock__systemd
        self.patch_object(self.c, 'stop', name='mock_c_stop')

        self.c.clean_up()
        self.mock_c_stop.assert_not_called()
        mock__systemd.disable.assert_not_called()
        mock__systemd.remove.assert_not_called()

        self.c._installed = True
        self.c.clean_up()
        self.mock_c_stop.assert_called_once_with()
        mock__systemd.disable.assert_called_once_with()
        mock__systemd.remove.assert_called_once_with()


class TestConnCheckInstanceJuju(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch('zaza.utilities.installers.make_juju_ssh_fn',
                   name='mock_make_juju_ssh_fn')
        self.mock_ssh_fn = mock.Mock()
        self.mock_make_juju_ssh_fn = self.mock_ssh_fn
        self.patch('zaza.utilities.installers.make_juju_scp_fn',
                   name='mock_make_juju_scp_fn')
        self.mock_scp_fn = mock.Mock()
        self.mock_make_juju_scp_fn = self.mock_scp_fn
        self.c = conncheck.ConnCheckInstanceJuju(
            '0',
            model='some-model',
            user='a-user',
            module_source='/some/source',
            collection='a-collection')

    def test_init(self):
        c = conncheck.ConnCheckInstanceJuju(
            '0/lxd/15',
            log_format=conncheck.LogFormats.CSV,
            config_file='thing.yaml',
            install_dir='/opt',
            module_source='/some/other/source',
            install_user='a-user')
        self.assertEqual(c.machine_or_unit_spec, '0/lxd/15')
        self.assertEqual(c.name, '0/lxd/15')
        self.assertEqual(c.log_format, conncheck.LogFormats.CSV)
        self.assertEqual(c.config_file, 'thing.yaml')
        self.assertEqual(c.install_dir, '/opt')
        self.assertEqual(c.module_source, '/some/other/source')
        self.assertEqual(c.install_user, 'a-user')

        self.assertEqual(self.c.machine_or_unit_spec, '0')
        self.assertEqual(self.c.name, '0')
        self.assertEqual(self.c.log_format, conncheck.LogFormats.InfluxDB)
        self.assertEqual(self.c.config_file, 'config.yaml')
        self.assertEqual(self.c.install_dir, '.')
        self.assertEqual(self.c.module_source, '/some/source')
        self.assertEqual(self.c.install_user, 'conncheck')

    def test_local_log_filename(self):
        self.assertEqual(self.c.local_log_filename, '0.log')
        self.c.machine_or_unit_spec = '0/lxd/15'
        self.assertEqual(self.c.local_log_filename, '0_lxd_15.log')

    def test__validate_spec(self):
        MACHINE = self.c.JujuTypes.MACHINE
        UNIT = self.c.JujuTypes.UNIT
        valid_specs = (('0', MACHINE),
                       ('9', MACHINE),
                       ('15', MACHINE),
                       ('0/lxd/10', MACHINE),
                       ('1/LXD/4', MACHINE),
                       ('some-unit-0/14', UNIT),
                       ('other/23', UNIT))
        invalid_specs = ('b', '1/spec/2', 'other-unit', 'd/10/10')

        for spec, type_ in valid_specs:
            self.c.machine_or_unit_spec = spec
            self.c._validate_spec()
            self.assertEqual(self.c._juju_type, type_)

        for spec in invalid_specs:
            self.c.machine_or_unit_spec = spec
            with self.assertRaises(ValueError):
                self.c._validate_spec()

    def test_add_listener(self):
        self.patch_object(self.c, '_validate_not_existing_listener',
                          name='mock__validate_not_existing_listener')
        self.patch_object(self.c, '_get_address', name='mock__get_address')
        self.mock__get_address.return_value = '1.2.3.4'
        self.patch_object(self.c, 'add_listener_spec',
                          name='mock_add_listener_spec')
        self.c.add_listener('udp', 1024, space='default', cidr='cidr')
        self.mock__validate_not_existing_listener.assert_called_once_with(
            'udp', 1024)
        self.mock__get_address('default', 'cidr')
        self.mock_add_listener_spec.assert_called_once_with(
            'udp', 1024, '1.2.3.4', reply_size=1024)

    def test__get_address(self):
        self.patch_object(self.c, '_get_address_unit',
                          name='mock__get_address_unit')
        self.mock__get_address_unit.return_value = '1.2.3.4'
        self.patch_object(self.c, '_get_address_machine',
                          name='mock__get_address_machine')
        self.mock__get_address_machine.return_value = '5.6.7.8'

        self.c._juju_type = self.c.JujuTypes.UNIT
        self.assertEqual(self.c._get_address(None, 'cidr'), '1.2.3.4')
        self.mock__get_address_unit.assert_called_once_with(
            'juju-info', 'cidr')
        self.mock__get_address_unit.reset_mock()

        self.c._juju_type = self.c.JujuTypes.MACHINE
        self.assertEqual(self.c._get_address(None, 'cidr'), '5.6.7.8')
        self.mock__get_address_machine.assert_called_once_with('cidr')

        self.c._juju_type = None
        with self.assertRaises(RuntimeError):
            self.c._get_address(None, 'cidr')

    def test__get_address_unit_single_address(self):
        self.patch('subprocess.check_output', name='mock_check_output')
        self.patch_object(conncheck, 'logger', name='mock_logger')
        self.patch('yaml.safe_load', name='mock_yaml_safe_load')

        self.mock_check_output.return_value = b'1.2.3.4'
        self.mock_yaml_safe_load.return_value = '1.2.3.4\n'
        self.assertEqual(self.c._get_address_unit('a-space', 'a-cidr'),
                         '1.2.3.4')
        self.mock_check_output.assert_called_once_with(
            ['juju', 'run', '-u', '0', '--', 'network-get', '--format',
             'yaml', '--bind-address', 'a-space'])
        self.mock_yaml_safe_load.assert_called_once_with('1.2.3.4')

    def test__get_address_unit_multiple_address(self):
        self.patch('subprocess.check_output', name='mock_check_output')
        self.patch_object(conncheck, 'logger', name='mock_logger')
        self.patch('yaml.safe_load', name='mock_yaml_safe_load')

        self.mock_check_output.return_value = b'1.2.3.4'
        self.mock_yaml_safe_load.return_value = ['1.2.3.4', '5.6.7.8']
        with self.assertRaises(NotImplementedError):
            self.c._get_address_unit('a-space', 'a-cidr')

    def test__get_address_unit_network_get_fails(self):
        self.patch('subprocess.check_output', name='mock_check_output')
        self.patch_object(conncheck, 'logger', name='mock_logger')
        self.patch('yaml.safe_load', name='mock_yaml_safe_load')

        self.mock_check_output.return_value = b'1.2.3.4'

        def raise_(*args):
            raise subprocess.CalledProcessError(cmd='bang', returncode=1)

        self.mock_check_output.side_effect = raise_

        with self.assertRaises(subprocess.CalledProcessError):
            self.c._get_address_unit('a-space', 'a-cidr')

    def test__get_address_machine(self):
        with self.assertRaises(NotImplementedError):
            self.c._get_address_machine()


class TestConnCheckInstanceSSH(tests_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch('zaza.utilities.installers.make_ssh_fn',
                   name='mock_make_ssh_fn')
        self.mock_ssh_fn = mock.Mock()
        self.mock_make_ssh_fn = self.mock_ssh_fn
        self.patch('zaza.utilities.installers.make_scp_fn',
                   name='mock_make_scp_fn')
        self.mock_scp_fn = mock.Mock()
        self.mock_make_scp_fn = self.mock_scp_fn
        self.c = conncheck.ConnCheckInstanceSSH(
            address='1.2.3.4',
            key_file='a-file',
            user='a-user',
            module_source='/some/source',
            collection='a-collection')

    def test_init(self):
        c = conncheck.ConnCheckInstanceSSH(
            '5.6.7.8',
            'my-key-file',
            log_format=conncheck.LogFormats.CSV,
            config_file='thing.yaml',
            install_dir='/opt',
            module_source='/some/other/source',
            install_user='a-user')
        self.assertEqual(c.address, '5.6.7.8')
        self.assertEqual(c.key_file, 'my-key-file')
        self.assertEqual(c.name, '5.6.7.8')
        self.assertEqual(c.log_format, conncheck.LogFormats.CSV)
        self.assertEqual(c.config_file, 'thing.yaml')
        self.assertEqual(c.install_dir, '/opt')
        self.assertEqual(c.module_source, '/some/other/source')
        self.assertEqual(c.install_user, 'a-user')

        self.assertEqual(self.c.address, '1.2.3.4')
        self.assertEqual(self.c.key_file, 'a-file')
        self.assertEqual(self.c.name, '1.2.3.4')
        self.assertEqual(self.c.log_format, conncheck.LogFormats.InfluxDB)
        self.assertEqual(self.c.config_file, 'config.yaml')
        self.assertEqual(self.c.install_dir, '.')
        self.assertEqual(self.c.module_source, '/some/source')
        self.assertEqual(self.c.install_user, 'conncheck')

    def test_local_log_filename(self):
        self.c.address = 'user@1.2.3.4'
        self.assertEqual(self.c.local_log_filename, 'user_1-2-3-4.log')

    def test_add_listener(self):
        self.patch_object(self.c, '_validate_not_existing_listener',
                          name='mock__validate_not_existing_listener')
        self.patch_object(self.c, 'add_listener_spec',
                          name='mock_add_listener_spec')
        self.c.add_listener('udp', 1024)
        self.mock__validate_not_existing_listener.assert_called_once_with(
            'udp', 1024)
        self.mock_add_listener_spec.assert_called_once_with(
            'udp', 1024, '0.0.0.0', reply_size=1024)
