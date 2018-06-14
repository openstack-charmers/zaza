"""Utilities to support running lifecycle phases."""
import importlib
import yaml

BUNDLE_DIR = "./tests/bundles/"
DEFAULT_TEST_CONFIG = "./tests/tests.yaml"


def get_charm_config(yaml_file=None):
    """Read the yaml test config file and return the resulting config.

    :param yaml_file: File to be read
    :type yaml_file: str
    :returns: Config dictionary
    :rtype: dict
    """
    if not yaml_file:
        yaml_file = DEFAULT_TEST_CONFIG
    with open(yaml_file, 'r') as stream:
        return yaml.load(stream)


def get_class(class_str):
    """Get the class represented by the given string.

    For example, get_class('zaza.charms_tests.svc.TestSVCClass1')
    returns zaza.charms_tests.svc.TestSVCClass1

    :param class_str: Class to be returned
    :type class_str: str
    :returns: Test class
    :rtype: class
    """
    module_name = '.'.join(class_str.split('.')[:-1])
    class_name = class_str.split('.')[-1]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)
