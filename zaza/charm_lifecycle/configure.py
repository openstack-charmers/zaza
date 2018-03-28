import asyncio
import argparse
import logging
import sys

import zaza.charm_lifecycle.utils as utils


def run_configure_list(functions):
    """Run the configure scripts as defined in the list of test classes in
       series.

    :param functions: List of configure functions functions
    :type tests: ['zaza.charms_tests.svc.setup', ...]
    """
    for func in functions:
        utils.get_class(func)()


def configure(model_name, functions):
    """Run all post-deployment configuration steps

    :param functions: List of configure functions functions
    :type tests: ['zaza.charms_tests.svc.setup', ...]"""
    utils.set_juju_model(model_name)
    run_configure_list(functions)


def parse_args(args):
    """Parse command line arguments

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--configfuncs', nargs='+',
                        help='Space sperated list of config functions',
                        required=False)
    parser.add_argument('-m', '--model-name', help='Name of model to remove',
                        required=True)
    return parser.parse_args(args)


def main():
    """Run the configuration defined by the command line args or if none were
       provided read the configuration functions  from the charms tests.yaml
       config file"""
    logging.basicConfig(level=logging.INFO)
    args = parse_args(sys.argv[1:])
    funcs = args.configfuncs or utils.get_charm_config()['configure']
    configure(args.model_name, funcs)
    asyncio.get_event_loop().close()
