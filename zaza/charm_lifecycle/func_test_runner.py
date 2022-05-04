# Copyright 2020 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Run full test lifecycle."""
import argparse
import asyncio
import logging
import os
import sys
import yaml

import zaza
import zaza.charm_lifecycle.before_deploy as before_deploy
import zaza.charm_lifecycle.configure as configure
import zaza.charm_lifecycle.destroy as destroy
import zaza.charm_lifecycle.utils as utils
import zaza.charm_lifecycle.prepare as prepare
import zaza.charm_lifecycle.deploy as deploy
import zaza.charm_lifecycle.test as test
import zaza.model
from zaza.notifications import notify_around, NotifyEvents
import zaza.plugins
import zaza.utilities.cli as cli_utils
import zaza.utilities.run_report as run_report

# Default: destroy any model after being used
DESTROY_MODEL = 0
# Do not destroy a model, for different reasons:
#   - want to keep all models
#   - want to keep the last model, tests being successful or not
KEEP_MODEL = 1
# Do not destroy a model with failed tests (which is the last one
# to run, but may not be the last one in the list of bundles to test)
KEEP_FAULTY_MODEL = 2


def failure_report(model_aliases, show_juju_status=False):
    """Report on apps and units in an error state.

    :param model_aliases: Map of aliases to model names.
    :type model_aliases: Dict
    :param show_juju_status: Whether include juju status in the summary.
    :type show_juju_status: bool
    """
    logging.error(model_aliases)
    error_lines = 20
    for model_alias, model_name in model_aliases.items():
        logging.error("Model {} ({})".format(model_alias, model_name))
        status = zaza.model.get_status(model_name=model_name)
        erred_apps = []
        for app in status.applications:
            if status.applications[app].status.status == 'error':
                erred_apps.append(app)
        erred_units = []
        for app in erred_apps:
            for uname, ustatus in status.applications[app].units.items():
                if ustatus.workload_status.status == 'error':
                    erred_units.append(uname)
        if erred_apps:
            logging.error("Applications in error state: {}".format(
                ','.join(erred_apps)))
        if erred_units:
            logging.error("Units in error state: {}".format(
                ','.join(erred_units)))
        for unit in erred_units:
            # libjuju has not implemented debug_log yet so get the log
            # from the unit.
            # https://github.com/juju/python-libjuju/issues/447
            unit_log = 'unit-{}.log'.format(unit.replace('/', '-'))
            logging.error("Juju log for {}".format(unit))
            log_output = zaza.model.run_on_unit(
                unit,
                'tail -{} {}'.format(
                    error_lines,
                    os.path.join('/var/log/juju', unit_log)),
                model_name=model_name)['stdout']
            for line in log_output.split('\n'):
                logging.error('{}: {}'.format(unit_log, line))
        if show_juju_status:
            logging.error(
                yaml.dump(
                    yaml.safe_load(status.to_json()),
                    default_flow_style=False))


def run_env_deployment(env_deployment, keep_model=DESTROY_MODEL, force=False,
                       test_directory=None):
    """Run the environment deployment.

    :param env_deployment: Environment Deploy to execute.
    :type env_deployment: utils.EnvironmentDeploy
    :param keep_model: Whether to destroy model at end of run
    :type keep_model: int
    :param force: Pass the force parameter if True
    :type force: Boolean
    :param test_directory: Set the directory containing tests.yaml and bundles.
    :type test_directory: str
    """
    config_steps = utils.get_config_steps()
    test_steps = utils.get_test_steps()
    before_deploy_steps = utils.get_before_deploy_steps()

    model_aliases = {model_deploy.model_alias: model_deploy.model_name
                     for model_deploy in env_deployment.model_deploys}
    zaza.model.set_juju_model_aliases(model_aliases)

    for deployment in env_deployment.model_deploys:
        prepare.prepare(
            deployment.model_name,
            test_directory=test_directory)

    for deployment in env_deployment.model_deploys:
        # Before deploy
        before_deploy.before_deploy(
            deployment.model_name,
            before_deploy_steps.get(deployment.model_alias, []),
            test_directory=test_directory)

    try:
        for deployment in env_deployment.model_deploys:
            force_ = force or utils.is_config_deploy_forced_for_bundle(
                deployment.bundle)

            deploy.deploy(
                os.path.join(
                    utils.get_bundle_dir(),
                    '{}.yaml'.format(deployment.bundle)),
                deployment.model_name,
                model_ctxt=model_aliases,
                force=force_,
                test_directory=test_directory)

        # When deploying bundles with cross model relations, hooks may be
        # triggered in already deployedi models so wait for all models to
        # settle.
        for deployment in env_deployment.model_deploys:
            logging.info("Waiting for {} to settle".format(
                deployment.model_name))
            with notify_around(NotifyEvents.WAIT_MODEL_SETTLE,
                               model_name=deployment.model_name):
                zaza.model.block_until_all_units_idle(
                    model_name=deployment.model_name)

        for deployment in env_deployment.model_deploys:
            configure.configure(
                deployment.model_name,
                config_steps.get(deployment.model_alias, []),
                test_directory=test_directory)

        for deployment in env_deployment.model_deploys:
            test.test(
                deployment.model_name,
                test_steps.get(deployment.model_alias, []),
                test_directory=test_directory)

    except zaza.model.ModelTimeout:
        failure_report(model_aliases, show_juju_status=True)
        # Destroy models that were not healthy before TEST_DEPLOY_TIMEOUT
        # was reached (default: 3600s)
        if keep_model == DESTROY_MODEL:
            destroy_models(model_aliases, destroy)
        raise
    except Exception:
        failure_report(model_aliases)
        # Destroy models that raised any other exception.
        # Note(aluria): KeyboardInterrupt will be raised on underlying libs,
        # and other signals (e.g. SIGTERM) will also miss this handler
        # In those cases, models will have to be manually destroyed
        if keep_model == DESTROY_MODEL:
            destroy_models(model_aliases, destroy)
        raise

    # Destroy successful models if --keep-model is not defined
    if keep_model in [DESTROY_MODEL, KEEP_FAULTY_MODEL]:
        destroy_models(model_aliases, destroy)


def destroy_models(model_aliases, destroy):
    """Destroy models created during integration tests."""
    # Destroy
    # Keep the model from the last run if keep_model is true, this is to
    # maintain compat with osci and should change when the zaza collect
    # functions take over from osci for artifact collection.
    for model_name in model_aliases.values():
        destroy.destroy(model_name)
    zaza.model.unset_juju_model_aliases()


def func_test_runner(keep_last_model=False, keep_all_models=False,
                     keep_faulty_model=False, smoke=False, dev=False,
                     bundles=None, force=False, test_directory=None):
    """Deploy the bundles and run the tests as defined by the charms tests.yaml.

    :param keep_last_model: Whether to destroy last model at end of run
    :type keep_last_model: boolean
    :param keep_all_models: Whether to keep all models at end of run
    :type keep_all_models: boolean
    :param keep_faulty_model: Whether to destroy a model when tests failed
    :param smoke: Whether to just run smoke test.
    :param dev: Whether to just run dev test.
    :type smoke: boolean
    :type dev: boolean
    :param bundles: Bundles is a list of specific bundles to run, in the format
                    ['bundle_name', 'model_alias:bundle2_name']. If a model
                    alias isn't provided for a bundle, this will attempt to
                    infer the correct model alias by reading through the
                    tests.yaml config file for a matching bundle name. If, and
                    only if, it finds a single matching bundle name, it will
                    use that alias as the model alias, otherwise it will fall
                    back to the default model alias.
    :type bundles: [str1, str2,...]
    :param force: Pass the force parameter if True to the juju deploy command
    :type force: Boolean
    :param test_directory: Set the directory containing tests.yaml and bundles.
    :type test_directory: str
    """
    utils.set_base_test_dir(test_dir=test_directory)
    if bundles is not None:
        all_bundles = None
        if not isinstance(bundles, list):
            bundles = [bundles]
        deploy = {}
        environment_deploys = []
        for bundle in bundles:
            if ':' in bundle:
                model_alias, bundle = bundle.split(':')
            else:
                if all_bundles is None:
                    all_bundles = {}
                    for name, values in utils.get_charm_config().items():
                        if '_bundles' in name:
                            all_bundles[name] = values
                matching_bundles = set()
                for _name, bundles in all_bundles.items():
                    if bundles:
                        for tests_bundle in bundles:
                            if isinstance(tests_bundle, dict):
                                for alias, tests_bundle in \
                                        tests_bundle.items():
                                    if tests_bundle == bundle:
                                        matching_bundles.add(alias)
                if len(set(matching_bundles)) == 1:
                    model_alias = matching_bundles.pop()
                else:
                    logging.info('Could not determine correct model alias'
                                 'from tests.yaml, using default')
                    model_alias = utils.DEFAULT_MODEL_ALIAS
            deploy[model_alias] = bundle
        environment_deploys.append(
            utils.get_environment_deploy(deploy)
        )
    else:
        if smoke:
            bundle_key = 'smoke_bundles'
        elif dev:
            bundle_key = 'dev_bundles'
        else:
            bundle_key = 'gate_bundles'
        environment_deploys = utils.get_environment_deploys(bundle_key)

    # Now inform any plugins of the environment deploys.
    zaza.plugins.find_and_configure_plugins(environment_deploys)

    # Now run the deploys
    last_test = environment_deploys[-1].name
    for env_deployment in environment_deploys:
        preserve_model = DESTROY_MODEL
        if (
            (keep_last_model and last_test == env_deployment.name) or
            keep_all_models
        ):
            preserve_model = KEEP_MODEL
        elif keep_faulty_model:
            preserve_model = KEEP_FAULTY_MODEL

        with notify_around(NotifyEvents.BUNDLE, env_deployment=env_deployment):
            run_env_deployment(env_deployment, keep_model=preserve_model,
                               force=force, test_directory=test_directory)


def parse_args(args):
    """Parse command line arguments.

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--keep-model', '--keep-last-model',
                        dest='keep_last_model',
                        help=('Keep last model at the end of the run '
                              '(successful or not)'),
                        action='store_true')
    parser.add_argument('--keep-all-models', dest='keep_all_models',
                        help=('Keep all models at the end of their run '
                              '(successful or not)'),
                        action='store_true')
    parser.add_argument('--keep-faulty-model', dest='keep_faulty_model',
                        help=('Keep last model at the end of the run '
                              '(if not successful)'),
                        action='store_true')
    parser.add_argument('--smoke', dest='smoke',
                        help='Just run smoke test(s)',
                        action='store_true')
    parser.add_argument('--dev', dest='dev',
                        help='Just run dev test(s)',
                        action='store_true')
    parser.add_argument('-b', '--bundle', dest='bundles',
                        help='Override the bundle(s) to be run. If a specific'
                             ' model alias is desired, it can be added to the'
                             ' bundle argument in the format'
                             ' alias:bundle-name. Additionally, if a model'
                             ' alias is not explicitly chosen, then Zaza will'
                             ' attempt to match the bundle name with a single'
                             ' bundle name in the tests.yaml',
                        required=False,
                        nargs='+')
    parser.add_argument('-f', '--force', dest='force',
                        help='Pass --force to the juju deploy command',
                        action='store_true')
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    cli_utils.add_test_directory_argument(parser)
    parser.set_defaults(keep_last_model=False,
                        keep_all_models=False,
                        keep_faulty_model=False,
                        smoke=False,
                        dev=False,
                        loglevel='INFO')
    return parser.parse_args(args)


def main():
    """Execute full test run."""
    args = parse_args(sys.argv[1:])

    cli_utils.setup_logging(log_level=args.loglevel.upper())

    if (
        (args.keep_last_model and args.keep_all_models) or
        (args.keep_last_model and args.keep_faulty_model) or
        (args.keep_all_models and args.keep_faulty_model)
    ):
        raise ValueError('Ambiguous arguments: --keep-last-model '
                         '(previously, --keep-model), --keep-all-models '
                         'and --keep-faulty-model cannot be used together')

    if args.dev and args.smoke:
        raise ValueError('Ambiguous arguments: --smoke and '
                         '--dev cannot be used together')

    if args.dev and args.bundles:
        raise ValueError('Ambiguous arguments: --bundle and '
                         '--dev cannot be used together')

    if args.smoke and args.bundles:
        raise ValueError('Ambiguous arguments: --bundle and '
                         '--smoke cannot be used together')

    if args.force:
        logging.warn("Using the --force argument for 'juju deploy'. Note "
                     "that this disables juju checks for compatibility.")
    func_test_runner(
        keep_last_model=args.keep_last_model,
        keep_all_models=args.keep_all_models,
        keep_faulty_model=args.keep_faulty_model,
        smoke=args.smoke,
        dev=args.dev,
        bundles=args.bundles,
        force=args.force,
        test_directory=args.test_directory)
    run_report.output_event_report()
    zaza.clean_up_libjuju_thread()
    asyncio.get_event_loop().close()
