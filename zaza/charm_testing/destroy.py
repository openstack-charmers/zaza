import argparse
import logging
import subprocess

def destroy_model(model_name):
    """Remove a model with the given name

    :param model: Name of model to remove
    :type bundle: str
    """
    logging.info("Remove model {}".format(model_name))
    subprocess.check_call(['juju', 'destroy-model', '--yes', model_name])

def clean_up(model_name):
    """Run all steps to cleaup after a test run

    :param model: Name of model to remove
    :type bundle: str
    """
    destroy_model(model_name)

def main():
    """Cleanup after test run"""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument('-m','--model-name', help='Name of model to remove',
                        required=True)
    args = parser.parse_args()
    clean_up(args.model_name)
