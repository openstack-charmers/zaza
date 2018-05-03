import mock

import unit_tests.utils as ut_utils
import zaza.utilities.cert as cert


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
