import argparse
import logging
import subprocess
import sys


def destroy_model(model_name):
    """Remove a model with the given name

    :param model: Name of model to remove
    :type bundle: str
    """
    logging.info("Remove model {}".format(model_name))
    subprocess.check_call(['juju', 'destroy-model', '--yes', model_name])


def destroy(model_name):
    """Run all steps to cleaup after a test run

    :param model: Name of model to remove
    :type bundle: str
    """
    destroy_model(model_name)


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
    """Cleanup after test run"""
    logging.basicConfig(level=logging.INFO)
    args = parse_args(sys.argv[1:])
    destroy(args.model_name)
