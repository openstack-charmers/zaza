#!/usr/bin/env python

# The purpose of this file is for general use utilities internally and directly
# consumed by zaza. No guarantees are made for consuming these utilities
# outside of zaza. These utilities may be deprecated, removed or transformed up
# to and including parameters and return values changing without warning.

# You have been warned.


import logging
import os
import six
import subprocess
import yaml

from zaza import model
from zaza.charm_lifecycle import utils as lifecycle_utils


def get_undercloud_env_vars():
    """ Get environment specific undercloud network configuration settings from
    environment variables.

    For each testing substrate, specific undercloud network configuration
    settings should be exported into the environment to enable testing on that
    substrate.

    Note: *Overcloud* settings should be declared by the test caller and should
    not be overridden here.

    Return a dictionary compatible with zaza.configure.network functions'
    expected key structure.

    Example exported environment variables:
    export default_gateway="172.17.107.1"
    export external_net_cidr="172.17.107.0/24"
    export external_dns="10.5.0.2"
    export start_floating_ip="172.17.107.200"
    export end_floating_ip="172.17.107.249"

    Example o-c-t & uosci non-standard environment variables:
    export NET_ID="a705dd0f-5571-4818-8c30-4132cc494668"
    export GATEWAY="172.17.107.1"
    export CIDR_EXT="172.17.107.0/24"
    export NAMESERVER="10.5.0.2"
    export FIP_RANGE="172.17.107.200:172.17.107.249"

    :returns: Network environment variables
    :rtype: dict
    """

    # Handle backward compatibile OSCI enviornment variables
    _vars = {}
    _vars['net_id'] = os.environ.get('NET_ID')
    _vars['external_dns'] = os.environ.get('NAMESERVER')
    _vars['default_gateway'] = os.environ.get('GATEWAY')
    _vars['external_net_cidr'] = os.environ.get('CIDR_EXT')

    # Take FIP_RANGE and create start and end floating ips
    _fip_range = os.environ.get('FIP_RANGE')
    if _fip_range and ':' in _fip_range:
        _vars['start_floating_ip'] = os.environ.get('FIP_RANGE').split(':')[0]
        _vars['end_floating_ip'] = os.environ.get('FIP_RANGE').split(':')[1]

    # Env var naming consistent with zaza.configure.network functions takes
    # priority. Override backward compatible settings.
    _keys = ['default_gateway',
             'start_floating_ip',
             'end_floating_ip',
             'external_dns',
             'external_net_cidr']
    for _key in _keys:
        _val = os.environ.get(_key)
        if _val:
            _vars[_key] = _val

    # Remove keys and items with a None value
    for k, v in list(_vars.items()):
        if not v:
            del _vars[k]

    return _vars


def dict_to_yaml(dict_data):
    """Return YAML from dictionary

    :param dict_data: Dictionary data
    :type dict_data: dict
    :returns: YAML dump
    :rtype: string
    """

    return yaml.dump(dict_data, default_flow_style=False)


def get_yaml_config(config_file):
    """Return configuration from YAML file

    :param config_file: Configuration file name
    :type config_file: string
    :returns: Dictionary of configuration
    :rtype: dict
    """

    # Note in its original form get_mojo_config it would do a search pattern
    # through mojo stage directories. This version assumes the yaml file is in
    # the pwd.
    logging.info('Using config %s' % (config_file))
    return yaml.load(open(config_file, 'r').read())


def get_net_info(net_topology, ignore_env_vars=False,
                 net_topology_file="network.yaml"):
    """Get network info from network.yaml, override the values if specific
    environment variables are set for the undercloud.

    This function may be used when running network configuration from CLI to
    pass in network configuration settings from a YAML file.

    :param net_topology: Network topology name from network.yaml
    :type net_topology: string
    :param ignore_env_vars: Ignore enviroment variables or not
    :type ignore_env_vars: boolean
    :returns: Dictionary of network configuration
    :rtype: dict
    """

    if os.path.exists(net_topology_file):
        net_info = get_yaml_config(net_topology_file)[net_topology]
    else:
        raise Exception("Network topology file: {} not found."
                        .format(net_topology_file))

    if not ignore_env_vars:
        logging.info("Consuming network environment variables as overrides "
                     "for the undercloud.")
        net_info.update(get_undercloud_env_vars())

    logging.info("Network info: {}".format(dict_to_yaml(net_info)))
    return net_info


def parse_arg(options, arg, multiargs=False):
    """Parse argparse argments

    :param options: Argparse options
    :type options: argparse object
    :param arg: Argument attribute key
    :type arg: string
    :param multiargs: More than one arugment or not
    :type multiargs: boolean
    :returns: Argparse atrribute value
    :rtype: string
    """

    if arg.upper() in os.environ:
        if multiargs:
            return os.environ[arg.upper()].split()
        else:
            return os.environ[arg.upper()]
    else:
        return getattr(options, arg)


def remote_run(unit, remote_cmd, timeout=None, fatal=None):
    """Run command on unit and return the output

    NOTE: This function is pre-deprecated. As soon as libjuju unit.run is able
    to return output this functionality should move to model.run_on_unit.

    :param remote_cmd: Command to execute on unit
    :type remote_cmd: string
    :param timeout: Timeout value for the command
    :type arg: int
    :param fatal: Command failure condidered fatal or not
    :type fatal: boolean
    :returns: Juju run output
    :rtype: string
    """
    if fatal is None:
        fatal = True
    result = model.run_on_unit(lifecycle_utils.get_juju_model(),
                               unit,
                               remote_cmd,
                               timeout=timeout)
    if result:
        if int(result.get('Code')) == 0:
            return result.get('Stdout')
        else:
            if fatal:
                raise Exception('Error running remote command: {}'
                                .format(result.get('Stderr')))
            return result.get('Stderr')


def get_pkg_version(application, pkg):
    """Return package version

    :param application: Application name
    :type application: string
    :param pkg: Package name
    :type pkg: string
    :returns: List of package version
    :rtype: list
    """

    versions = []
    units = model.get_units(
        lifecycle_utils.get_juju_model(), application)
    for unit in units:
        cmd = 'dpkg -l | grep {}'.format(pkg)
        out = remote_run(unit.entity_id, cmd)
        versions.append(out.split('\n')[0].split()[2])
    if len(set(versions)) != 1:
        raise Exception('Unexpected output from pkg version check')
    return versions[0]


def get_cloud_from_controller():
    """Get the cloud name from the Juju controller

    :returns: Name of the cloud for the current controller
    :rtype: string
    """

    cmd = ['juju', 'show-controller', '--format=yaml']
    output = subprocess.check_output(cmd)
    if six.PY3:
        output = output.decode('utf-8')
    cloud_config = yaml.load(output)
    # There will only be one top level controller from show-controller,
    # but we do not know its name.
    assert len(cloud_config) == 1
    try:
        return list(cloud_config.values())[0]['details']['cloud']
    except KeyError:
        raise KeyError("Failed to get cloud information from the controller")


def get_provider_type():
    """Get the type of the undercloud

    :returns: Name of the undercloud type
    :rtype: string
    """

    juju_env = subprocess.check_output(['juju', 'switch'])
    if six.PY3:
        juju_env = juju_env.decode('utf-8')
    juju_env = juju_env.strip('\n')
    cloud = get_cloud_from_controller()
    if cloud:
        # If the controller was deployed from this system with
        # the cloud configured in ~/.local/share/juju/clouds.yaml
        # Determine the cloud type directly
        cmd = ['juju', 'show-cloud', cloud, '--format=yaml']
        output = subprocess.check_output(cmd)
        if six.PY3:
            output = output.decode('utf-8')
        return yaml.load(output)['type']
    else:
        # If the controller was deployed elsewhere
        # show-controllers unhelpfully returns an empty string for cloud
        # For now assume openstack
        return 'openstack'


def get_full_juju_status():
    """Return the full juju status output

    :returns: Full juju status output
    :rtype: dict
    """

    status = model.get_status(lifecycle_utils.get_juju_model())
    return status


def get_application_status(application=None, unit=None):
    """Return the juju status for an application

    :param application: Application name
    :type application: string
    :param unit: Specific unit
    :type unit: string
    :returns: Juju status output for an application
    :rtype: dict
    """

    status = get_full_juju_status()
    if application:
        status = status.applications.get(application)
    if unit:
        status = status.units.get(unit)
    return status


def get_machine_status(machine, key=None):
    """Return the juju status for a machine

    :param machine: Machine number
    :type machine: string
    :param key: Key option requested
    :type key: string
    :returns: Juju status output for a machine
    :rtype: dict
    """

    status = get_full_juju_status()
    status = status.machines.get(machine)
    if key:
        status = status.get(key)
    return status


def get_machines_for_application(application):
    """Return machines for a given application

    :param application: Application name
    :type application: string
    :returns: List of machines for an application
    :rtype: list
    """

    status = get_application_status(application)
    machines = []
    for unit in status.get('units').keys():
        machines.append(
            status.get('units').get(unit).get('machine'))
    return machines


def get_machine_uuids_for_application(application):
    """Return machine uuids for a given application

    :param application: Application name
    :type application: string
    :returns: List of machine uuuids for an application
    :rtype: list
    """

    uuids = []
    for machine in get_machines_for_application(application):
        uuids.append(get_machine_status(machine, key='instance-id'))
    return uuids


def setup_logging():
    """Setup zaza logging

    :returns: Nothing: This fucntion is executed for its sideffect
    :rtype: None
    """

    logFormatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")
    rootLogger = logging.getLogger()
    rootLogger.setLevel('INFO')
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(consoleHandler)
