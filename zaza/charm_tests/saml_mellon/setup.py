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

"""Code for setting up keystone federation."""

import json
import keystoneauth1
import os
import tempfile

import zaza.charm_lifecycle.utils as charm_lifecycle_utils
import zaza.model
from zaza.utilities import (
    cert as cert_utils,
    cli as cli_utils,
    openstack as openstack_utils,
)


APP_NAME = "keystone-saml-mellon"

FEDERATED_DOMAIN = "federated_domain"
FEDERATED_GROUP = "federated_users"
MEMBER = "Member"
IDP = "samltest"
REMOTE_ID = "https://samltest.id/saml/idp"
MAP_NAME = "{}_mapping".format(IDP)
PROTOCOL_NAME = "mapped"
MAP_TEMPLATE = '''
    [{{
            "local": [
                {{
                    "user": {{
                        "name": "{{0}}"
                    }},
                    "group": {{
                        "name": "federated_users",
                        "domain": {{
                            "id": "{domain_id}"
                        }}
                    }},
                    "projects": [
                    {{
                        "name": "{{0}}_project",
                        "roles": [
                                     {{
                                         "name": "Member"
                                     }}
                                 ]
                    }}
                    ]
               }}
            ],
            "remote": [
                {{
                    "type": "MELLON_NAME_ID"
                }}
            ]
    }}]
'''

SP_SIGNING_KEY_INFO_XML_TEMPLATE = '''
<ds:KeyInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
    <ds:X509Data>
        <ds:X509Certificate>
            {}
        </ds:X509Certificate>
    </ds:X509Data>
</ds:KeyInfo>
'''


def keystone_federation_setup():
    """Configure Keystone Federation."""
    cli_utils.setup_logging()
    keystone_session = openstack_utils.get_overcloud_keystone_session()
    keystone_client = openstack_utils.get_keystone_session_client(
        keystone_session)

    try:
        domain = keystone_client.domains.find(name=FEDERATED_DOMAIN)
    except keystoneauth1.exceptions.http.NotFound:
        domain = keystone_client.domains.create(
            FEDERATED_DOMAIN,
            description="Federated Domain",
            enabled=True)

    try:
        group = keystone_client.groups.find(
            name=FEDERATED_GROUP, domain=domain)
    except keystoneauth1.exceptions.http.NotFound:
        group = keystone_client.groups.create(
            FEDERATED_GROUP,
            domain=domain,
            enabled=True)

    role = keystone_client.roles.find(name=MEMBER)
    keystone_client.roles.grant(role, group=group, domain=domain)

    try:
        idp = keystone_client.federation.identity_providers.find(
            name=IDP, domain_id=domain.id)
    except keystoneauth1.exceptions.http.NotFound:
        idp = keystone_client.federation.identity_providers.create(
            IDP,
            remote_ids=[REMOTE_ID],
            domain_id=domain.id,
            enabled=True)

    JSON_RULES = json.loads(MAP_TEMPLATE.format(domain_id=domain.id))

    try:
        keystone_client.federation.mappings.find(name=MAP_NAME)
    except keystoneauth1.exceptions.http.NotFound:
        keystone_client.federation.mappings.create(
            MAP_NAME, rules=JSON_RULES)

    try:
        keystone_client.federation.protocols.get(IDP, PROTOCOL_NAME)
    except keystoneauth1.exceptions.http.NotFound:
        keystone_client.federation.protocols.create(
            PROTOCOL_NAME, mapping=MAP_NAME, identity_provider=idp)


def attach_saml_resources(application="keystone-saml-mellon"):
    """Attach resource to the Keystone SAML Mellon charm."""
    test_idp_metadata_xml = "samltest.xml"
    idp_metadata_xml_file = os.path.join(
        charm_lifecycle_utils.BUNDLE_DIR, test_idp_metadata_xml)

    idp_metadata_name = "idp-metadata"
    sp_private_key_name = "sp-private-key"
    sp_signing_keyinfo_name = "sp-signing-keyinfo"

    zaza.model.attach_resource(
        application, idp_metadata_name, idp_metadata_xml_file)

    (key, cert) = cert_utils.generate_cert('SP Signing Key')

    with tempfile.NamedTemporaryFile(mode='w', suffix='.pem') as fp:
        fp.write(key.decode())
        fp.flush()
        zaza.model.attach_resource(application, sp_private_key_name, fp.name)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml') as fp:
        fp.write(SP_SIGNING_KEY_INFO_XML_TEMPLATE.format(key.decode()))
        fp.flush()
        zaza.model.attach_resource(
            application, sp_signing_keyinfo_name, fp.name)
