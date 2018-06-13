import argparse
import logging
import sys

import zaza.controller


def destroy(model_name):
    """Run all steps to cleaup after a test run

    :param model: Name of model to remove
    :type bundle: str
    """
    zaza.controller.destroy_model(model_name)


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
