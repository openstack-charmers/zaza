#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
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
from pathlib import Path

import zaza.model as model
import subprocess


class CharmRefreshAll:
    """Perform upgrades of all charms in a local file path."""

    test_runner = 'direct_with_args'

    def run(self, *args, **kwargs):
        """Upgrade all the charms found in a local path."""
        path = os.environ.get('CHARMS_ARTIFACT_DIR')
        if not path:
            logging.info('CHARMS_ARTIFACT_DIR not set; skipping charm refresh')
            return True

        path = Path(path).resolve()
        charms = list(path.glob('*.charm'))
        if not charms:
            logging.info('no charms found in path: %s' % str(path))
            return True

        for charm in charms:
            app_name = charm.stem
            try:
                model.get_application(app_name)
            except KeyError:
                logging.info('charm %s not found in current model' % app_name)
                continue

            logging.info('refreshing charm %s' % app_name)
            subprocess.check_call([
                'juju', 'refresh', '--path', str(charm), app_name
            ])

        return True
