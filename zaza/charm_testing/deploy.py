import argparse
import logging
import subprocess
import sys

import juju_wait


def deploy_bundle(bundle, model, wait=True):
    """Deploy the given bundle file in the specified model

    :param bundle: Path to bundle file
    :type bundle: str
    :param model: Name of model to deploy bundle in
    :type model: str
    """
    logging.info("Deploying bundle {}".format(bundle))
    subprocess.check_call(['juju', 'deploy', '-m', model, bundle])
    if wait:
        logging.info("Waiting for environment to settle")
        juju_wait.wait()


def main():
    """Deploy bundle"""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument('-m','--model',
                        help='Model to deploy to',
                        required=True)
    parser.add_argument('-b','--bundle',
                        help='Bundle name (excluding file ext)',
                        required=True)
    parser.add_argument('--no-wait', dest='wait',
                        help='Do not wait for deployment to settle',
                        action='store_false')
    parser.set_defaults(wait=True)
    args = parser.parse_args()
    deploy_bundle(args.bundle, args.model, wait=args.wait)
