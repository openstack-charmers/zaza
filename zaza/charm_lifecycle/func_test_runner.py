import asyncio
import datetime
import logging
import os

import zaza.charm_lifecycle.configure as configure
import zaza.charm_lifecycle.destroy as destroy
import zaza.charm_lifecycle.utils as utils
import zaza.charm_lifecycle.prepare as prepare
import zaza.charm_lifecycle.deploy as deploy
import zaza.charm_lifecycle.test as test


def generate_model_name(charm_name, bundle_name):
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    return '{}{}{}'.format(charm_name, bundle_name, timestamp)


def func_test_runner():
    """Deploy the bundles and run the tests as defined by the charms tests.yaml
    """
    test_config = utils.get_charm_config()
    for t in test_config['gate_bundles']:
        model_name = generate_model_name(test_config['charm_name'], t)
        # Prepare
        prepare.prepare(model_name)
        # Deploy
        deploy.deploy(
            os.path.join(utils.BUNDLE_DIR, '{}.yaml'.format(t)),
            model_name)
        # Configure
        configure.configure(model_name, test_config['configure'])
        # Test
        test.test(model_name, test_config['tests'])
        # Destroy
        destroy.destroy(model_name)


def main():
    logging.basicConfig(level=logging.INFO)
    func_test_runner()
    asyncio.get_event_loop().close()
