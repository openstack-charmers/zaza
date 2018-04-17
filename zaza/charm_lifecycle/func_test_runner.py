import argparse
import asyncio
import datetime
import logging
import os
import sys

import zaza.charm_lifecycle.configure as configure
import zaza.charm_lifecycle.destroy as destroy
import zaza.charm_lifecycle.utils as utils
import zaza.charm_lifecycle.prepare as prepare
import zaza.charm_lifecycle.deploy as deploy
import zaza.charm_lifecycle.test as test


def generate_model_name(charm_name, bundle_name):
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    return '{}{}{}'.format(charm_name, bundle_name, timestamp)


def func_test_runner(keep_model=False, smoke=False, destroy_model=True,
                     deploy_model=True):
    """Deploy the bundles and run the tests as defined by the charms tests.yaml

    :param keep_model: Whether to destroy model at end of run
    :type keep_model: boolean
    :param smoke: Whether to just run smoke test.
    :type smoke: boolean
    """
    test_config = utils.get_charm_config()
    if smoke:
        bundle_key = 'smoke_bundles'
    else:
        bundle_key = 'gate_bundles'
    bundles = test_config[bundle_key]
    last_test = bundles[-1]
    for t in bundles:
        if destroy_model:
            model_name = generate_model_name(test_config['charm_name'], t)
            # Prepare
            prepare.prepare(model_name)
        else:
            model_name = utils.get_juju_model()
        if deploy_model:
            # Deploy
            deploy.deploy(
                os.path.join(utils.BUNDLE_DIR, '{}.yaml'.format(t)),
                model_name)
        # Configure
        configure.configure(model_name, test_config['configure'])
        # Test
        test.test(model_name, test_config['tests'])
        # Destroy
        # Keep the model from the last run if keep_model is true, this is to
        # maintian compat with osci and should change when the zaza collect
        # functions take over from osci for artifact collection.
        if keep_model and t == last_test:
            pass
        else:
            destroy.destroy(model_name)


def parse_args(args):
    """Parse command line arguments

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--keep-model', dest='keep_model',
                        help='Keep model at the end of the run',
                        action='store_true')
    parser.add_argument('--smoke', dest='smoke',
                        help='Just run smoke test',
                        action='store_true')
    parser.add_argument('--no-destroy',
                        dest='destroy_model',
                        help=('Do not destroy existing model '
                              'before test run.'
                              'For use during development'),
                        action='store_false')
    parser.add_argument('--no-deploy',
                        dest='deploy_model',
                        help=('Do not deploy model before test run. '
                              'For use during development.'),
                        action='store_false')
    parser.set_defaults(keep_model=False, smoke=False,
                        destroy_model=True, deploy_model=True)
    return parser.parse_args(args)


def main():
    logging.basicConfig(level=logging.INFO)
    args = parse_args(sys.argv[1:])
    func_test_runner(keep_model=args.keep_model, smoke=args.smoke,
                     destroy_model=args.destroy_model,
                     deploy_model=args.deploy_model)
    asyncio.get_event_loop().close()
