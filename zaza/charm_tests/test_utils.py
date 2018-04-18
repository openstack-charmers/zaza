import json
import logging
import subprocess
import zaza.model

import zaza.charm_lifecycle.utils as utils


def skipIfNotHA(service_name):
    def _skipIfNotHA_inner_1(f):
        def _skipIfNotHA_inner_2(*args, **kwargs):
            ips = zaza.model.get_app_ips(utils.get_juju_model(), service_name)
            if len(ips) > 1:
                return f(*args, **kwargs)
            else:
                logging.warn("Skipping HA test for non-ha service {}".format(
                    service_name))
        return _skipIfNotHA_inner_2

    return _skipIfNotHA_inner_1


# NOTE(fnordahl) this function exists because libjuju has currently not
#                implemented Application.get_actions()
def get_actions(application, schema=False):
    """
    Get available actions for application, optionally get schema (schema==True)

    :param schema: If set, include action schema in the returned data.
    :type schema: Optional[bool]
    :returns: Dictionary where keys are action names.
    :rtype: dict
    """
    logging.debug("list actions for application '{}' schema='{}'"
                  "".format(application, schema))
    cmd = ['juju', 'list-actions', "--schema={}".format(schema),
           '--format=json', application]
    actions = json.loads(subprocess.check_output(cmd))
    return actions
