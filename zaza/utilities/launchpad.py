# Copyright 2023 Canonical Ltd.
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
"""Module for interacting with Launchpad API."""

import json
import requests
import typing


def get_ubuntu_series(
) -> typing.Dict[str, typing.List[typing.Dict[str, any]]]:
    """Contact Launchpad API and retrieve a list of all Ubuntu releases.

    Launchpad documentation for the returned data structure can be found here:
    https://launchpad.net/+apidoc/devel.html#distribution
    https://launchpad.net/+apidoc/devel.html#distro_series
    """
    r = requests.get('https://api.launchpad.net/devel/ubuntu/series')
    return json.loads(r.text)


def get_ubuntu_series_by_version() -> typing.Dict[str, typing.Dict[str, any]]:
    """Get a Dict of distro series information indexed by version number.

    Please refer to the `get_ubuntu_series()` function docstring for docs.
    """
    return {
        entry['version']: entry
        for entry in get_ubuntu_series().get('entries', {})
    }


def get_ubuntu_series_by_name() -> typing.Dict[str, typing.Dict[str, any]]:
    """Get a Dict of distro series information indexed by version name.

    Please refer to the `get_ubuntu_series()` function docstring for docs.
    """
    return {
        entry['name']: entry
        for entry in get_ubuntu_series().get('entries', {})
    }
