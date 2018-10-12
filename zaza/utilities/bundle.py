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
"""Module for disfiguring Juju bundles."""


import argparse
import yaml
import sys


def remove_machine_specification(input_yaml):
    """
    Will remove the machine specifications from a supplied bundle.

    :param input_yaml: Juju bundle to strip machinens from
    :type input_yaml: dict
    :returns: bundle without machine placements
    :rtype: dict
    """
    machines = input_yaml.pop("machines", None)

    input_series = input_yaml.get('series', None)
    if machines:
        for (name, details) in machines.items():
            if details['series']:
                if input_series and details['series'] != input_series:
                    raise Exception("Mixing series is not supported")
                input_yaml['series'] = details['series']
                input_series = input_yaml['series']

    for (application_name, application) in input_yaml['services'].items():
        application.pop("to", None)
    return input_yaml


def parse_args(args):
    """Parse command line arguments.

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input',
                        help='Bundle to remove placement from',
                        required=True)
    parser.add_argument('-o', '--output',
                        help='Where to output',
                        default="/dev/stdout")
    return parser.parse_args(args)


def main():
    """Run the configuration defined by the command line args.

    Remove machine placement as specified in the command line args
    """
    args = parse_args(sys.argv[1:])
    with open(args.input, 'r') as file:
        input_yaml = yaml.safe_load(file)
    stripped_yaml = remove_machine_specification(input_yaml)
    with open(args.output, 'w') as output:
        print(yaml.dump(stripped_yaml), file=output)
