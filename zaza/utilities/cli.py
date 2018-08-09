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

"""Module containing utilities for working with commandline tools."""

import logging
import os


def parse_arg(options, arg, multiargs=False):
    """Parse argparse argments.

    :param options: Argparse options
    :type options: argparse object
    :param arg: Argument attribute key
    :type arg: string
    :param multiargs: More than one arugment or not
    :type multiargs: boolean
    :returns: Argparse atrribute value
    :rtype: string
    """
    if arg.upper() in os.environ:
        if multiargs:
            return os.environ[arg.upper()].split()
        else:
            return os.environ[arg.upper()]
    else:
        return getattr(options, arg)


def setup_logging():
    """Do setup for logging.

    :returns: Nothing: This fucntion is executed for its sideffect
    :rtype: None
    """
    logFormatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")
    rootLogger = logging.getLogger()
    rootLogger.setLevel('INFO')
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(consoleHandler)
