# Copyright 2019 Canonical Ltd.
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

"""Encapsulate ``ceph-rbd-mirror`` testing."""
import json
import logging
import re

import zaza.charm_tests.test_utils as test_utils

import zaza.model
import zaza.utilities.ceph
import zaza.utilities.openstack

from zaza.charm_tests.glance.setup import LTS_IMAGE_NAME


class CephRBDMirrorBase(test_utils.OpenStackBaseTest):
    """Base class for ``ceph-rbd-mirror`` tests."""

    @classmethod
    def setUpClass(cls):
        """Run setup for ``ceph-rbd-mirror`` tests."""
        super().setUpClass()
        # get ready for multi-model Zaza
        cls.site_a_model = cls.site_b_model = zaza.model.get_juju_model()
        cls.site_b_app_suffix = '-b'

    def run_status_action(self, application_name=None, model_name=None):
        """Run status action, decode and return response."""
        result = zaza.model.run_action_on_leader(
            application_name or self.application_name,
            'status',
            model_name=model_name,
            action_params={
                'verbose': True,
                'format': 'json',
            })
        return json.loads(result.results['output'])

    def get_pools(self):
        """Retrieve list of pools from both sites.

        :returns: Tuple with list of pools on each side.
        :rtype: tuple
        """
        site_a_pools = zaza.utilities.ceph.get_ceph_pools(
            zaza.model.get_lead_unit_name(
                'ceph-mon', model_name=self.site_a_model),
            model_name=self.site_a_model)
        site_b_pools = zaza.utilities.ceph.get_ceph_pools(
            zaza.model.get_lead_unit_name(
                'ceph-mon' + self.site_b_app_suffix,
                model_name=self.site_b_model),
            model_name=self.site_b_model)
        return sorted(site_a_pools.keys()), sorted(site_b_pools.keys())

    def wait_for_mirror_state(self, state, application_name=None,
                              model_name=None,
                              check_entries_behind_master=False):
        """Wait until all images reach requested state.

        This function runs the ``status`` action and examines the data it
        returns.

        :param state: State to expect all images to be in
        :type state: str
        :param application_name: Application to run action on
        :type application_name: str
        :param model_name: Model to run in
        :type model_name: str
        :param check_entries_behind_master: Wait for ``entries_behind_master``
                                            to become '0'.  Only makes sense
                                            when used with state
                                            ``up+replying``.
        :type check_entries_behind_master: bool
        :returns: True on success, never returns on failure
        """
        rep = re.compile(r'.*entries_behind_master=(\d+)')
        while True:
            pool_status = self.run_status_action(
                application_name=application_name, model_name=model_name)
            for pool, status in pool_status.items():
                for image in status.get('images', []):
                    if image['state'] and image['state'] != state:
                        break
                    if check_entries_behind_master:
                        m = rep.match(image['description'])
                        # NOTE(fnordahl): Tactical fix for upstream Ceph
                        # Luminous bug https://tracker.ceph.com/issues/23516
                        if m and int(m.group(1)) > 42:
                            logging.info('entries_behind_master={}'
                                         .format(m.group(1)))
                            break
                else:
                    # not found here, check next pool
                    continue
                # found here, pass on to outer loop
                break
            else:
                # all images with state has expected state
                return True


class CephRBDMirrorTest(CephRBDMirrorBase):
    """Encapsulate ``ceph-rbd-mirror`` tests."""

    def test_pause_resume(self):
        """Run pause and resume tests."""
        self.pause_resume(['rbd-mirror'])

    def test_pool_broker_synced(self):
        """Validate that pools created with broker protocol are synced.

        The functional test bundle includes the ``cinder``, ``cinder-ceph`` and
        ``glance`` charms.  The ``cinder-ceph`` and ``glance`` charms will
        create pools using the ceph charms broker protocol at deploy time.
        """
        site_a_pools, site_b_pools = self.get_pools()
        self.assertEqual(site_a_pools, site_b_pools)

    def test_pool_manual_synced(self):
        """Validate that manually created pools are synced after refresh.

        The ``ceph-rbd-mirror`` charm does not get notified when the operator
        creates a pool manually without using the ceph charms broker protocol.

        To alleviate this the charm has a ``refresh-pools`` action the operator
        can call to have it discover such pools.  Validate its operation.
        """
        # use action on ceph-mon to create a pool directly in the Ceph cluster
        # without using the broker protocol
        zaza.model.run_action_on_leader(
            'ceph-mon',
            'create-pool',
            model_name=self.site_a_model,
            action_params={
                'name': 'zaza',
                'app-name': 'rbd',
            })
        # tell ceph-rbd-mirror unit on site_a to refresh list of pools
        zaza.model.run_action_on_leader(
            'ceph-rbd-mirror',
            'refresh-pools',
            model_name=self.site_a_model,
            action_params={
            })
        # wait for execution to start
        zaza.model.wait_for_agent_status(model_name=self.site_a_model)
        zaza.model.wait_for_agent_status(model_name=self.site_b_model)
        # wait for execution to finish
        zaza.model.wait_for_application_states(model_name=self.site_a_model)
        zaza.model.wait_for_application_states(model_name=self.site_b_model)
        # make sure everything is idle before we test
        zaza.model.block_until_all_units_idle(model_name=self.site_a_model)
        zaza.model.block_until_all_units_idle(model_name=self.site_b_model)
        # validate result
        site_a_pools, site_b_pools = self.get_pools()
        self.assertEqual(site_a_pools, site_b_pools)

    def test_cinder_volume_mirrored(self):
        """Validate that a volume created through Cinder is mirrored.

        For RBD Mirroring to work clients must enable the correct set of
        features when creating images.

        The RBD image feature settings are announced by the ``ceph-mon`` charm
        over the client relation when it has units related on its
        ``rbd-mirror`` endpoint.

        By creating a volume through cinder on site A, checking for presence on
        site B and subsequently comparing the contents we get a full end to end
        test.
        """
        session = zaza.utilities.openstack.get_overcloud_keystone_session()
        glance = zaza.utilities.openstack.get_glance_session_client(session)
        cinder = zaza.utilities.openstack.get_cinder_session_client(session)

        image = next(glance.images.list(name=LTS_IMAGE_NAME))

        # NOTE(fnordahl): for some reason create volume from image often fails
        # when run just after deployment is finished.  We should figure out
        # why, resolve the underlying issue and then remove this.
        #
        # We do not use tenacity here as it will interfere with tenacity used
        # in ``resource_reaches_status``
        def create_volume_from_image(cinder, image, retry=5):
            if retry < 1:
                return
            volume = cinder.volumes.create(8, name='zaza', imageRef=image.id)
            try:
                zaza.utilities.openstack.resource_reaches_status(
                    cinder.volumes, volume.id, msg='volume')
                return volume
            except AssertionError:
                logging.info('retrying')
                volume.delete()
                return create_volume_from_image(cinder, image, retry=retry - 1)
        volume = create_volume_from_image(cinder, image)

        site_a_hash = zaza.utilities.ceph.get_rbd_hash(
            zaza.model.get_lead_unit_name('ceph-mon',
                                          model_name=self.site_a_model),
            'cinder-ceph',
            'volume-{}'.format(volume.id),
            model_name=self.site_a_model)
        self.wait_for_mirror_state(
            'up+replaying',
            check_entries_behind_master=True,
            application_name=self.application_name + self.site_b_app_suffix,
            model_name=self.site_b_model)
        site_b_hash = zaza.utilities.ceph.get_rbd_hash(
            zaza.model.get_lead_unit_name('ceph-mon' + self.site_b_app_suffix,
                                          model_name=self.site_b_model),
            'cinder-ceph',
            'volume-{}'.format(volume.id),
            model_name=self.site_b_model)
        logging.info(site_a_hash)
        logging.info(site_b_hash)
        self.assertEqual(site_a_hash, site_b_hash)


class CephRBDMirrorControlledFailoverTest(CephRBDMirrorBase):
    """Encapsulate ``ceph-rbd-mirror`` controlled failover tests."""

    def test_fail_over_fall_back(self):
        """Validate controlled fail over and fall back."""
        site_a_pools, site_b_pools = self.get_pools()
        result = zaza.model.run_action_on_leader(
            'ceph-rbd-mirror',
            'demote',
            model_name=self.site_a_model,
            action_params={})
        logging.info(result.results)
        n_pools_demoted = len(result.results['output'].split('\n'))
        self.assertEqual(len(site_a_pools), n_pools_demoted)
        self.wait_for_mirror_state('up+unknown', model_name=self.site_a_model)
        self.wait_for_mirror_state(
            'up+unknown',
            application_name=self.application_name + self.site_b_app_suffix,
            model_name=self.site_b_model)
        result = zaza.model.run_action_on_leader(
            'ceph-rbd-mirror' + self.site_b_app_suffix,
            'promote',
            model_name=self.site_b_model,
            action_params={})
        logging.info(result.results)
        n_pools_promoted = len(result.results['output'].split('\n'))
        self.assertEqual(len(site_b_pools), n_pools_promoted)
        self.wait_for_mirror_state(
            'up+replaying',
            model_name=self.site_a_model)
        self.wait_for_mirror_state(
            'up+stopped',
            application_name=self.application_name + self.site_b_app_suffix,
            model_name=self.site_b_model)
        result = zaza.model.run_action_on_leader(
            'ceph-rbd-mirror' + self.site_b_app_suffix,
            'demote',
            model_name=self.site_b_model,
            action_params={
            })
        logging.info(result.results)
        n_pools_demoted = len(result.results['output'].split('\n'))
        self.assertEqual(len(site_a_pools), n_pools_demoted)
        self.wait_for_mirror_state(
            'up+unknown',
            model_name=self.site_a_model)
        self.wait_for_mirror_state(
            'up+unknown',
            application_name=self.application_name + self.site_b_app_suffix,
            model_name=self.site_b_model)
        result = zaza.model.run_action_on_leader(
            'ceph-rbd-mirror',
            'promote',
            model_name=self.site_a_model,
            action_params={
            })
        logging.info(result.results)
        n_pools_promoted = len(result.results['output'].split('\n'))
        self.assertEqual(len(site_b_pools), n_pools_promoted)
        self.wait_for_mirror_state(
            'up+stopped',
            model_name=self.site_a_model)
        self.wait_for_mirror_state(
            'up+replaying',
            application_name=self.application_name + self.site_b_app_suffix,
            model_name=self.site_b_model)


class CephRBDMirrorDisasterFailoverTest(CephRBDMirrorBase):
    """Encapsulate ``ceph-rbd-mirror`` destructive tests."""

    def test_kill_site_a_fail_over(self):
        """Validate fail over after uncontrolled shutdown of primary."""
        for application in 'ceph-rbd-mirror', 'ceph-mon', 'ceph-osd':
            zaza.model.remove_application(
                application,
                model_name=self.site_a_model,
                forcefully_remove_machines=True)
        result = zaza.model.run_action_on_leader(
            'ceph-rbd-mirror' + self.site_b_app_suffix,
            'promote',
            model_name=self.site_b_model,
            action_params={
            })
        self.assertEqual(result.status, 'failed')
        result = zaza.model.run_action_on_leader(
            'ceph-rbd-mirror' + self.site_b_app_suffix,
            'promote',
            model_name=self.site_b_model,
            action_params={
                'force': True,
            })
        self.assertEqual(result.status, 'completed')
