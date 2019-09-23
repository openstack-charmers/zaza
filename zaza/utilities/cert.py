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
"""Module for working with x.509 certificates."""

import cryptography
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import cryptography.hazmat.primitives.hashes as hashes
import cryptography.hazmat.primitives.serialization as serialization
import datetime
import ipaddress


def generate_cert(common_name,
                  alternative_names=None,
                  password=None,
                  issuer_name=None,
                  signing_key=None,
                  signing_key_password=None,
                  generate_ca=False):
    """Generate x.509 certificate.

    Example of how to create a certificate chain::

        (cakey, cacert) = generate_cert(
            'DivineAuthority',
            generate_ca=True)
        (crkey, crcert) = generate_cert(
            'test.com',
            issuer_name='DivineAuthority',
            signing_key=cakey)

    :param common_name: Common Name to use in generated certificate
    :type common_name: str
    :param alternative_names: List of names to add as SubjectAlternativeName
    :type alternative_names: Optional[list(str)]
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
        encryption_algorithm = serialization.BestAvailableEncryption(
            password.encode('utf-8'))
    else:
        encryption_algorithm = serialization.NoEncryption()

    if signing_key:
        if signing_key_password:
            signing_key_password = signing_key_password.encode('utf-8')
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
        datetime.datetime.utcnow() - datetime.timedelta(0, 1, 0),
    )
    builder = builder.not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(30, 0, 0),
    )
    builder = builder.serial_number(cryptography.x509.random_serial_number())
    builder = builder.public_key(public_key)

    san_list = [cryptography.x509.DNSName(common_name)]
    if alternative_names is not None:
        for name in alternative_names:
            try:
                addr = ipaddress.ip_address(name)
            except ValueError:
                san_list.append(cryptography.x509.DNSName(name))
            else:
                san_list.append(cryptography.x509.IPAddress(addr))

    builder = builder.add_extension(
        cryptography.x509.SubjectAlternativeName(
            san_list,
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


def sign_csr(csr, ca_private_key, ca_cert=None, issuer_name=None,
             ca_private_key_password=None, generate_ca=False):
    """Sign CSR with the given key.

    :param csr: Certificate to sign
    :type csr: str
    :param ca_private_key: Private key to be used to sign csr
    :type ca_private_key: str
    :param ca_cert: Cert to base some options from
    :type ca_cert: str
    :param issuer_name: Issuer name, must match provided_private_key issuer
    :type issuer_name: Optional[str]
    :param ca_private_key_password: Password to decrypt ca_private_key
    :type ca_private_key_password: Optional[str]
    :param generate_ca: Allow resulting cert to be used as ca
    :type generate_ca: bool
    :returns: x.509 certificate
    :rtype: cryptography.x509.Certificate
    """
    backend = cryptography.hazmat.backends.default_backend()
    # Create x509 artifacts
    root_ca_pkey = serialization.load_pem_private_key(
        ca_private_key.encode(),
        password=ca_private_key_password,
        backend=backend)

    new_csr = cryptography.x509.load_pem_x509_csr(
        csr.encode(),
        backend)

    if ca_cert:
        root_ca_cert = cryptography.x509.load_pem_x509_certificate(
            ca_cert.encode(),
            backend)
        issuer_name = root_ca_cert.subject
    else:
        issuer_name = issuer_name
    # Create builder
    builder = cryptography.x509.CertificateBuilder()
    builder = builder.serial_number(
        cryptography.x509.random_serial_number())
    builder = builder.issuer_name(issuer_name)
    builder = builder.not_valid_before(
        datetime.datetime.today() - datetime.timedelta(1, 0, 0),
    )
    builder = builder.not_valid_after(
        datetime.datetime.today() + datetime.timedelta(80, 0, 0),
    )
    builder = builder.subject_name(new_csr.subject)
    builder = builder.public_key(new_csr.public_key())

    builder = builder.add_extension(
        cryptography.x509.BasicConstraints(ca=generate_ca, path_length=None),
        critical=True
    )

    # Sign the csr
    signer_ca_cert = builder.sign(
        private_key=root_ca_pkey,
        algorithm=hashes.SHA256(),
        backend=backend)

    return signer_ca_cert.public_bytes(encoding=serialization.Encoding.PEM)


def is_keys_valid(public_key_string, private_key_string):
    """Test whether these are a valid public/private key pair.

    :param public_key_string: PEM encoded key data.
    :type public_key_string: str
    :param private_key_string: OpenSSH encoded key data.
    :type private_key_string: str
    """
    private_key = serialization.load_pem_private_key(
        private_key_string.encode(),
        password=None,
        backend=cryptography.hazmat.backends.default_backend()
    )
    public_key = serialization.load_ssh_public_key(
        public_key_string.encode(),
        backend=cryptography.hazmat.backends.default_backend()
    )
    message = b"encrypted data"
    ciphertext = public_key.encrypt(
        message,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None))

    try:
        plaintext = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None))
    except ValueError:
        plaintext = ''
    return plaintext == message
