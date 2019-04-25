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

"""Module containing deprecated module paths."""


print("Loading zaza.openstack.utilities is deprecated. You should"
      " migrate to zaza.openstack.utilities immediately.")


from zaza.openstack.utilities import bundle  # noqa
from zaza.openstack.utilities import ceph  # noqa
from zaza.openstack.utilities import cert  # noqa
from zaza.openstack.utilities import cli  # noqa
from zaza.openstack.utilities import exceptions  # noqa
from zaza.openstack.utilities import file_assertions  # noqa
from zaza.openstack.utilities import generic  # noqa
from zaza.openstack.utilities import juju  # noqa
from zaza.openstack.utilities import openstack  # noqa
from zaza.openstack.utilities import os_versions  # noqa
