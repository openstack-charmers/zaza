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

"""Run an arbitrary module with parameters.

The function allows the caller to specify a specific module to call and pass
arguments to.

The module is specified as a dotted list of valid python modules with the last
one being the function to call in that module. e.g.

    mod1.mod2.mod3.function
"""
import argparse
import asyncio
import logging
import sys

import zaza
import zaza.utilities.cli as cli_utils
import zaza.charm_lifecycle.utils as utils


def parse_args(args):
    """Parse command line arguments.

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Tuple[Namespace, List[str]]
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('module',
                        help=('The module to run.'))
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    parser.set_defaults(loglevel='INFO')
    return parser.parse_known_args(args)


def main():
    """Execute full test run."""
    # known_args are the remaining args to pass to the module function that is
    # being run.
    args, known_args  = parse_args(sys.argv[1:])

    cli_utils.setup_logging(log_level=args.loglevel.upper())

    # now find the module, load it, and then pass control to it.
    function = None
    try:
        function = utils.load_module_and_getattr(args.module)
    except AttributeError:
        logging.error("Couldn't find function %s", args.module)
    if function is not None:
        try:
            function(known_args)
        finally:
            zaza.clean_up_libjuju_thread()
            asyncio.get_event_loop().close()
