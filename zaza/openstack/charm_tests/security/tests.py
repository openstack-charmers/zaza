#!/usr/bin/env python3

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

"""Encapsulate general security testing."""

import unittest

import zaza.model as model
import zaza.charm_lifecycle.utils as utils
from zaza.openstack.utilities.file_assertions import (
    assert_path_glob,
    assert_single_file,
)


def _make_test_function(application, file_details, paths=None):
    """Generate a test function given the specified inputs.

    :param application: Application name to assert file ownership on
    :type application: str
    :param file_details: Dictionary of file details to test
    :type file_details: dict
    :param paths: List of paths to test in this application
    :type paths: Optional[list(str)]
    :returns: Test function
    :rtype: unittest.TestCase
    """
    def test(self):
        for unit in model.get_units(application):
            unit = unit.entity_id
            if '*' in file_details['path']:
                assert_path_glob(self, unit, file_details, paths)
            else:
                assert_single_file(self, unit, file_details)
    return test


def _add_tests():
    """Add tests to the unittest.TestCase."""
    def class_decorator(cls):
        """Add tests based on input yaml to `cls`."""
        files = utils.get_charm_config('./file-assertions.yaml')
        deployed_applications = model.sync_deployed()
        for name, attributes in files.items():
            # Lets make sure to only add tests for deployed applications
            if name in deployed_applications:
                paths = [
                    file['path'] for
                    file in attributes['files']
                    if "*" not in file["path"]
                ]
                for file in attributes['files']:
                    test_func = _make_test_function(name, file, paths=paths)
                    setattr(
                        cls,
                        'test_{}_{}'.format(name, file['path']),
                        test_func)
        return cls
    return class_decorator


class FileOwnershipTest(unittest.TestCase):
    """Encapsulate File ownership tests."""

    pass


FileOwnershipTest = _add_tests()(FileOwnershipTest)
