import mock

import unit_tests.utils as ut_utils
import zaza.utilities.cert as cert

TEST_SSH_PRIVATE_KEY = """
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAvWNz+tJAVyudNsDYrFK4CnJV+/nBmjYJXC3Zf42RFmzJ/Sff
bMSXM/OBPOPtpJg/FawzsTgoHQRMQ/oEcKRSJ0ZGQINlwlrfHdyJcdyH4ifad2oT
42cYRW0yMJggQGe7ttruCvY0mZugwrCjHoX3bqKjSg7YaMpyUKBa2cwCWJu/GUlp
sT1jjY89QYvzb/Auj5lMfk8Qmc4fIcC7EZ+lf+1iuwg7OJjRKbsBqVhUgTKisTxD
kzvo6SLy49j+mWUjfWlCI74D6QhW8OH9sN6MxI1sYiomPrCo+eBc1fkr0dUT8xd6
t1UL6HHx8XkO16BMbLc+lIVNiifZtAK3SL1BnwIDAQABAoIBABZYxtWgu3DNt6Y/
SRHETO0GorixtrNwjtgunMxdMvJ3cboKW2WlKMY7hFNf/al/QWpYQF036BvMZwda
V+3Gpd72ftGb74ToXg1S+XDS+cGovDF89c3OW2HNya9MM/oFg3PHD3GBraE2aNiw
KP8wBYsra6MQb16mDKkQ0seCOACmY/4jYlZ/7YbFtZPBPeZpnlxg4hgFIkiJmuPf
pmHpLFBhpmyo0yf3DGf/rsL9ti6LPBo8vCH6anM9ljn/BW2a3JA/ap4uUGb+FuoV
lwa1by1L6uLNYQb3fSEtmEEIy1mn89SjlEPfHnooXdadTM+9zT9xIc1ArNOSZagU
UHibUXECgYEA5C3h8d1MU5tKppoIM8aOC+OQFZbFd+bF8z+t7RdX9P6br5J0Ugtj
GcykUz6IRQWGZRCsyM9zshK2gQRCul0byNcFjzIHhR62Va6h1u7iwN1F4qc8a5WS
bb/1TEVprTSu9guW8OO/EmUgWkBgej4/j31F8PZG4+m1defLZXNo7skCgYEA1HrN
UOaBMzaFujGRZjlF54v7flCa1YYcv51Dfk8LEScs/jJvTY664ofj6AfQQN37Akmh
6B6jBfP8K7RxcJvAXE00oNliDvwo9TxoTc/F59HbgsEcR739fMjwvpOBWJg0zJy8
28/29dy9e0Fcy6ay55l050+0CBdzkvTWNHBVWScCgYEAhsTi0qvWTPtHmCcZ+Rqp
AzShAV9PuoW/HPDblVFYTgejhIuH0H2RRserts8URVACFOdIZkLBHsgWqxUNJG2h
33nAetcdwe5l2y2NwRjPLQKEKF6GPTTWi6P5CddllzuqqwAlYpnhXMgF18h2Mz1Y
5TMkgDG1pR+AYedKJt2HeKECgYAKR+LVTkHkG3g++RUC8DR8rp49j2Lef/22G8Lf
Qq3TZ6Taq9AM3aIXQeH6IR6ndNYnVy65T3ot2I9UAggXHcIh9S5dtgbzmKnWq9SU
J0B5JgNMAVH/+qZgOkzDu9lfUwYC/HZ64EYfwU19wDzgMbGoWRl587ZPSesyqhwP
L3xBswKBgQDc3WnWDP/KFjzWKY8KG4XZYKvvOy1en4hytbWrFssu5HlYoQeRgAog
K8ZAFLW2Mn0QebwL/gXSDYlZHmu6EbnO4v1kzRMi6aQxYOgKJWLEwj3r3hzJh6YU
QEGH15IncVqMch6HIir4oTF7RY2BsikDDY/GB/l0pRfZrGl9mnrY6Q==
-----END RSA PRIVATE KEY-----
"""
TEST_SSH_PUB_KEY = """ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC9Y3P60kBXK502wNisUrgKclX7+cGaNglcLdl/jZEWbMn9J99sxJcz84E84+2kmD8VrDOxOCgdBExD+gRwpFInRkZAg2XCWt8d3Ilx3IfiJ9p3ahPjZxhFbTIwmCBAZ7u22u4K9jSZm6DCsKMehfduoqNKDthoynJQoFrZzAJYm78ZSWmxPWONjz1Bi/Nv8C6PmUx+TxCZzh8hwLsRn6V/7WK7CDs4mNEpuwGpWFSBMqKxPEOTO+jpIvLj2P6ZZSN9aUIjvgPpCFbw4f2w3ozEjWxiKiY+sKj54FzV+SvR1RPzF3q3VQvocfHxeQ7XoExstz6UhU2KJ9m0ArdIvUGf ubuntu@gnuoy-bastion """  # noqa
TEST_SSH_PUB_KEY_INVALID = """ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDMz6U88GVhwAjjhzSrcyKKWe3LfB4pK4Ap6XpIfSmiVDPTBiBU3wzj1YAIBo26OMHDkfUnmtBgtzOfcb64QPaUmMfCkzadxrd8inYlpz+0AoahCTTONkElMxj+wa7SYVF4GphrDKDvlPi83bcLmO39veNVcLYHcDa+9mWBP3AlI3TdKqJpgOtCzLu9qbhlpmYa7YD6ijQrTJI3wOOw0uZeEARVCCKU44BVUFnWrNx5ioihETj9rAxRFrm1dx8mKDP0fCf53/Xn+LKLcYBPVovT6BpBHkaLuG6mTYU7puHN607wRhRwYhc3Y9y0sd6rHykYKL3G27w08s597paFtXg5 ubuntu@gnuoy-bastion"""  # noqa


class TestUtilitiesCert(ut_utils.BaseTestCase):

    def test_generate_cert(self):
        self.patch_object(cert, 'serialization')
        self.patch_object(cert, 'rsa')
        self.patch_object(cert, 'cryptography')
        cert.generate_cert('unit_test.ci.local')
        self.assertTrue(self.serialization.NoEncryption.called)
        self.cryptography.x509.NameAttribute.assert_called_with(
            self.cryptography.x509.oid.NameOID.COMMON_NAME,
            'unit_test.ci.local',
        )
        self.cryptography.x509.SubjectAlternativeName.assert_called_with(
            [
                self.cryptography.x509.DNSName('unit_test.ci.local'),
            ]
        )
        self.cryptography.x509.BasicConstraints.assert_called_with(
            ca=False, path_length=None
        )

    def test_generate_cert_san(self):
        self.patch_object(cert, 'serialization')
        self.patch_object(cert, 'rsa')
        self.patch_object(cert, 'cryptography')
        cert.generate_cert(
            'unit_test.ci.local',
            alternative_names=['unit_test_second.ci.local', '172.16.42.1']
        )
        self.assertTrue(self.serialization.NoEncryption.called)
        self.cryptography.x509.NameAttribute.assert_called_with(
            self.cryptography.x509.oid.NameOID.COMMON_NAME,
            'unit_test.ci.local',
        )
        self.cryptography.x509.SubjectAlternativeName.assert_called_with(
            [
                self.cryptography.x509.DNSName('unit_test.ci.local'),
                self.cryptography.x509.DNSName('unit_test_second.ci.local'),
                self.cryptography.x509.IPAddress('172.16.42.1'),
            ]
        )
        self.cryptography.x509.BasicConstraints.assert_called_with(
            ca=False, path_length=None
        )

    def test_generate_cert_password(self):
        self.patch_object(cert, 'serialization')
        self.patch_object(cert, 'rsa')
        self.patch_object(cert, 'cryptography')
        cert.generate_cert('unit_test.ci.local', password='secret')
        self.serialization.BestAvailableEncryption.assert_called_with('secret')
        self.cryptography.x509.NameAttribute.assert_called_with(
            self.cryptography.x509.oid.NameOID.COMMON_NAME,
            'unit_test.ci.local',
        )
        self.cryptography.x509.SubjectAlternativeName.assert_called_with(
            [
                self.cryptography.x509.DNSName('unit_test.ci.local'),
            ]
        )
        self.cryptography.x509.BasicConstraints.assert_called_with(
            ca=False, path_length=None
        )

    def test_generate_cert_issuer_name(self):
        self.patch_object(cert, 'serialization')
        self.patch_object(cert, 'rsa')
        self.patch_object(cert, 'cryptography')
        cert.generate_cert('unit_test.ci.local', issuer_name='issuer')
        self.cryptography.x509.NameAttribute.assert_called_with(
            self.cryptography.x509.oid.NameOID.COMMON_NAME,
            'issuer',
        )
        self.cryptography.x509.BasicConstraints.assert_called_with(
            ca=False, path_length=None
        )

    def test_generate_cert_signing_key(self):
        self.patch_object(cert, 'serialization')
        self.patch_object(cert, 'rsa')
        self.patch_object(cert, 'cryptography')
        cert.generate_cert('unit_test.ci.local', signing_key='signing_key')
        self.assertTrue(self.serialization.NoEncryption.called)
        self.serialization.load_pem_private_key.assert_called_with(
            'signing_key',
            password=None,
            backend=self.cryptography.hazmat.backends.default_backend(),
        )
        self.cryptography.x509.NameAttribute.assert_called_with(
            self.cryptography.x509.oid.NameOID.COMMON_NAME,
            'unit_test.ci.local',
        )
        self.cryptography.x509.SubjectAlternativeName.assert_called_with(
            [
                self.cryptography.x509.DNSName('unit_test.ci.local'),
            ]
        )
        self.cryptography.x509.BasicConstraints.assert_called_with(
            ca=False, path_length=None
        )

    def test_generate_cert_signing_key_signing_key_password(self):
        self.patch_object(cert, 'serialization')
        self.patch_object(cert, 'rsa')
        self.patch_object(cert, 'cryptography')
        cert.generate_cert(
            'unit_test.ci.local',
            signing_key='signing_key',
            signing_key_password='signing_key_password',
        )
        self.assertTrue(self.serialization.NoEncryption.called)
        self.serialization.load_pem_private_key.assert_called_with(
            'signing_key',
            password='signing_key_password',
            backend=self.cryptography.hazmat.backends.default_backend(),
        )
        self.cryptography.x509.NameAttribute.assert_called_with(
            self.cryptography.x509.oid.NameOID.COMMON_NAME,
            'unit_test.ci.local',
        )
        self.cryptography.x509.SubjectAlternativeName.assert_called_with(
            [
                self.cryptography.x509.DNSName('unit_test.ci.local'),
            ]
        )
        self.cryptography.x509.BasicConstraints.assert_called_with(
            ca=False, path_length=None
        )

    def test_generate_cert_generate_ca(self):
        self.patch_object(cert, 'serialization')
        self.patch_object(cert, 'rsa')
        self.patch_object(cert, 'cryptography')
        cert.generate_cert('unit_test.ci.local', generate_ca=True)
        self.assertTrue(self.serialization.NoEncryption.called)
        self.cryptography.x509.NameAttribute.assert_called_with(
            self.cryptography.x509.oid.NameOID.COMMON_NAME,
            'unit_test.ci.local',
        )
        self.cryptography.x509.SubjectAlternativeName.assert_called_with(
            [
                self.cryptography.x509.DNSName('unit_test.ci.local'),
            ]
        )
        self.cryptography.x509.BasicConstraints.assert_called_with(
            ca=True, path_length=None
        )

    def sign_csr_mocks(self):
        self.patch_object(cert, 'serialization')
        self.patch_object(cert, 'cryptography')
        self.expect_bend = self.cryptography.hazmat.backends.default_backend()
        self.builder_mock = mock.MagicMock()
        self.builder_mock.serial_number.return_value = self.builder_mock
        self.builder_mock.issuer_name.return_value = self.builder_mock
        self.builder_mock.not_valid_before.return_value = self.builder_mock
        self.builder_mock.not_valid_after.return_value = self.builder_mock
        self.builder_mock.subject_name.return_value = self.builder_mock
        self.builder_mock.public_key.return_value = self.builder_mock
        self.builder_mock.add_extension.return_value = self.builder_mock

        self.cryptography.x509.CertificateBuilder.return_value = \
            self.builder_mock
        self.bcons_mock = mock.MagicMock()
        self.cryptography.x509.BasicConstraints.side_effect = self.bcons_mock

    def test_sign_csr(self):
        self.sign_csr_mocks()
        cert.sign_csr('acsr', 'secretkey', ca_cert='cacert')
        self.serialization.load_pem_private_key.assert_called_with(
            b'secretkey',
            password=None,
            backend=self.expect_bend)
        self.cryptography.x509.load_pem_x509_csr.assert_called_with(
            b'acsr',
            self.expect_bend)
        self.cryptography.x509.load_pem_x509_certificate.assert_called_with(
            b'cacert',
            self.expect_bend)

    def test_sign_csr_key_password(self):
        self.sign_csr_mocks()
        cert.sign_csr('acsr', 'secretkey', ca_cert='cacert',
                      ca_private_key_password='bob')
        self.serialization.load_pem_private_key.assert_called_with(
            b'secretkey',
            password='bob',
            backend=self.expect_bend)
        self.cryptography.x509.load_pem_x509_csr.assert_called_with(
            b'acsr',
            self.expect_bend)
        self.cryptography.x509.load_pem_x509_certificate.assert_called_with(
            b'cacert',
            self.expect_bend)
        self.bcons_mock.assert_called_with(ca=False, path_length=None)
        self.builder_mock.add_extension.assert_called_once_with(
            self.bcons_mock(),
            critical=True)

    def test_sign_csr_issuer_name(self):
        self.sign_csr_mocks()
        cert.sign_csr('acsr', 'secretkey', issuer_name='issuer')
        self.serialization.load_pem_private_key.assert_called_with(
            b'secretkey',
            password=None,
            backend=self.expect_bend)
        self.cryptography.x509.load_pem_x509_csr.assert_called_with(
            b'acsr',
            self.expect_bend)
        self.bcons_mock.assert_called_with(ca=False, path_length=None)
        self.builder_mock.issuer_name.assert_called_once_with('issuer')
        self.builder_mock.add_extension.assert_called_once_with(
            self.bcons_mock(),
            critical=True)

    def test_sign_csr_generate_ca(self):
        self.sign_csr_mocks()
        cert.sign_csr('acsr', 'secretkey', issuer_name='issuer',
                      generate_ca=True)
        self.serialization.load_pem_private_key.assert_called_with(
            b'secretkey',
            password=None,
            backend=self.expect_bend)
        self.cryptography.x509.load_pem_x509_csr.assert_called_with(
            b'acsr',
            self.expect_bend)
        self.bcons_mock.assert_called_with(ca=True, path_length=None)
        self.builder_mock.issuer_name.assert_called_once_with('issuer')
        self.builder_mock.add_extension.assert_called_once_with(
            self.bcons_mock(),
            critical=True)

    def test_is_keys_valid(self):
        self.assertTrue(
            cert.is_keys_valid(TEST_SSH_PUB_KEY, TEST_SSH_PRIVATE_KEY))

    def test_is_keys_valid_invalid(self):
        self.assertFalse(
            cert.is_keys_valid(TEST_SSH_PUB_KEY_INVALID, TEST_SSH_PRIVATE_KEY))
