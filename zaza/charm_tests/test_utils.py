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
"""Module containg base class for implementing charm tests."""
import contextlib
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


def audit_assertions(action,
                     expected_passes,
                     expected_failures=None,
                     expected_to_pass=True):
    """Check expected assertion failures in security-checklist actions.

    :param action: Action object from running the security-checklist action
    :type action: juju.action.Action
    :param expected_passes: List of test names that are expected to pass
    :type expected_passes: List[str]
    :param expected_failures: List of test names that are expected to fail
    :type expexted_failures: List[str]
    """
    if expected_failures is None:
        expected_failures = []
    if expected_to_pass:
        assert action.data["status"] == "completed", \
            "Security check is expected to pass by default"
    else:
        assert action.data["status"] == "failed", \
            "Security check is not expected to pass by default"

    results = action.data['results']
    for key, value in results.items():
        if key in expected_failures:
            assert "FAIL" in value, "Unexpected test pass: {}".format(key)
        if key in expected_passes:
            assert value == "PASS", "Unexpected failure: {}".format(key)


class OpenStackBaseTest(unittest.TestCase):
    """Generic helpers for testing OpenStack API charms."""

    @classmethod
    def setUpClass(cls):
        """Run setup for test class to create common resourcea."""
        cls.keystone_session = openstack_utils.get_overcloud_keystone_session()
        cls.model_name = model.get_juju_model()
        cls.test_config = lifecycle_utils.get_charm_config()
        cls.application_name = cls.test_config['charm_name']
        cls.lead_unit = model.get_lead_unit_name(
            cls.application_name,
            model_name=cls.model_name)
        logging.debug('Leader unit is {}'.format(cls.lead_unit))

    @contextlib.contextmanager
    def config_change(self, default_config, alternate_config,
                      application_name=None):
        """Run change config tests.

        Change config to `alternate_config`, wait for idle workload status,
        yield, return config to `default_config` and wait for idle workload
        status before return from function.

        Example usage:
            with self.config_change({'preferred-api-version': '2'},
                                    {'preferred-api-version': '3'}):
                do_something()

        :param default_config: Dict of charm settings to set on completion
        :type default_config: dict
        :param alternate_config: Dict of charm settings to change to
        :type alternate_config: dict
        :param application_name: String application name for use when called
                                 by a charm under test other than the object's
                                 application.
        :type application_name: str
        """
        if not application_name:
            application_name = self.application_name
        # we need to compare config values to what is already applied before
        # attempting to set them.  otherwise the model will behave differently
        # than we would expect while waiting for completion of the change
        _app_config = model.get_application_config(application_name)
        app_config = {}
        # convert the more elaborate config structure from libjuju to something
        # we can compare to what the caller supplies to this function
        for k in alternate_config.keys():
            # note that conversion to string for all values is due to
            # attempting to set any config with other types lead to Traceback
            app_config[k] = str(_app_config.get(k, {}).get('value', ''))
        if all(item in app_config.items()
                for item in alternate_config.items()):
            logging.debug('alternate_config equals what is already applied '
                          'config')
            yield
            if default_config == alternate_config:
                logging.debug('default_config also equals what is already '
                              'applied config')
                return
            logging.debug('alternate_config already set, and default_config '
                          'needs to be applied before return')
        else:
            logging.debug('Changing charm setting to {}'
                          .format(alternate_config))
            model.set_application_config(
                application_name,
                alternate_config,
                model_name=self.model_name)

            logging.debug(
                'Waiting for units to execute config-changed hook')
            model.wait_for_agent_status(model_name=self.model_name)

            logging.debug(
                'Waiting for units to reach target states')
            model.wait_for_application_states(
                model_name=self.model_name,
                states=self.test_config.get('target_deploy_status', {}))
            # TODO: Optimize with a block on a specific application until idle.
            model.block_until_all_units_idle()

            yield

        logging.debug('Restoring charm setting to {}'.format(default_config))
        model.set_application_config(
            application_name,
            default_config,
            model_name=self.model_name)

        logging.debug(
            'Waiting for units to reach target states')
        model.wait_for_application_states(
            model_name=self.model_name,
            states=self.test_config.get('target_deploy_status', {}))
        # TODO: Optimize with a block on a specific application until idle.
        model.block_until_all_units_idle()

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
        # lead_unit is only useed to grab a timestamp, the assumption being
        # that all the units times are in sync.

        mtime = model.get_unit_time(
            self.lead_unit,
            model_name=self.model_name)
        logging.debug('Remote unit timestamp {}'.format(mtime))

        with self.config_change(default_config, alternate_config):
            logging.debug(
                'Waiting for updates to propagate to {}'.format(config_file))
            model.block_until_oslo_config_entries_match(
                self.application_name,
                config_file,
                alternate_entry,
                model_name=self.model_name)

            # Config update has occured and hooks are idle. Any services should
            # have been restarted by now:
            logging.debug(
                'Waiting for services ({}) to be restarted'.format(services))
            model.block_until_services_restarted(
                self.application_name,
                mtime,
                services,
                model_name=self.model_name)

            logging.debug(
                'Waiting for updates to propagate to '.format(config_file))
            model.block_until_oslo_config_entries_match(
                self.application_name,
                config_file,
                default_entry,
                model_name=self.model_name)

    @contextlib.contextmanager
    def pause_resume(self, services):
        """Run Pause and resume tests.

        Pause and then resume a unit checking that services are in the
        required state after each action

        :param services: Services expected to be restarted when config_file is
                         changed.
        :type services: list
        """
        model.block_until_service_status(
            self.lead_unit,
            services,
            'running',
            model_name=self.model_name)
        model.block_until_unit_wl_status(
            self.lead_unit,
            'active',
            model_name=self.model_name)
        model.run_action(
            self.lead_unit,
            'pause',
            model_name=self.model_name)
        model.block_until_unit_wl_status(
            self.lead_unit,
            'maintenance',
            model_name=self.model_name)
        model.block_until_all_units_idle(model_name=self.model_name)
        model.block_until_service_status(
            self.lead_unit,
            services,
            'stopped',
            model_name=self.model_name)
        yield
        model.run_action(
            self.lead_unit,
            'resume',
            model_name=self.model_name)
        model.block_until_unit_wl_status(
            self.lead_unit,
            'active',
            model_name=self.model_name)
        model.block_until_all_units_idle(model_name=self.model_name)
        model.block_until_service_status(
            self.lead_unit,
            services,
            'running',
            model_name=self.model_name)
