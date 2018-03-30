#!/usr/bin/env python

import logging
import os
import six
import subprocess
import yaml

from zaza import model
from zaza.charm_lifecycle import utils as lifecycle_utils


def get_network_env_vars():
    """Get environment variables with names which are consistent with
    network.yaml keys;  Also get network environment variables as commonly
    used by openstack-charm-testing and ubuntu-openstack-ci automation.
    Return a dictionary compatible with openstack-mojo-specs network.yaml
    key structure."""

    # Example o-c-t & uosci environment variables:
    #   NET_ID="a705dd0f-5571-4818-8c30-4132cc494668"
    #   GATEWAY="172.17.107.1"
    #   CIDR_EXT="172.17.107.0/24"
    #   CIDR_PRIV="192.168.121.0/24"
    #   NAMESERVER="10.5.0.2"
    #   FIP_RANGE="172.17.107.200:172.17.107.249"
    #   AMULET_OS_VIP00="172.17.107.250"
    #   AMULET_OS_VIP01="172.17.107.251"
    #   AMULET_OS_VIP02="172.17.107.252"
    #   AMULET_OS_VIP03="172.17.107.253"
    _vars = {}
    _vars['net_id'] = os.environ.get('NET_ID')
    _vars['external_dns'] = os.environ.get('NAMESERVER')
    _vars['default_gateway'] = os.environ.get('GATEWAY')
    _vars['external_net_cidr'] = os.environ.get('CIDR_EXT')
    _vars['private_net_cidr'] = os.environ.get('CIDR_PRIV')

    _fip_range = os.environ.get('FIP_RANGE')
    if _fip_range and ':' in _fip_range:
        _vars['start_floating_ip'] = os.environ.get('FIP_RANGE').split(':')[0]
        _vars['end_floating_ip'] = os.environ.get('FIP_RANGE').split(':')[1]

    _vips = [os.environ.get('AMULET_OS_VIP00'),
             os.environ.get('AMULET_OS_VIP01'),
             os.environ.get('AMULET_OS_VIP02'),
             os.environ.get('AMULET_OS_VIP03')]

    # Env var naming consistent with network.yaml takes priority
    _keys = ['default_gateway'
             'start_floating_ip',
             'end_floating_ip',
             'external_dns',
             'external_net_cidr',
             'external_net_name',
             'external_subnet_name',
             'network_type',
             'private_net_cidr',
             'router_name']
    for _key in _keys:
        _val = os.environ.get(_key)
        if _val:
            _vars[_key] = _val

    # Remove keys and items with a None value
    _vars['vips'] = [_f for _f in _vips if _f]
    for k, v in list(_vars.items()):
        if not v:
            del _vars[k]

    return _vars


def dict_to_yaml(dict_data):
    return yaml.dump(dict_data, default_flow_style=False)


def get_yaml_config(config_file):
    # Note in its original form get_mojo_config it would do a search pattern
    # through mojo stage directories. This version assumes the yaml file is in
    # the pwd.
    logging.info('Using config %s' % (config_file))
    return yaml.load(open(config_file, 'r').read())


def get_net_info(net_topology, ignore_env_vars=False):
    """Get network info from network.yaml, override the values if specific
    environment variables are set."""
    net_info = get_yaml_config('network.yaml')[net_topology]

    if not ignore_env_vars:
        logging.info('Consuming network environment variables as overrides.')
        net_info.update(get_network_env_vars())

    logging.info('Network info: {}'.format(dict_to_yaml(net_info)))
    return net_info


def parse_arg(options, arg, multiargs=False):
    if arg.upper() in os.environ:
        if multiargs:
            return os.environ[arg.upper()].split()
        else:
            return os.environ[arg.upper()]
    else:
        return getattr(options, arg)


def remote_run(unit, remote_cmd=None, timeout=None, fatal=None):
    logging.warn("Deprecate as soons as possible. Use model.run_on_unit() as "
                 "soon as libjuju unit.run returns output.")
    if fatal is None:
        fatal = True
    cmd = ['juju', 'run', '--unit', unit]
    if timeout:
        cmd.extend(['--timeout', str(timeout)])
    if remote_cmd:
        cmd.append(remote_cmd)
    else:
        cmd.append('uname -a')
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    output = p.communicate()
    if six.PY3:
        output = (output[0].decode('utf-8'), output[1])
    if p.returncode != 0 and fatal:
        raise Exception('Error running remote command')
    return output


def get_pkg_version(application, pkg):
    versions = []
    units = model.get_units(
        lifecycle_utils.get_juju_model(), application)
    for unit in units:
        cmd = 'dpkg -l | grep {}'.format(pkg)
        out = remote_run(unit.entity_id, cmd)
        versions.append(out[0].split()[2])
    if len(set(versions)) != 1:
        raise Exception('Unexpected output from pkg version check')
    return versions[0]


def get_cloud_from_controller():
    """ Get the cloud name from the Juju 2.x controller

    @returns String name of the cloud for the current Juju 2.x controller
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
    """ Get the type of the undercloud

    @returns String name of the undercloud type
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
    status = model.get_status(lifecycle_utils.get_juju_model())
    return status


def get_application_status(application=None, unit=None):
    status = get_full_juju_status()
    if application:
        status = status.applications.get(application)
    if unit:
        status = status.units.get(unit)
    return status


def get_machine_status(machine, key=None):
    status = get_full_juju_status()
    status = status.machines.get(machine)
    if key:
        status = status.get(key)
    return status


def get_machines_for_application(application):
    status = get_application_status(application)
    machines = []
    for unit in status.get('units').keys():
        machines.append(
            status.get('units').get(unit).get('machine'))
    return machines


def get_machine_uuids_for_application(application):
    uuids = []
    for machine in get_machines_for_application(application):
        uuids.append(get_machine_status(machine, key='instance-id'))
    return uuids


def setup_logging():
    logFormatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")
    rootLogger = logging.getLogger()
    rootLogger.setLevel('INFO')
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(consoleHandler)
