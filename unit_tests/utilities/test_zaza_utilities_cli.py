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

import argparse
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

    def setup_logging_mocks(self, has_handlers=False):
        self.patch_object(cli_utils, "logging")
        _logformatter = mock.MagicMock()
        _logger = mock.MagicMock()
        _logger.hasHandlers.return_value = has_handlers
        _consolehandler = mock.MagicMock()
        setattr(self.logging, 'INFO', 20)
        setattr(self.logging, 'DEBUG', 10)
        self.logging.Formatter.return_value = _logformatter
        self.logging.getLogger.return_value = _logger
        self.logging.StreamHandler.return_value = _consolehandler
        return _logger, _consolehandler, _logformatter

    def test_setup_logging(self):
        _logger, _consolehandler, _logformatter = self.setup_logging_mocks()
        cli_utils.setup_logging()
        self.logging.Formatter.assert_called_with(
            datefmt='%Y-%m-%d %H:%M:%S',
            fmt='%(asctime)s [%(levelname)s] %(message)s')
        self.logging.getLogger.assert_called_with()
        _logger.setLevel.assert_called_with(20)
        _consolehandler.setFormatter.assert_called_with(_logformatter)
        _logger.addHandler.assert_called_with(_consolehandler)

    def test_setup_logging_existing_handler(self):
        _logger, _, _ = self.setup_logging_mocks(has_handlers=True)
        cli_utils.setup_logging()
        self.assertFalse(_logger.addHandler.called)

    def test_setup_logging_invalid_loglevel(self):
        _, _, _ = self.setup_logging_mocks()
        with self.assertRaises(ValueError):
            cli_utils.setup_logging('invalid')

    def test_setup_logging_mixed_case_loglevel(self):
        _logger, _, _ = self.setup_logging_mocks()
        cli_utils.setup_logging('DeBug')
        _logger.setLevel.assert_called_with(10)

    def test_parser_single_model(self):
        parser = argparse.ArgumentParser()
        cli_utils.add_model_parser(parser)
        result = parser.parse_args([
            '-m', 'mod1'])
        self.assertEqual(
            result.model,
            {'default_alias': 'mod1'})

    def test_parser_single_models(self):
        parser = argparse.ArgumentParser()
        cli_utils.add_model_parser(parser)
        result = parser.parse_args([
            '--models', 'model1'])
        self.assertEqual(
            result.model,
            {'default_alias': 'model1'})

    def test_parser_model_map(self):
        parser = argparse.ArgumentParser()
        cli_utils.add_model_parser(parser)
        result = parser.parse_args([
            '-m', 'modalias1:model1'])
        self.assertEqual(
            result.model,
            {'modalias1': 'model1'})

    def test_parser_multi_modeli_map(self):
        parser = argparse.ArgumentParser()
        cli_utils.add_model_parser(parser)
        result = parser.parse_args([
            '-m', 'modalias1:model1',
            '-m', 'modalias2:model2'])
        self.assertEqual(
            result.model,
            {
                'modalias1': 'model1',
                'modalias2': 'model2'})
