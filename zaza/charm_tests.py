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


print("Loading zaza.openstack.charm_tests is deprecated. You should"
      " migrate to zaza.openstack.charm_tests immediately.")


from zaza.openstack.charm_tests import barbican_vault  # noqa
from zaza.openstack.charm_tests import ceph  # noqa
from zaza.openstack.charm_tests import dragent  # noqa
from zaza.openstack.charm_tests import glance  # noqa
from zaza.openstack.charm_tests import keystone  # noqa
from zaza.openstack.charm_tests import masakari  # noqa
from zaza.openstack.charm_tests import neutron  # noqa
from zaza.openstack.charm_tests import neutron_openvswitch  # noqa
from zaza.openstack.charm_tests import noop  # noqa
from zaza.openstack.charm_tests import nova  # noqa
from zaza.openstack.charm_tests import octavia  # noqa
from zaza.openstack.charm_tests import pacemaker_remote  # noqa
from zaza.openstack.charm_tests import security  # noqa
from zaza.openstack.charm_tests import series_upgrade  # noqa
from zaza.openstack.charm_tests import vault  # noqa
