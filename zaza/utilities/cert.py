#!/usr/bin/env python3
#
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

import cryptography
from cryptography.hazmat.primitives.asymmetric import rsa
import cryptography.hazmat.primitives.serialization as serialization
import datetime


def generate_cert(common_name,
                  password=None,
                  issuer_name=None,
                  signing_key=None,
                  signing_key_password=None,
                  generate_ca=False):
    """
    Generate x.509 certificate

    Example of how to create a certificate chain:
        (cakey, cacert) = generate_cert('DivineAuthority', generate_ca=True)
        (crkey, crcert) = generate_cert('test.com',
                                        issuer_name='DivineAuthority',
                                        signing_key=cakey)

    :param common_name: Common Name to use in generated certificate
    :type common_name: str
    :param password: Password to protect encrypted private key with
    :type password: Optional[str]
    :param issuer_name: Issuer name, must match provided_private_key issuer
    :type issuer_name: Optional[str]
    :param signing_key: PEM encoded PKCS8 formatted private key
    :type signing_key: Optional[str]
    :param signing_key_password: Password to decrypt private key
    :type signing_key_password: Optional[str]
    :param generate_ca: Generate a certificate usable as a CA certificate
    :type generate_ca: bool
    :returns: x.509 certificate
    :rtype: cryptography.x509.Certificate
    """
    if password is not None:
        encryption_algorithm = serialization.BestAvailableEncryption(password)
    else:
        encryption_algorithm = serialization.NoEncryption()

    if signing_key:
        _signing_key = serialization.load_pem_private_key(
            signing_key,
            password=signing_key_password,
            backend=cryptography.hazmat.backends.default_backend(),
        )

    private_key = rsa.generate_private_key(
        public_exponent=65537,  # per RFC 5280 Appendix C
        key_size=2048,
        backend=cryptography.hazmat.backends.default_backend()
    )

    public_key = private_key.public_key()

    builder = cryptography.x509.CertificateBuilder()
    builder = builder.subject_name(cryptography.x509.Name([
        cryptography.x509.NameAttribute(
            cryptography.x509.oid.NameOID.COMMON_NAME, common_name),
    ]))

    if issuer_name is None:
        issuer_name = common_name

    builder = builder.issuer_name(cryptography.x509.Name([
        cryptography.x509.NameAttribute(
            cryptography.x509.oid.NameOID.COMMON_NAME, issuer_name),
    ]))
    builder = builder.not_valid_before(
        datetime.datetime.today() - datetime.timedelta(1, 0, 0),
    )
    builder = builder.not_valid_after(
        datetime.datetime.today() + datetime.timedelta(1, 0, 0),
    )
    builder = builder.serial_number(cryptography.x509.random_serial_number())
    builder = builder.public_key(public_key)
    builder = builder.add_extension(
        cryptography.x509.SubjectAlternativeName(
            [cryptography.x509.DNSName(common_name)],
        ),
        critical=False,
    )
    builder = builder.add_extension(
        cryptography.x509.BasicConstraints(ca=generate_ca, path_length=None),
        critical=True,
    )

    if signing_key:
        sign_key = _signing_key
    else:
        sign_key = private_key

    certificate = builder.sign(
        private_key=sign_key,
        algorithm=cryptography.hazmat.primitives.hashes.SHA256(),
        backend=cryptography.hazmat.backends.default_backend(),
    )

    return (
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption_algorithm),
        certificate.public_bytes(
            serialization.Encoding.PEM)
    )
