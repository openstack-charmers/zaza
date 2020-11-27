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

import zaza.charm_lifecycle.before_deploy as before_deploy
import zaza.charm_lifecycle.configure as configure
import zaza.charm_lifecycle.destroy as destroy
import zaza.charm_lifecycle.utils as utils
import zaza.charm_lifecycle.prepare as prepare
import zaza.charm_lifecycle.deploy as deploy
import zaza.charm_lifecycle.test as test
import zaza.model
import zaza.utilities.cli as cli_utils
import zaza.utilities.run_report as run_report


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
            unit_log = '/var/log/juju/unit-{}.log'.format(
                unit.replace('/', '-'))
            logging.error("Juju log for {}".format(unit))
            log_output = zaza.model.run_on_unit(
                unit,
                'tail -{} {}'.format(error_lines, unit_log),
                model_name=model_name)['stdout']
            for line in log_output.split('\n'):
                logging.error("    " + line)
        if show_juju_status:
            logging.error(
                yaml.dump(
                    yaml.load(status.to_json()),
                    default_flow_style=False))


def run_env_deployment(env_deployment, keep_model=False, force=False,
                       test_directory=None):
    """Run the environment deployment.

    :param env_deployment: Environment Deploy to execute.
    :type env_deployment: utils.EnvironmentDeploy
    :param keep_model: Whether to destroy models at end of run
    :type keep_model: boolean
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

    force = force or utils.is_config_deploy_forced_for_bundle(
        deployment.bundle)

    for deployment in env_deployment.model_deploys:
        # Before deploy
        before_deploy.before_deploy(
            deployment.model_name,
            before_deploy_steps.get(deployment.model_alias, []),
            test_directory=test_directory)

    try:
        for deployment in env_deployment.model_deploys:
            deploy.deploy(
                os.path.join(
                    utils.get_bundle_dir(),
                    '{}.yaml'.format(deployment.bundle)),
                deployment.model_name,
                model_ctxt=model_aliases,
                force=force,
                test_directory=test_directory)

        # When deploying bundles with cross model relations, hooks may be
        # triggered in already deployedi models so wait for all models to
        # settle.
        for deployment in env_deployment.model_deploys:
            logging.info("Waiting for {} to settle".format(
                deployment.model_name))
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
        raise

    except Exception:
        failure_report(model_aliases)
        raise

    # Destroy
    # Keep the model from the last run if keep_model is true, this is to
    # maintian compat with osci and should change when the zaza collect
    # functions take over from osci for artifact collection.
    if not keep_model:
        for model_name in model_aliases.values():
            destroy.destroy(model_name)
    zaza.model.unset_juju_model_aliases()


def func_test_runner(keep_model=False, smoke=False, dev=False, bundle=None,
                     force=False, test_directory=None):
    """Deploy the bundles and run the tests as defined by the charms tests.yaml.

    :param keep_model: Whether to destroy model at end of run
    :type keep_model: boolean
    :param smoke: Whether to just run smoke test.
    :param dev: Whether to just run dev test.
    :type smoke: boolean
    :type dev: boolean
    :param force: Pass the force parameter if True to the juju deploy command
    :type force: Boolean
    :param test_directory: Set the directory containing tests.yaml and bundles.
    :type test_directory: str
    """
    utils.set_base_test_dir(test_dir=test_directory)
    if bundle:
        if ':' in bundle:
            model_alias, bundle = bundle.split(':')
        else:
            model_alias = utils.DEFAULT_MODEL_ALIAS
        environment_deploys = [
            utils.EnvironmentDeploy(
                'default',
                [utils.ModelDeploy(
                    model_alias.strip(),
                    utils.generate_model_name(),
                    bundle.strip())],
                True)]
    else:
        if smoke:
            bundle_key = 'smoke_bundles'
        elif dev:
            bundle_key = 'dev_bundles'
        else:
            bundle_key = 'gate_bundles'
        environment_deploys = utils.get_environment_deploys(bundle_key)
    last_test = environment_deploys[-1].name

    for env_deployment in environment_deploys:
        preserve_model = False
        if keep_model and last_test == env_deployment.name:
            preserve_model = True
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
    parser.add_argument('--keep-model', dest='keep_model',
                        help='Keep model at the end of the run',
                        action='store_true')
    parser.add_argument('--smoke', dest='smoke',
                        help='Just run smoke test(s)',
                        action='store_true')
    parser.add_argument('--dev', dest='dev',
                        help='Just run dev test(s)',
                        action='store_true')
    parser.add_argument('-b', '--bundle', dest='bundle',
                        help='Override the bundle to be run',
                        required=False)
    parser.add_argument('-f', '--force', dest='force',
                        help='Pass --force to the juju deploy command',
                        action='store_true')
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    cli_utils.add_test_directory_argument(parser)
    parser.set_defaults(keep_model=False,
                        smoke=False,
                        dev=False,
                        loglevel='INFO')
    return parser.parse_args(args)


def main():
    """Execute full test run."""
    args = parse_args(sys.argv[1:])

    cli_utils.setup_logging(log_level=args.loglevel.upper())

    if args.dev and args.smoke:
        raise ValueError('Ambiguous arguments: --smoke and '
                         '--dev cannot be used together')

    if args.dev and args.bundle:
        raise ValueError('Ambiguous arguments: --bundle and '
                         '--dev cannot be used together')

    if args.smoke and args.bundle:
        raise ValueError('Ambiguous arguments: --bundle and '
                         '--smoke cannot be used together')

    if args.force:
        logging.warn("Using the --force argument for 'juju deploy'. Note "
                     "that this disables juju checks for compatibility.")

    func_test_runner(
        keep_model=args.keep_model,
        smoke=args.smoke,
        dev=args.dev,
        bundle=args.bundle,
        force=args.force,
        test_directory=args.test_directory)
    run_report.output_event_report()
    asyncio.get_event_loop().close()
