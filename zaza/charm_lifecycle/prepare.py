import argparse
import logging
import subprocess
import sys


MODEL_DEFAULTS = [
    # Model defaults from charm-test-infra
    #   https://jujucharms.com/docs/2.1/models-config
    '--config', 'agent-stream=proposed',
    '--config', 'default-series=xenial',
    '--config', 'image-stream=daily',
    '--config', 'test-mode=true',
    '--config', 'transmit-vendor-metrics=false',
    # https://bugs.launchpad.net/juju/+bug/1685351
    # enable-os-refresh-update: false
    '--config', 'enable-os-upgrade=false',
    '--config', 'automatically-retry-hooks=false',
    '--config', 'use-default-secgroup=true',
]


def add_model(model_name):
    """Add a model with the given name

    :param model: Name of model to add
    :type bundle: str
    """
    logging.info("Adding model {}".format(model_name))
    subprocess.check_call(['juju', 'add-model', model_name] + MODEL_DEFAULTS)


def prepare(model_name):
    """Run all steps to prepare the environment before a functional test run

    :param model: Name of model to add
    :type bundle: str
    """
    add_model(model_name)


def parse_args(args):
    """Parse command line arguments

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model-name', help='Name of model to remove',
                        required=True)
    return parser.parse_args(args)


def main():
    """Add a new model"""
    logging.basicConfig(level=logging.INFO)
    args = parse_args(sys.argv[1:])
    prepare(args.model_name)
