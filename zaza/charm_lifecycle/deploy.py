import argparse
import jinja2
import logging
import os
import subprocess
import sys
import tempfile

import juju_wait

import zaza.charm_lifecycle.utils as utils

DEFAULT_OVERLAY_TEMPLATE_DIR = 'tests/bundles/overlays'
DEFAULT_OVERLAYS = ['local-charm-overlay.yaml']
VALID_ENVIRONMENT_KEY_PREFIXES = ['AMULET', 'ZAZA_TEMPLATE']


def is_valid_env_key(key):
    """Check if key is a valid environment variable name for use with template
       rendering

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
    """Return environment variables from the current environment that can be
       used for template rendering.

    :returns: Environment variable key values for use with template rendering
    :rtype: dict
    """
    return {k: v for k, v in os.environ.items() if is_valid_env_key(k)}


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
        loader=jinja2.FileSystemLoader(template_dir)
    )


def get_template_name(target_file):
    """Return the expected name of the template used to generate the
       target_file

    :param target_file: File to be rendered
    :type target_file: str
    :returns: Name of template used to render target_file
    :rtype: str
    """
    return '{}.j2'.format(os.path.basename(target_file))


def get_template(target_file):
    """Return the jinja2 template for the given file

    :returns: Template object used to generate target_file
    :rtype: jinja2.Template
    """
    jinja2_env = get_jinja2_env()
    try:
        template = jinja2_env.get_template(get_template_name(target_file))
    except jinja2.exceptions.TemplateNotFound:
        template = None
    return template


def render_overlay(overlay_name, target_dir):
    """Render the overlay template in the directory supplied

    :param overlay_name: Name of overlay to be rendered
    :type overlay_name: str
    :param target_dir: Directory to render overlay in
    :type overlay_name: str
    :returns: Path to rendered overlay
    :rtype: str
    """
    template = get_template(overlay_name)
    rendered_template_file = os.path.join(
        target_dir,
        os.path.basename(overlay_name))
    with open(rendered_template_file, "w") as fh:
        fh.write(
            template.render(get_template_context_from_env()))
    return rendered_template_file


def render_overlays(bundle, target_dir):
    """Render the overlays for the given bundle in the directory provided

    :param bundle: Name of bundle being deployed
    :type bundle: str
    :param target_dir: Directory to render overlay in
    :type overlay_name: str
    :returns: Path to rendered overlay
    :rtype: str
    """
    overlays = []
    for overlay in DEFAULT_OVERLAYS + [bundle]:
        rendered_overlay = render_overlay(overlay, target_dir)
        if rendered_overlay:
            overlays.append(rendered_overlay)
    return overlays


def deploy_bundle(bundle, model):
    """Deploy the given bundle file in the specified model

    :param bundle: Path to bundle file
    :type bundle: str
    :param model: Name of model to deploy bundle in
    :type model: str
    """
    logging.info("Deploying bundle {}".format(bundle))
    cmd = ['juju', 'deploy', '-m', model, bundle]
    with tempfile.TemporaryDirectory() as tmpdirname:
        for overlay in render_overlays(bundle, tmpdirname):
            cmd.extend(['--overlay', overlay])
        subprocess.check_call(cmd)


def deploy(bundle, model, wait=True):
    """Run all steps to complete deployment

    :param bundle: Path to bundle file
    :type bundle: str
    :param model: Name of model to deploy bundle in
    :type model: str
    :param wait: Whether to wait until deployment completes
    :type model: bool
    """
    deploy_bundle(bundle, model)
    if wait:
        logging.info("Waiting for environment to settle")
        utils.set_juju_model(model)
        juju_wait.wait()


def parse_args(args):
    """Parse command line arguments

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
    parser.set_defaults(wait=True)
    return parser.parse_args(args)


def main():
    """Deploy bundle"""
    logging.basicConfig(level=logging.INFO)
    args = parse_args(sys.argv[1:])
    deploy(args.bundle, args.model, wait=args.wait)
