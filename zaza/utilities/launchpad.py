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
import logging
import os
import requests
import typing
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


def get_ubuntu_series(
) -> typing.Dict[str, typing.List[typing.Dict[str, any]]]:
    """Contact Launchpad API and retrieve a list of all Ubuntu releases.

    Launchpad documentation for the returned data structure can be found here:
    https://launchpad.net/+apidoc/devel.html#distribution
    https://launchpad.net/+apidoc/devel.html#distro_series
    """
    retries = Retry(
        total=10,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    s = requests.Session()

    proxies = {}
    for ptype in ['http', 'https']:
        proxies[ptype] = os.environ.get(f"TEST_{ptype.upper()}_PROXY")

    proxies['no_proxy'] = os.environ.get('TEST_NO_PROXY')
    logging.info(f"using proxies: {proxies}")
    s.proxies.update(proxies)
    s.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        r = s.get('https://api.launchpad.net/devel/ubuntu/series')
        r.raise_for_status()
        return json.loads(r.text)
    finally:
        s.close()


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
