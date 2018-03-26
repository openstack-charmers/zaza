import logging
import zaza.model


def skipIfNotHA(service_name):
    def _skipIfNotHA_inner_1(f):
        def _skipIfNotHA_inner_2(*args, **kwargs):
            if len(zaza.model.get_app_ips(service_name)) > 1:
                return f(*args, **kwargs)
            else:
                logging.warn("Skipping HA test for non-ha service {}".format(
                    service_name))
        return _skipIfNotHA_inner_2

    return _skipIfNotHA_inner_1
