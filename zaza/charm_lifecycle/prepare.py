"""Run prepare phase."""
import argparse
import logging
import sys

import zaza.model

MODEL_DEFAULTS = {
    # Model defaults from charm-test-infra
    #   https://jujucharms.com/docs/2.1/models-config
    'agent-stream': 'proposed',
    'default-series': 'xenial',
    'image-stream': 'daily',
    'test-mode': 'true',
    'transmit-vendor-metrics': 'false',
    # https://bugs.launchpad.net/juju/+bug/1685351
    # enable-os-refresh-update: false
    'enable-os-upgrade': 'false',
    'automatically-retry-hooks': 'false',
    'use-default-secgroup': 'true',
}


def prepare(model_name):
    """Run all steps to prepare the environment before a functional test run.

    :param model: Name of model to add
    :type bundle: str
    """
    zaza.model.add_model(model_name, config=MODEL_DEFAULTS)


def parse_args(args):
    """Parse command line arguments.

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model-name', help='Name of model to add',
                        required=True)
    return parser.parse_args(args)


def main():
    """Add a new model."""
    logging.basicConfig(level=logging.INFO)
    args = parse_args(sys.argv[1:])
    prepare(args.model_name)
