# Copyright 2021 Canonical Ltd.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Plugins.

Provides an ability for test run to plug in additional functionality to the
zaza runner.

The "tests_options" section may contain a 'plugins:' key that provides a list
of plugin configure functions.  e.g.

  tests_options:
    plugins:
      - zaza.plugins.events.configure

The configure function is called with a utils.EnvironmentDeploy which has a
'name', 'model_deploys' and 'run_in_series' attributes.  model_deploys are
utils.ModelDeploy which have a "model_alias", 'model_name' and 'bundle'.

The 'configure_plugins' method here must be called AFTER config is available in
the zaza.global_options module (currently filled by a call to
zaza.charm_lifecycle.utils.get_charm_config() from the tests.yaml file).

However, to not create a dependency on a yaml file, this module only uses the
zaza.global_options to be more flexible in how tests are specified in the
future (e.g. without a tests.yaml).
"""

from collections.abc import Iterable
import logging

import zaza.charm_lifecycle.utils as utils
from zaza.global_options import get_option


logger = logging.getLogger(__name__)


def find_and_configure_plugins(env_deployments):
    """Find and configure plugins that may have been declared.

    If the option 'plugins' is not defined, this function is a no-op.  If the
    plugins value is not a string or list, the an error is logged and the
    function just returns; i.e. misconfiguring the plugins option in the yaml
    file doesn't end the test.

    :param env_deployments: The enviroments that are doing to be run.
    :type env_deployments: List[EnvironmentDeploy]
    :raises Exception: a plugin may explode, which means this function can
        fail.
    """
    plugins = get_option("plugins")
    if plugins is None:
        return
    if isinstance(plugins, str):
        plugins = (plugins, )
    if not isinstance(plugins, Iterable):
        logger.error("Couldn't load plugins as it doesn't seem to be a list?")
        return
    for plugin_func in plugins:
        logger.debug("Running plugin func %s.", plugin_func)
        utils.get_class(plugin_func)(env_deployments)
