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

"""Keystone SAML Mellon Testing."""

import logging
from lxml import etree
import requests

import zaza.model
from zaza.charm_tests.keystone import BaseKeystoneTest


class FailedToReachIDP(Exception):
    """Custom Exception for failing to reach the IDP."""

    pass


class CharmKeystoneSAMLMellonTest(BaseKeystoneTest):
    """Charm Keystone SAML Mellon tests."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running Keystone SAML Mellon charm tests."""
        super(CharmKeystoneSAMLMellonTest, cls).setUpClass()
        cls.action = "get-sp-metadata"

    def test_run_get_sp_metadata_action(self):
        """Validate the get-sp-metadata action."""
        if self.vip:
            ip = self.vip
        else:
            unit = zaza.model.get_units(self.application_name)[0]
            ip = unit.public_address

        action = zaza.model.run_action(unit.entity_id, self.action)
        if "failed" in action.data["status"]:
            raise Exception(
                "The action failed: {}".format(action.data["message"]))

        output = action.data["results"]["output"]
        root = etree.fromstring(output)
        for item in root.items():
            if "entityID" in item[0]:
                assert ip in item[1]

        for appt in root.getchildren():
            for elem in appt.getchildren():
                for item in elem.items():
                    if "Location" in item[0]:
                        assert ip in item[1]

        logging.info("Successul get-sp-metadata action")

    def test_saml_mellon_redirects(self):
        """Validate the horizon -> keystone -> IDP redirects."""
        if self.vip:
            keystone_ip = self.vip
        else:
            unit = zaza.model.get_units(self.application_name)[0]
            keystone_ip = unit.public_address

        horizon = "openstack-dashboard"
        horizon_vip = (zaza.model.get_application_config(horizon)
                       .get("vip").get("value"))
        if horizon_vip:
            horizon_ip = horizon_vip
        else:
            unit = zaza.model.get_units("openstack-dashboard")[0]
            horizon_ip = unit.public_address

        if self.tls_rid:
            proto = "https"
        else:
            proto = "http"

        url = "{}://{}/horizon/auth/login/".format(proto, horizon_ip)
        region = "{}://{}:5000/v3".format(proto, keystone_ip)
        horizon_expect = ('<option value="samltest_mapped">'
                          'samltest.id</option>')

        # This is the message samltest.id gives when it has not had
        # SP XML uploaded. It still shows we have been directed to:
        # horizon -> keystone -> samltest.id
        idp_expect = ("The application you have accessed is not registered "
                      "for use with this service.")

        def _do_redirect_check(url, region, idp_expect, horizon_expect):

            # start session, get csrftoken
            client = requests.session()
            # Verify=False see note below
            login_page = client.get(url, verify=False)

            # Validate SAML method is available
            assert horizon_expect in login_page.text

            # Get cookie
            if "csrftoken" in client.cookies:
                csrftoken = client.cookies["csrftoken"]
            else:
                raise Exception("Missing csrftoken")

            # Build and send post request
            form_data = {
                "auth_type": "samltest_mapped",
                "csrfmiddlewaretoken": csrftoken,
                "next": "/horizon/project/api_access",
                "region": region,
            }

            # Verify=False due to CA certificate bundles.
            # If we point to the CA for keystone/horizon they work but
            # samltest.id does not.
            # If we don't set it validation fails for keystone/horizon
            # We would have to install the keystone CA onto the system
            # to validate end to end.
            response = client.post(
                url, data=form_data,
                headers={"Referer": url},
                allow_redirects=True,
                verify=False)

            if idp_expect not in response.text:
                msg = "FAILURE code={} text={}".format(response, response.text)
                # Raise a custom exception.
                raise FailedToReachIDP(msg)

        # Execute the check
        # We may need to try/except to allow horizon to build its pages
        _do_redirect_check(url, region, idp_expect, horizon_expect)
        logging.info("SUCCESS")
