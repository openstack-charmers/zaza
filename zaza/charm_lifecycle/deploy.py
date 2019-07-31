# Copyright 2018 Canonical Ltd.
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

"""Run deploy phase."""
import argparse
import jinja2
import logging
import os
import sys
import tempfile
import yaml

import zaza.model
import zaza.charm_lifecycle.utils as utils
import zaza.utilities.cli as cli_utils
import zaza.utilities.run_report as run_report

DEFAULT_OVERLAY_TEMPLATE_DIR = 'tests/bundles/overlays'
VALID_ENVIRONMENT_KEY_PREFIXES = [
    'FIP_RANGE',
    'GATEWAY',
    'NAME_SERVER',
    'NET_ID',
    'OS_',
    'VIP_RANGE',
    'AMULET_',
    'MOJO_',
    'JUJU_',
    'CHARM_',
]
LOCAL_OVERLAY_TEMPLATE = """
applications:
  {{ charm_name }}:
    charm: {{ charm_location }}
"""
LOCAL_OVERLAY_TEMPLATE_NAME = 'local-charm-overlay.yaml'
LOCAL_OVERLAY_ENABLED_KEY = 'local_overlay_enabled'


def is_valid_env_key(key):
    """Check if key is a valid environment variable name for use with template.

    :param key: List of configure functions functions
    :type key: str
    :returns: Whether key is a valid environment variable name
    :rtype: bool
    """
    valid = False
    for _k in VALID_ENVIRONMENT_KEY_PREFIXES:
        if key.startswith(_k):
            valid = True
            break
    return valid


def get_template_context_from_env():
    """Return environment vars from the current env for template rendering.

    :returns: Environment variable key values for use with template rendering
    :rtype: dict
    """
    return {k: v for k, v in os.environ.items() if is_valid_env_key(k)}


def get_charm_config_context():
    """Return settings from charm config file.

    :returns: Context for template rendering
    :rtype: dict
    """
    test_config = utils.get_charm_config()
    ctxt = {
        'charm_name': test_config['charm_name'],
        'charm_location': '../../../{}'.format(test_config['charm_name'])}
    return ctxt


def get_template_overlay_context():
    """Combine contexts which can be used for overlay template rendering.

    :returns: Context for template rendering
    :rtype: dict
    """
    context = {}
    contexts = [
        get_template_context_from_env(),
    ]
    try:
        contexts.append(get_charm_config_context())
    except KeyError:
        pass

    for c in contexts:
        context.update(c)
    return context


def get_overlay_template_dir():
    """Return the directory to look for overlay template files in.

    :returns: Overlay template file dir
    :rtype: str
    """
    return DEFAULT_OVERLAY_TEMPLATE_DIR


def get_jinja2_env():
    """Return a jinja2 environment that can be used to render templates from.

    :returns: Jinja2 template loader
    :rtype: jinja2.Environment
    """
    template_dir = get_overlay_template_dir()
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        undefined=jinja2.StrictUndefined
    )


def get_template_name(target_file):
    """Return the template name for target_file.

    Return the expected name of the template used to generate the
    target_file

    :param target_file: File to be rendered
    :type target_file: str
    :returns: Name of template used to render target_file
    :rtype: str
    """
    return '{}.j2'.format(os.path.basename(target_file))


def get_template(target_file):
    """Return the jinja2 template for the given file.

    :returns: Template object used to generate target_file
    :rtype: jinja2.Template
    """
    jinja2_env = get_jinja2_env()
    try:
        template = jinja2_env.get_template(get_template_name(target_file))
    except jinja2.exceptions.TemplateNotFound:
        template = None
    return template


def render_template(template, target_file):
    """Render the template to the file supplied.

    :param template: Template to be rendered
    :type template: jinja2.Template
    :param target_file: File name for rendered template
    :type target_file: str
    """
    try:
        with open(target_file, "w") as fh:
            fh.write(
                template.render(get_template_overlay_context()))
    except jinja2.exceptions.UndefinedError as e:
        logging.error("Template error. You may be missing"
                      " a mandatory environment variable : {}".format(e))
        sys.exit(1)
    logging.info("Rendered template '{}' to file '{}'".format(template,
                                                              target_file))


def render_overlay(overlay_name, target_dir):
    """Render the overlay template in the directory supplied.

    :param overlay_name: Name of overlay to be rendered
    :type overlay_name: str
    :param target_dir: Directory to render overlay in
    :type overlay_name: str
    :returns: Path to rendered overlay
    :rtype: str
    """
    template = get_template(overlay_name)
    if not template:
        return
    rendered_template_file = os.path.join(
        target_dir,
        os.path.basename(overlay_name))
    render_template(template, rendered_template_file)
    return rendered_template_file


def render_local_overlay(target_dir):
    """Render the local overlay template in the directory supplied.

    :param target_dir: Directory to render overlay in
    :type overlay_name: str
    :returns: Path to rendered overlay
    :rtype: str
    """
    template = get_template(LOCAL_OVERLAY_TEMPLATE_NAME)
    if not template:
        template = jinja2.Environment(loader=jinja2.BaseLoader).from_string(
            LOCAL_OVERLAY_TEMPLATE)
    rendered_template_file = os.path.join(
        target_dir,
        os.path.basename(LOCAL_OVERLAY_TEMPLATE_NAME))
    if utils.get_charm_config().get('charm_name', None):
        render_template(template, rendered_template_file)
        return rendered_template_file


def is_local_overlay_enabled(bundle):
    """Check the bundle to see if a local overlay should be applied.

    Read the bundle and look for LOCAL_OVERLAY_ENABLED_KEY and return
    its value if present otherwise return True. This allows a bundle
    to disable adding the local overlay which points the bundle at
    the local charm.

    :param bundle: Name of bundle being deployed
    :type bundle: str
    :returns: Whether to enable local overlay
    :rtype: bool
    """
    with open(bundle, 'r') as stream:
        return yaml.safe_load(stream).get(LOCAL_OVERLAY_ENABLED_KEY, True)


def render_overlays(bundle, target_dir):
    """Render the overlays for the given bundle in the directory provided.

    :param bundle: Name of bundle being deployed
    :type bundle: str
    :param target_dir: Directory to render overlay in
    :type overlay_name: str
    :returns: List of rendered overlays
    :rtype: [str, str,...]
    """
    overlays = []
    if is_local_overlay_enabled(bundle):
        local_overlay = render_local_overlay(target_dir)
        if local_overlay:
            overlays.append(local_overlay)
    rendered_bundle_overlay = render_overlay(bundle, target_dir)
    if rendered_bundle_overlay:
        overlays.append(rendered_bundle_overlay)
    return overlays


def deploy_bundle(bundle, model):
    """Deploy the given bundle file in the specified model.

    :param bundle: Path to bundle file
    :type bundle: str
    :param model: Name of model to deploy bundle in
    :type model: str
    """
    logging.info("Deploying bundle '{}' on to '{}' model"
                 .format(bundle, model))
    cmd = ['juju', 'deploy', '-m', model, bundle]
    with tempfile.TemporaryDirectory() as tmpdirname:
        for overlay in render_overlays(bundle, tmpdirname):
            logging.info("Deploying overlay '{}' on to '{}' model"
                         .format(overlay, model))
            cmd.extend(['--overlay', overlay])
        utils.check_output_logging(cmd)


def deploy(bundle, model, wait=True):
    """Run all steps to complete deployment.

    :param bundle: Path to bundle file
    :type bundle: str
    :param model: Name of model to deploy bundle in
    :type model: str
    :param wait: Whether to wait until deployment completes
    :type model: bool
    """
    run_report.register_event_start('Deploy Bundle')
    deploy_bundle(bundle, model)
    run_report.register_event_finish('Deploy Bundle')
    if wait:
        run_report.register_event_start('Wait for Deployment')
        test_config = utils.get_charm_config()
        logging.info("Waiting for environment to settle")
        zaza.model.set_juju_model(model)
        zaza.model.wait_for_application_states(
            model,
            test_config.get('target_deploy_status', {}))
        run_report.register_event_finish('Wait for Deployment')


def parse_args(args):
    """Parse command line arguments.

    :param args: List of configure functions functions
    :type list: [str1, str2,...] List of command line arguments
    :returns: Parsed arguments
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model',
                        help='Model to deploy to',
                        required=True)
    parser.add_argument('-b', '--bundle',
                        help='Bundle name (excluding file ext)',
                        required=True)
    parser.add_argument('--no-wait', dest='wait',
                        help='Do not wait for deployment to settle',
                        action='store_false')
    parser.add_argument('--log', dest='loglevel',
                        help='Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]')
    parser.set_defaults(wait=True, loglevel='INFO')
    return parser.parse_args(args)


def main():
    """Deploy bundle."""
    args = parse_args(sys.argv[1:])
    cli_utils.setup_logging(log_level=args.loglevel.upper())
    deploy(args.bundle, args.model, wait=args.wait)
    run_report.output_event_report()
