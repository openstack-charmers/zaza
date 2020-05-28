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

import zaza.controller
import zaza.model
import zaza.charm_lifecycle.utils as utils
import zaza.utilities.cli as cli_utils
import zaza.utilities.exceptions as zaza_exceptions
import zaza.utilities.run_report as run_report
import zaza.utilities.deployment_env as deployment_env

DEFAULT_OVERLAY_TEMPLATE_DIR = 'tests/bundles/overlays'
LOCAL_OVERLAY_TEMPLATE = """
applications:
  {{ charm_name }}:
    charm: {{ charm_location }}
"""
LOCAL_OVERLAY_TEMPLATE_NAME = 'local-charm-overlay.yaml'
LOCAL_OVERLAY_ENABLED_KEY = 'local_overlay_enabled'


def get_charm_config_context():
    """Return settings from charm config file.

    :returns: Context for template rendering
    :rtype: dict
    """
    # NOTE(fnordahl): Starting with Juju version 2.7, relative charm paths will
    # be interpreted in relation to the location of the overlay file.  Previous
    # versions would interpret paths relative to the location of the main
    # bundle file.  Build an absolute path so we can work with both paradigms.
    bundle_dir_abspath = os.path.abspath(utils.BUNDLE_DIR)
    test_config = utils.get_charm_config()
    ctxt = {
        'charm_name': test_config['charm_name'],
        'charm_location': '{}/../../../{}'
                          .format(bundle_dir_abspath,
                                  test_config['charm_name']),
    }
    return ctxt


def get_template_overlay_context():
    """Combine contexts which can be used for overlay template rendering.

    :returns: Context for template rendering
    :rtype: dict
    """
    context = {}
    contexts = [
        deployment_env.get_deployment_context(),
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


def get_jinja2_loader(template_dir=None):
    """Inspect the template directory and set up appropriate loader.

    :param target_dir: Limit template loading to this directory.
    :type target_dir: str
    :returns: Jinja2 loader
    :rtype: jinja2.loaders.BaseLoader
    """
    if template_dir:
        return jinja2.FileSystemLoader(template_dir)
    else:
        template_dir = get_overlay_template_dir()
    provider_template_dir = os.path.join(
        template_dir, zaza.controller.get_cloud_type())
    if (os.path.exists(provider_template_dir) and
            os.path.isdir(provider_template_dir)):
        return jinja2.ChoiceLoader([
            jinja2.FileSystemLoader(provider_template_dir),
            jinja2.FileSystemLoader(template_dir),
        ])
    else:
        return jinja2.FileSystemLoader(template_dir)


def get_jinja2_env(template_dir=None):
    """Return a jinja2 environment that can be used to render templates from.

    :param target_dir: Limit template loading to this directory.
    :type target_dir: str
    :returns: Jinja2 template loader
    :rtype: jinja2.Environment
    """
    return jinja2.Environment(
        loader=get_jinja2_loader(template_dir=template_dir),
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


def get_template(target_file, template_dir=None):
    """Return the jinja2 template for the given file.

    :param target_dir: Limit template loading to this directory.
    :type target_dir: str
    :returns: Template object used to generate target_file
    :rtype: jinja2.Template
    """
    jinja2_env = get_jinja2_env(template_dir=template_dir)
    try:
        template = jinja2_env.get_template(get_template_name(target_file))
    except jinja2.exceptions.TemplateNotFound:
        template = None
    return template


def render_template(template, target_file, model_ctxt=None):
    """Render the template to the file supplied.

    :param template: Template to be rendered
    :type template: jinja2.Template
    :param target_file: File name for rendered template
    :type target_file: str
    :param model_ctxt: Additional context to be used when rendering bundle
                       templates.
    :type model_ctxt: {}
    """
    model_ctxt = model_ctxt or {}
    try:
        overlay_ctxt = get_template_overlay_context()
        overlay_ctxt.update(model_ctxt)
        with open(target_file, "w") as fh:
            fh.write(
                template.render(overlay_ctxt))
    except jinja2.exceptions.UndefinedError as e:
        logging.error("Template error. You may be missing"
                      " a mandatory environment variable : {}".format(e))
        sys.exit(1)
    logging.info("Rendered template '{}' to file '{}'".format(template,
                                                              target_file))


def render_overlay(overlay_name, target_dir, model_ctxt=None):
    """Render the overlay template in the directory supplied.

    :param overlay_name: Name of overlay to be rendered
    :type overlay_name: str
    :param target_dir: Directory to render overlay in
    :type overlay_name: str
    :param model_ctxt: Additional context to be used when rendering bundle
                       templates.
    :type model_ctxt: {}
    :returns: Path to rendered overlay
    :rtype: str
    """
    template = get_template(overlay_name)
    if not template:
        return
    rendered_template_file = os.path.join(
        target_dir,
        os.path.basename(overlay_name))
    render_template(template, rendered_template_file, model_ctxt=model_ctxt)
    return rendered_template_file


def render_local_overlay(target_dir, model_ctxt=None):
    """Render the local overlay template in the directory supplied.

    :param target_dir: Directory to render overlay in
    :type overlay_name: str
    :param model_ctxt: Additional context to be used when rendering bundle
                       templates.
    :type model_ctxt: {}
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
    render_template(
        template,
        rendered_template_file,
        model_ctxt=model_ctxt)
    return rendered_template_file


def is_local_overlay_enabled_in_bundle(bundle):
    """Check the bundle to see if a local overlay should be applied.

    Read the bundle and look for LOCAL_OVERLAY_ENABLED_KEY and return
    its value if present otherwise return True. This allows a bundle
    to disable adding the local overlay which points the bundle at
    the local charm.

    :param bundle: Name of bundle being deployed
    :type bundle: str
    :returns: Whether the bundle asserts to enable local overlay
    :rtype: bool
    """
    with open(bundle, 'r') as stream:
        return yaml.safe_load(stream).get(LOCAL_OVERLAY_ENABLED_KEY, True)


def should_render_local_overlay(bundle):
    """Determine if the local overlay should be rendered.

    Check if an overlay file exists, then check if the bundle overrides
    LOCAL_OVERLAY_ENABLED_KEY with a False value. If no file exists, determine
    if the LOCAL_OVERLAY_TEMPLATE should be rendered by checking for the
    charm_name setting in the tests.yaml file.

    :param bundle: Name of bundle being deployed
    :type bundle: str
    :returns: Whether to render a local overlay
    :rtype: bool
    """
    # Is there a local overlay file?
    if os.path.isfile(
            os.path.join(
                DEFAULT_OVERLAY_TEMPLATE_DIR,
                "{}.j2".format(LOCAL_OVERLAY_TEMPLATE_NAME))):
        # Check for an override in the bundle.
        # Note: the default is True if the LOCAL_OVERLAY_ENABLED_KEY
        # is not present.
        return is_local_overlay_enabled_in_bundle(bundle)
    # Should we render the LOCAL_OVERLAY_TEMPLATE?
    elif utils.get_charm_config().get('charm_name', None):
        # Need to convert to boolean
        return True
    return False


def render_overlays(bundle, target_dir, model_ctxt=None):
    """Render the overlays for the given bundle in the directory provided.

    :param bundle: Name of bundle being deployed
    :type bundle: str
    :param target_dir: Directory to render overlay in
    :type overlay_name: str
    :param model_ctxt: Additional context to be used when rendering bundle
                       templates.
    :type model_ctxt: {}
    :returns: List of rendered overlays
    :rtype: [str, str,...]
    """
    overlays = []
    if should_render_local_overlay(bundle):
        local_overlay = render_local_overlay(target_dir, model_ctxt=model_ctxt)
        if local_overlay:
            overlays.append(local_overlay)
    rendered_bundle_overlay = render_overlay(bundle, target_dir,
                                             model_ctxt=model_ctxt)
    if rendered_bundle_overlay:
        overlays.append(rendered_bundle_overlay)
    return overlays


def deploy_bundle(bundle, model, model_ctxt=None, force=False):
    """Deploy the given bundle file in the specified model.

    The force param is used to enable zaza testing with Juju with charms
    that would be rejected by juju (e.g. series not supported).

    :param bundle: Path to bundle file
    :type bundle: str
    :param model: Name of model to deploy bundle in
    :type model: str
    :param model_ctxt: Additional context to be used when rendering bundle
                       templates.
    :type model_ctxt: {}
    :param force: Pass the force parameter if True
    :type force: Boolean
    """
    logging.info("Deploying bundle '{}' on to '{}' model"
                 .format(bundle, model))
    cmd = ['juju', 'deploy', '-m', model]
    if force:
        cmd.append('--force')
    with tempfile.TemporaryDirectory() as tmpdirname:
        bundle_out = '{}/{}'.format(tmpdirname, os.path.basename(bundle))
        # Bundle templates should only exist in the bundle directory so
        # explicitly set the Jinja2 load path.
        bundle_template = get_template(
            bundle,
            template_dir=os.path.dirname(bundle))
        if bundle_template:
            if os.path.exists(bundle):
                raise zaza_exceptions.TemplateConflict(
                    "Found bundle template ({}) and bundle ({})".format(
                        bundle_template.filename,
                        bundle))
            render_template(bundle_template, bundle_out, model_ctxt=model_ctxt)
            cmd.append(bundle_out)
        else:
            cmd.append(bundle)
        for overlay in render_overlays(bundle, tmpdirname,
                                       model_ctxt=model_ctxt):
            logging.info("Deploying overlay '{}' on to '{}' model"
                         .format(overlay, model))
            cmd.extend(['--overlay', overlay])
        utils.check_output_logging(cmd)


def deploy(bundle, model, wait=True, model_ctxt=None, force=False):
    """Run all steps to complete deployment.

    :param bundle: Path to bundle file
    :type bundle: str
    :param model: Name of model to deploy bundle in
    :type model: str
    :param wait: Whether to wait until deployment completes
    :type wait: bool
    :param model_ctxt: Additional context to be used when rendering bundle
                       templates.
    :type model_ctxt: {}
    :param force: Pass the force parameter if True
    :type force: Boolean
    """
    run_report.register_event_start('Deploy Bundle')
    deploy_bundle(bundle, model, model_ctxt=model_ctxt, force=force)
    run_report.register_event_finish('Deploy Bundle')
    if wait:
        run_report.register_event_start('Wait for Deployment')
        test_config = utils.get_charm_config()
        logging.info("Waiting for environment to settle")
        zaza.model.set_juju_model(model)
        deploy_ctxt = deployment_env.get_deployment_context()
        timeout = int(deploy_ctxt.get('TEST_DEPLOY_TIMEOUT', '3600'))
        logging.info("Timeout for deployment to settle set to: {}".format(
            timeout))
        zaza.model.wait_for_application_states(
            model,
            test_config.get('target_deploy_status', {}),
            timeout=timeout)
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
    parser.add_argument('-f', '--force', dest='force',
                        help='Pass --force to the juju deploy command',
                        action='store_true')
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
    if args.force:
        logging.warn("Using the --force argument for 'juju deploy'. Note "
                     "that this disables juju checks for compatibility.")
    deploy(args.bundle, args.model, wait=args.wait, force=args.force)
    run_report.output_event_report()
