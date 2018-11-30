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

"""Code for configuring octavia."""

import os
import base64
import logging

import zaza.utilities.cert
import zaza.charm_lifecycle.utils
import zaza.charm_tests.test_utils
import zaza.charm_tests.glance.setup as glance_setup


def add_amphora_image(image_url=None):
    """Add Octavia ``amphora`` test image to glance.

    :param image_url: URL where image resides
    :type image_url: str
    """
    image_name = 'amphora-x64-haproxy'
    if not image_url:
        image_url = (
            os.environ.get('FUNCTEST_AMPHORA_LOCATION', None) or
            'http://tarballs.openstack.org/octavia/test-images/'
            'test-only-amphora-x64-haproxy-ubuntu-xenial.qcow2')
    glance_setup.add_image(
        image_url,
        image_name=image_name,
        tags=['octavia-amphora'])


def configure_amphora_certs():
    """Configure certificates for internal Octavia client/server auth."""
    (issuing_cakey, issuing_cacert) = zaza.utilities.cert.generate_cert(
        'OSCI Zaza Issuer',
        password='zaza',
        generate_ca=True)
    (controller_cakey, controller_cacert) = zaza.utilities.cert.generate_cert(
        'OSCI Zaza Octavia Controller',
        generate_ca=True)
    (controller_key, controller_cert) = zaza.utilities.cert.generate_cert(
        '*.serverstack',
        issuer_name='OSCI Zaza Octavia Controller',
        signing_key=controller_cakey)
    controller_bundle = controller_cert + controller_key
    cert_config = {
        'lb-mgmt-issuing-cacert': base64.b64encode(
            issuing_cacert).decode('utf-8'),
        'lb-mgmt-issuing-ca-private-key': base64.b64encode(
            issuing_cakey).decode('utf-8'),
        'lb-mgmt-issuing-ca-key-passphrase': 'zaza',
        'lb-mgmt-controller-cacert': base64.b64encode(
            controller_cacert).decode('utf-8'),
        'lb-mgmt-controller-cert': base64.b64encode(
            controller_bundle).decode('utf-8'),
    }
    logging.info('Configuring certificates for mandatory Octavia '
                 'client/server authentication '
                 '(client being the ``Amphorae`` load balancer instances)')

    # Our expected workload status will change after we have configured the
    # certificates
    test_config = zaza.charm_lifecycle.utils.get_charm_config()
    del test_config['target_deploy_status']['octavia']

    _singleton = zaza.charm_tests.test_utils.OpenStackBaseTest()
    _singleton.setUpClass()
    with _singleton.config_change(cert_config, cert_config):
        # wait for configuration to be applied then return
        pass
