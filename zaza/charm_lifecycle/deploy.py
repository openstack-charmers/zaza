import argparse
import logging
import subprocess
import sys

import juju_wait

import zaza.charm_lifecycle.utils as utils


def deploy_bundle(bundle, model):
    """Deploy the given bundle file in the specified model

    :param bundle: Path to bundle file
    :type bundle: str
    :param model: Name of model to deploy bundle in
    :type model: str
    """
    logging.info("Deploying bundle {}".format(bundle))
    subprocess.check_call(['juju', 'deploy', '-m', model, bundle])


def deploy(bundle, model, wait=True):
    """Run all steps to complete deployment

    :param bundle: Path to bundle file
    :type bundle: str
    :param model: Name of model to deploy bundle in
    :type model: str
    :param wait: Whether to wait until deployment completes
    :type model: bool
    """
    deploy_bundle(bundle, model)
    if wait:
        logging.info("Waiting for environment to settle")
        utils.set_juju_model(model)
        juju_wait.wait()


def parse_args(args):
    """Parse command line arguments

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model',
                        help='Model to deploy to',
                        required=True)
    parser.add_argument('-b', '--bundle',
                        help='Bundle name (excluding file ext)',
                        required=True)
    parser.add_argument('--no-wait', dest='wait',
                        help='Do not wait for deployment to settle',
                        action='store_false')
    parser.set_defaults(wait=True)
    return parser.parse_args(args)


def main():
    """Deploy bundle"""
    logging.basicConfig(level=logging.INFO)
    args = parse_args(sys.argv[1:])
    deploy(args.bundle, args.model, wait=args.wait)
