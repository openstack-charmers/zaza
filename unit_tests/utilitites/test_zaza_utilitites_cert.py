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
