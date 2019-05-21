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

import mock
import unit_tests.utils as ut_utils
from zaza.utilities import cli as cli_utils


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
        _logger.hasHandlers.return_value = False
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

    def test_setup_logging_existing_handler(self):
        self.patch_object(cli_utils, "logging")
        _logformatter = mock.MagicMock()
        _logger = mock.MagicMock()
        _logger.hasHandlers.return_value = True
        _consolehandler = mock.MagicMock()
        self.logging.Formatter.return_value = _logformatter
        self.logging.getLogger.return_value = _logger
        self.logging.StreamHandler.return_value = _consolehandler
        cli_utils.setup_logging()
        self.assertFalse(_logger.addHandler.called)
