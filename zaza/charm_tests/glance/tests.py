#!/usr/bin/env python3

import logging

import zaza.utilities.openstack as openstack_utils
import zaza.charm_tests.test_utils as test_utils


class GlanceTest(test_utils.OpenStackBaseTest):

    @classmethod
    def setUpClass(cls):
        super(GlanceTest, cls).setUpClass()
        cls.glance_client = openstack_utils.get_glance_session_client(
            cls.keystone_session)

    def test_410_glance_image_create_delete(self):
        """Create an image and then delete it"""
        image_url = openstack_utils.find_cirros_image(arch='x86_64')
        image = openstack_utils.create_image(
            self.glance_client,
            image_url,
            'cirrosimage')
        openstack_utils.delete_image(self.glance_client, image.id)

    def test_411_set_disk_format(self):
        """Change disk format and assert then change propagates to the correct
           file and that services are restarted as a result"""
        # Expected default and alternate values
        set_default = {
            'disk-formats': 'ami,ari,aki,vhd,vmdk,raw,qcow2,vdi,iso,root-tar'}
        set_alternate = {'disk-formats': 'qcow2'}

        # Config file affected by juju set config change
        conf_file = '/etc/glance/glance-api.conf'

        # Make config change, check for service restarts
        logging.debug('Setting disk format glance...')
        self.restart_on_changed(
            conf_file,
            set_default,
            set_alternate,
            {'image_format': {
                'disk_formats': [
                    'ami,ari,aki,vhd,vmdk,raw,qcow2,vdi,iso,root-tar']}},
            {'image_format': {'disk_formats': ['qcow2']}},
            ['glance-api'])

    def test_901_pause_resume(self):
        """Pause service and check services are stopped then resume and check
           they are started"""
        self.pause_resume(['glance-api'])
