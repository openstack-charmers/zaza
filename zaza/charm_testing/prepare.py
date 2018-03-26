import argparse
import logging
import subprocess


def add_model(model_name):
    """Add a model with the given name

    :param model: Name of model to add
    :type bundle: str
    """
    logging.info("Adding model {}".format(model_name))
    subprocess.check_call(['juju', 'add-model', model_name])


def prepare(model_name):
    """Run all steps to prepare the environment before a functional test run

    :param model: Name of model to add
    :type bundle: str
    """
    add_model(model_name)


def main():
    """Add a new model"""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model-name', help='Name of new model',
                        required=True)
    args = parser.parse_args()
    prepare(args.model_name)
