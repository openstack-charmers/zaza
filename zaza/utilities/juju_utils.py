#!/usr/bin/env python3

import os
from pathlib import Path

from zaza import (
    model,
    controller,
)
from zaza.charm_lifecycle import utils as lifecycle_utils
from zaza.utilities import generic_utils


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

    if unit and not application:
        application = unit.split("/")[0]

    if application:
        status = status.applications.get(application)
    if unit:
        status = status.get("units").get(unit)
    return status


def get_cloud_configs(cloud=None):
    """Get cloud configuration from local clouds.yaml

    libjuju does not yet have cloud information implemented.
    Use libjuju as soon as possible.

    :param cloud: Name of specific cloud
    :type remote_cmd: string
    :returns: Dictionary of cloud configuration
    :rtype: dict
    """

    home = str(Path.home())
    cloud_config = os.path.join(home, ".local", "share", "juju", "clouds.yaml")
    if cloud:
        return generic_utils.get_yaml_config(cloud_config)["clouds"].get(cloud)
    else:
        return generic_utils.get_yaml_config(cloud_config)


def get_full_juju_status():
    """Return the full juju status output

    :returns: Full juju status output
    :rtype: dict
    """

    status = model.get_status(lifecycle_utils.get_juju_model())
    return status


def get_machines_for_application(application):
    """Return machines for a given application

    :param application: Application name
    :type application: string
    :returns: List of machines for an application
    :rtype: list
    """

    status = get_application_status(application)

    # libjuju juju status no longer has units for subordinate charms
    # Use the application it is subordinate-to to find machines
    if status.get("units") is None and status.get("subordinate-to"):
        return get_machines_for_application(status.get("subordinate-to")[0])

    machines = []
    for unit in status.get("units").keys():
        machines.append(
            status.get("units").get(unit).get("machine"))
    return machines


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


def get_machine_uuids_for_application(application):
    """Return machine uuids for a given application

    :param application: Application name
    :type application: string
    :returns: List of machine uuuids for an application
    :rtype: list
    """

    uuids = []
    for machine in get_machines_for_application(application):
        uuids.append(get_machine_status(machine, key="instance-id"))
    return uuids


def get_provider_type():
    """Get the type of the undercloud

    :returns: Name of the undercloud type
    :rtype: string
    """

    cloud = controller.get_cloud()
    if cloud:
        # If the controller was deployed from this system with
        # the cloud configured in ~/.local/share/juju/clouds.yaml
        # Determine the cloud type directly
        return get_cloud_configs(cloud)["type"]
    else:
        # If the controller was deployed elsewhere
        # For now assume openstack
        return "openstack"


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
        if int(result.get("Code")) == 0:
            return result.get("Stdout")
        else:
            if fatal:
                raise Exception("Error running remote command: {}"
                                .format(result.get("Stderr")))
            return result.get("Stderr")
