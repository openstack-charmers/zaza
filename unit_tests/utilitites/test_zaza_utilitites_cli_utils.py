import mock
import unit_tests.utils as ut_utils
from zaza.utilities import cli_utils


class TestCLIUtils(ut_utils.BaseTestCase):

    def setUp(self):
        super(TestCLIUtils, self).setUp()

    def test_parse_arg(self):
        _options = mock.MagicMock()
        _arg_property = "property-value"
        _options.property = _arg_property
        # Argparse value
        self.assertEqual(cli_utils.parse_arg(_options, "property"),
                         _arg_property)

        # Single value environment
        _environ_value = "environ-value"
        _env = {"PROPERTY": _environ_value}
        with mock.patch.dict(cli_utils.os.environ, _env):
            self.assertEqual(cli_utils.parse_arg(_options, "property"),
                             _environ_value)

        # Multi value environment
        _multi_value = "val1 val2"
        _env = {"PROPERTY": _multi_value}
        with mock.patch.dict(cli_utils.os.environ, _env):
            self.assertEqual(
                cli_utils.parse_arg(_options, "property", multiargs=True),
                _multi_value.split())

    def test_setup_logging(self):
        self.patch_object(cli_utils, "logging")
        _logformatter = mock.MagicMock()
        _logger = mock.MagicMock()
        _consolehandler = mock.MagicMock()
        self.logging.Formatter.return_value = _logformatter
        self.logging.getLogger.return_value = _logger
        self.logging.StreamHandler.return_value = _consolehandler
        cli_utils.setup_logging()
        self.logging.Formatter.assert_called_with(
            datefmt='%Y-%m-%d %H:%M:%S',
            fmt='%(asctime)s [%(levelname)s] %(message)s')
        self.logging.getLogger.assert_called_with()
        _logger.setLevel.assert_called_with("INFO")
        _consolehandler.setFormatter.assert_called_with(_logformatter)
        _logger.addHandler.assert_called_with(_consolehandler)
