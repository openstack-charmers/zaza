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

"""Module containing data about OpenStack versions."""
from collections import OrderedDict


UBUNTU_OPENSTACK_RELEASE = OrderedDict([
    ('oneiric', 'diablo'),
    ('precise', 'essex'),
    ('quantal', 'folsom'),
    ('raring', 'grizzly'),
    ('saucy', 'havana'),
    ('trusty', 'icehouse'),
    ('utopic', 'juno'),
    ('vivid', 'kilo'),
    ('wily', 'liberty'),
    ('xenial', 'mitaka'),
    ('yakkety', 'newton'),
    ('zesty', 'ocata'),
    ('artful', 'pike'),
    ('bionic', 'queens'),
    ('cosmic', 'rocky'),
    ('disco', 'stein'),
])


OPENSTACK_CODENAMES = OrderedDict([
    ('2011.2', 'diablo'),
    ('2012.1', 'essex'),
    ('2012.2', 'folsom'),
    ('2013.1', 'grizzly'),
    ('2013.2', 'havana'),
    ('2014.1', 'icehouse'),
    ('2014.2', 'juno'),
    ('2015.1', 'kilo'),
    ('2015.2', 'liberty'),
    ('2016.1', 'mitaka'),
    ('2016.2', 'newton'),
    ('2017.1', 'ocata'),
    ('2017.2', 'pike'),
    ('2018.1', 'queens'),
    ('2018.2', 'rocky'),
    ('2019.1', 'stein'),
])

OPENSTACK_RELEASES_PAIRS = [
    'trusty_icehouse', 'trusty_kilo', 'trusty_liberty',
    'trusty_mitaka', 'xenial_mitaka', 'xenial_newton',
    'yakkety_newton', 'xenial_ocata', 'zesty_ocata',
    'xenial_pike', 'artful_pike', 'xenial_queens',
    'bionic_queens', 'bionic_rocky', 'cosmic_rocky',
    'bionic-stein', 'disco-stein']

# The ugly duckling - must list releases oldest to newest
SWIFT_CODENAMES = OrderedDict([
    ('diablo',
        ['1.4.3']),
    ('essex',
        ['1.4.8']),
    ('folsom',
        ['1.7.4']),
    ('grizzly',
        ['1.7.6', '1.7.7', '1.8.0']),
    ('havana',
        ['1.9.0', '1.9.1', '1.10.0']),
    ('icehouse',
        ['1.11.0', '1.12.0', '1.13.0', '1.13.1']),
    ('juno',
        ['2.0.0', '2.1.0', '2.2.0']),
    ('kilo',
        ['2.2.1', '2.2.2']),
    ('liberty',
        ['2.3.0', '2.4.0', '2.5.0']),
    ('mitaka',
        ['2.5.0', '2.6.0', '2.7.0']),
    ('newton',
        ['2.8.0', '2.9.0']),
    ('ocata',
        ['2.11.0', '2.12.0', '2.13.0']),
    ('pike',
        ['2.13.0', '2.15.0']),
    ('queens',
        ['2.16.0', '2.17.0']),
    ('rocky',
        ['2.18.0', '2.19.0']),
    ('stein',
        ['2.20.0', '2.21.0'])
])

# >= Liberty version->codename mapping
PACKAGE_CODENAMES = {
    'nova-common': OrderedDict([
        ('12', 'liberty'),
        ('13', 'mitaka'),
        ('14', 'newton'),
        ('15', 'ocata'),
        ('16', 'pike'),
        ('17', 'queens'),
        ('18', 'rocky'),
        ('19', 'stein'),
    ]),
    'neutron-common': OrderedDict([
        ('7', 'liberty'),
        ('8', 'mitaka'),
        ('9', 'newton'),
        ('10', 'ocata'),
        ('11', 'pike'),
        ('12', 'queens'),
        ('13', 'rocky'),
        ('14', 'stein'),
    ]),
    'cinder-common': OrderedDict([
        ('7', 'liberty'),
        ('8', 'mitaka'),
        ('9', 'newton'),
        ('10', 'ocata'),
        ('11', 'pike'),
        ('12', 'queens'),
        ('13', 'rocky'),
        ('14', 'stein'),
    ]),
    'keystone': OrderedDict([
        ('8', 'liberty'),
        ('9', 'mitaka'),
        ('10', 'newton'),
        ('11', 'ocata'),
        ('12', 'pike'),
        ('13', 'queens'),
        ('14', 'rocky'),
        ('15', 'stein'),
    ]),
    'horizon-common': OrderedDict([
        ('8', 'liberty'),
        ('9', 'mitaka'),
        ('10', 'newton'),
        ('11', 'ocata'),
        ('12', 'pike'),
        ('13', 'queens'),
        ('14', 'rocky'),
        ('15', 'stein'),
    ]),
    'ceilometer-common': OrderedDict([
        ('5', 'liberty'),
        ('6', 'mitaka'),
        ('7', 'newton'),
        ('8', 'ocata'),
        ('9', 'pike'),
        ('10', 'queens'),
        ('11', 'rocky'),
        ('12', 'stein'),
    ]),
    'heat-common': OrderedDict([
        ('5', 'liberty'),
        ('6', 'mitaka'),
        ('7', 'newton'),
        ('8', 'ocata'),
        ('9', 'pike'),
        ('10', 'queens'),
        ('11', 'rocky'),
        ('12', 'stein'),
    ]),
    'glance-common': OrderedDict([
        ('11', 'liberty'),
        ('12', 'mitaka'),
        ('13', 'newton'),
        ('14', 'ocata'),
        ('15', 'pike'),
        ('16', 'queens'),
        ('17', 'rocky'),
        ('18', 'stein'),
    ]),
    'openstack-dashboard': OrderedDict([
        ('8', 'liberty'),
        ('9', 'mitaka'),
        ('10', 'newton'),
        ('11', 'ocata'),
        ('12', 'pike'),
        ('13', 'queens'),
        ('14', 'rocky'),
        ('15', 'stein'),
    ]),
}
