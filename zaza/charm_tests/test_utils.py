"""Module containg base class for implementing charm tests."""
import logging
import unittest
import zaza.model

import zaza.model as model
import zaza.charm_lifecycle.utils as lifecycle_utils
import zaza.utilities.openstack as openstack_utils


def skipIfNotHA(service_name):
    """Run decorator to skip tests if application not in HA configuration."""
    def _skipIfNotHA_inner_1(f):
        def _skipIfNotHA_inner_2(*args, **kwargs):
            ips = zaza.model.get_app_ips(
                service_name)
            if len(ips) > 1:
                return f(*args, **kwargs)
            else:
                logging.warn("Skipping HA test for non-ha service {}".format(
                    service_name))
        return _skipIfNotHA_inner_2

    return _skipIfNotHA_inner_1


class OpenStackBaseTest(unittest.TestCase):
    """Generic helpers for testing OpenStack API charms."""

    @classmethod
    def setUpClass(cls):
        """Run setup for test class to create common resourcea."""
        cls.keystone_session = openstack_utils.get_overcloud_keystone_session()
        cls.model_name = model.get_juju_model()
        cls.test_config = lifecycle_utils.get_charm_config()
        cls.application_name = cls.test_config['charm_name']
        cls.first_unit = model.get_first_unit_name(
            cls.model_name,
            cls.application_name)
        logging.debug('First unit is {}'.format(cls.first_unit))

    def restart_on_changed(self, config_file, default_config, alternate_config,
                           default_entry, alternate_entry, services):
        """Run restart on change tests.

        Test that changing config results in config file being updates and
        services restarted. Return config to default_config afterwards

        :param config_file: Config file to check for settings
        :type config_file: str
        :param default_config: Dict of charm settings to set on completion
        :type default_config: dict
        :param alternate_config: Dict of charm settings to change to
        :type alternate_config: dict
        :param default_entry: Config file entries that correspond to
                              default_config
        :type default_entry: dict
        :param alternate_entry: Config file entries that correspond to
                                alternate_config
        :type alternate_entry: dict
        :param services: Services expected to be restarted when config_file is
                         changed.
        :type services: list
        """
        # first_unit is only useed to grab a timestamp, the assumption being
        # that all the units times are in sync.

        mtime = model.get_unit_time(self.model_name, self.first_unit)
        logging.debug('Remote unit timestamp {}'.format(mtime))

        logging.debug('Changing charm setting to {}'.format(alternate_config))
        model.set_application_config(
            self.model_name,
            self.application_name,
            alternate_config)

        logging.debug(
            'Waiting for updates to propagate to {}'.format(config_file))
        model.block_until_oslo_config_entries_match(
            self.model_name,
            self.application_name,
            config_file,
            alternate_entry)

        logging.debug(
            'Waiting for units to reach target states'.format(config_file))
        model.wait_for_application_states(
            self.model_name,
            self.test_config.get('target_deploy_status', {}))

        # Config update has occured and hooks are idle. Any services should
        # have been restarted by now:
        logging.debug(
            'Waiting for services ({}) to be restarted'.format(services))
        model.block_until_services_restarted(
            self.model_name,
            self.application_name,
            mtime,
            services)

        logging.debug('Restoring charm setting to {}'.format(default_config))
        model.set_application_config(
            self.model_name,
            self.application_name,
            default_config)

        logging.debug(
            'Waiting for updates to propagate to '.format(config_file))
        model.block_until_oslo_config_entries_match(
            self.model_name,
            self.application_name,
            config_file,
            default_entry)

        logging.debug(
            'Waiting for units to reach target states'.format(config_file))
        model.wait_for_application_states(
            self.model_name,
            self.test_config.get('target_deploy_status', {}))

    def pause_resume(self, services):
        """Run Pause and resume tests.

        Pause and then resume a unit checking that services are in the
        required state after each action

        :param services: Services expected to be restarted when config_file is
                         changed.
        :type services: list
        """
        model.block_until_service_status(
            self.model_name,
            self.first_unit,
            services,
            'running')
        model.block_until_unit_wl_status(
            self.model_name,
            self.first_unit,
            'active')
        model.run_action(self.model_name, self.first_unit, 'pause', {})
        model.block_until_unit_wl_status(
            self.model_name,
            self.first_unit,
            'maintenance')
        model.block_until_all_units_idle(self.model_name)
        model.block_until_service_status(
            self.model_name,
            self.first_unit,
            services,
            'stopped')
        model.run_action(self.model_name, self.first_unit, 'resume', {})
        model.block_until_unit_wl_status(
            self.model_name,
            self.first_unit,
            'active')
        model.block_until_all_units_idle(self.model_name)
        model.block_until_service_status(
            self.model_name,
            self.first_unit,
            services,
            'running')
