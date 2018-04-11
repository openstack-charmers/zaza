import logging
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
