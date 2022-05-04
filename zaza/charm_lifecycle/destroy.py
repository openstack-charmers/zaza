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

"""Run destroy phase."""
import argparse
import sys

import zaza.controller
import zaza.utilities.cli as cli_utils
import zaza.utilities.juju as juju_utils
import zaza.model as model


def destroy(model_name):
    """Run all steps to cleaup after a test run.

    Note: on the OpenStack provider we also verify after the destroy model call
    that the instances associated with the model really are gone.  Reap any
    instances that have the model name in them before returning.
    Bug: https://bugs.launchpad.net/juju/+bug/1913418

    :param model: Name of model to remove
    :type bundle: str
    """
    machines = model.get_status()["machines"]
    zaza.controller.destroy_model(model_name)
    if juju_utils.get_provider_type() == "openstack":
        # only import openstack_provider if it's needed.  This avoids forcing
        # zaza to have dependencies for providers that the user isn't using.
        import zaza.utilities.openstack_provider as op
        op.clean_up_instances(model_name, machines)


def parse_args(args):
    """Parse command line arguments.

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model-name', help='Name of model to remove',
                        required=True)
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    parser.set_defaults(loglevel='INFO')
    return parser.parse_args(args)


def main():
    """Cleanup after test run."""
    args = parse_args(sys.argv[1:])
    cli_utils.setup_logging(log_level=args.loglevel.upper())
    destroy(args.model_name)
    zaza.clean_up_libjuju_thread()
