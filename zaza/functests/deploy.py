import argparse
import datetime
import importlib
import logging
import os
import subprocess
import sys
import unittest
import yaml

import juju_wait

BUNDLE_DIR = "./tests/bundles/"
DEFAULT_TEST_CONFIG = "./tests/tests.yaml"

def deploy_bundle(bundle, model):
    """Deploy the given bundle file in the specified model

    :param bundle: str Path to bundle file
    :param model: str Name of model to deploy bundle in
    """
    logging.info("Deploying bundle {}".format(bundle))
    subprocess.check_call(['juju', 'deploy', '-m', model, bundle])

def add_model(model_name):
    """Add a model with the given name

    :param model: str Name of model to add
    """
    logging.info("Adding model {}".format(model_name))
    subprocess.check_call(['juju', 'add-model', model_name])

def get_test_class(class_str):
    """Get the test class represented by the given string

    :param class_str: str Class to be returned
    """
    test_module_name = '.'.join(class_str.split('.')[:-1])
    test_class_name = class_str.split('.')[-1]
    test_module = importlib.import_module(test_module_name)
    return getattr(test_module, test_class_name)

def run_test_list(tests):
    """Run the tests as defined in the list of test classes in series.

    :param tests: [TestClass1, TestClass2, ...] List of tests classes to run
    """
    for _testcase in tests:
        testcase = get_test_class(_testcase)
        suite = unittest.TestLoader().loadTestsFromTestCase(testcase)
        test_result = unittest.TextTestRunner(verbosity=2).run(suite)
        assert test_result.wasSuccessful(), "Test run failed"

def deploy():
    """Deploy the bundles and run the tests as defined by the charms tests.yaml

    """
    test_config = get_test_config()
    for t in test_config['gate_bundles']:
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        model_name = '{}{}{}'.format(test_config['charm_name'], t, timestamp)
        add_model(model_name)
        deploy_bundle(
            os.path.join(BUNDLE_DIR, '{}.yaml'.format(t)),
            model_name)
        logging.info("Waiting for environment to settle")
        juju_wait.wait()
        run_test_list(test_config['tests'])

def get_test_config():
    """Read the yaml test config file and return the resulting config

    """
    with open(DEFAULT_TEST_CONFIG, 'r') as stream:
        return yaml.load(stream)

def run_tests():
    """Run the tests defined by the command line args or if none were provided
       read the tests from the charms tests.yaml config file"""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument('-t','--tests', nargs='+',
                        help='Space sperated list of test classes',
                        required=False)
    args = parser.parse_args()
    tests = args.tests or get_test_config()['tests']
    run_test_list(tests)
