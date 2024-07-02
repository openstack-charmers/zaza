#!/usr/bin/env python3

# Copyright 2022 Canonical Ltd.
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

"""Code for managing various lifecycle functionality via Zaza."""

import logging
import os

import subprocess


class UpgradeCharmsToPath(object):
    """Perform charm upgrades to a local file path."""

    test_runner = 'direct_with_args'

    def run(self, charms):
        """
        Upgrade the named charm(s) to a locally defined "name.charm" file.

        :param charms: List of charms to upgrade
        :type charms: List[str]
        :returns: Status of charm upgrade test
        :rtype: bool
        """
        logging.info("Performing a charm upgrade on: %s", charms)
        cwd = os.getcwd()
        for charm in charms:
            charm_path = cwd + '/' + charm + '.charm'
            logging.debug("Upgrading %s to %s", charm, charm_path)
            subprocess.check_call([
                'juju', 'refresh',
                '--path', str(charm_path),
                str(charm)
            ])
        return True
