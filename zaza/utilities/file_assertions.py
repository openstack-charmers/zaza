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

"""Module of helpers for Zaza file assertions."""

import zaza.model as model


def assert_path_glob(test_case, unit, file_details, paths=[]):
    """Verify all files in a given directory."""
    result = model.run_on_unit(
        unit, 'bash -c "'
        'shopt -s -q globstar; '
        'stat -c "%n %U %G %a" {}"'.format(file_details['path']))
    files = result['Stdout']
    for file in files.splitlines():
        file, owner, group, mode = file.split()
        if file not in paths and file not in ['.', '..']:
            verify_file(test_case,
                        unit,
                        file_details,
                        owner,
                        group,
                        mode,
                        path=file)


def assert_single_file(test_case, unit, file_details):
    """Verify ownership of a single file."""
    result = model.run_on_unit(
        unit, 'stat -c "%U %G %a" {}'.format(file_details['path']))
    ownership = result['Stdout']
    owner, group, mode = ownership.split()
    verify_file(test_case, unit, file_details, owner, group, mode)


def verify_file(test_case, unit, file_details,
                actual_owner, actual_group, actual_mode, path=None):
    """Assert file has correct permissions."""
    expected_owner = file_details.get("owner", "root")
    expected_group = file_details.get("group", "root")
    expected_mode = file_details.get("mode", "600")
    test_case.assertEqual(expected_owner,
                          actual_owner,
                          _error_message("Owner", unit, actual_owner, path))
    test_case.assertEqual(expected_group,
                          actual_group,
                          _error_message("Group", unit, actual_group, path))
    test_case.assertEqual(expected_mode,
                          actual_mode,
                          _error_message("Mode", unit, actual_mode, path))


def _error_message(thing, unit, value, path=None):
    if path:
        return "{} is incorrect for {} on {}: {}".format(
            thing, path, unit, value)
    else:
        return "{} is incorrect on {}: {}".format(thing, unit, value)
