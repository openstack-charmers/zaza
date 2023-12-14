# -*- coding: utf-8 -*-

# Copyright 2020 Canonical Ltd.
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

"""Module used to setup the zaza framework."""

from __future__ import print_function

import os
import sys
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

version = "0.0.1.dev1"
install_require = [
    'oslo.config<6.12.0',  # pin at stable/train to retain Py3.5 support
    'async_generator',

    # Newer versions require a Rust compiler to build, see
    # * https://github.com/openstack-charmers/zaza/issues/421
    # * https://mail.python.org/pipermail/cryptography-dev/2021-January/001003.html
    'cryptography<3.4',

    'hvac<0.7.0',
    'jinja2',
    'juju<3.0',
    'juju-wait',
    'PyYAML',
    'tenacity',
    'python-libmaas',
    # protobuf dropped support for python-3.6 in v3.20.0[0], although it wasn't
    # until 4.21.0 that it became truly incompatible. The pinning used is
    # `<4.21.0`
    #
    # [0] https://github.com/protocolbuffers/protobuf/commit/301d315dc4674d1bc799446644e88eff0af1ac86  # noqa
    # [1] https://github.com/protocolbuffers/protobuf/issues/10076
    'protobuf < 4.21.0',
    # macaroonbakery in v1.3.4 added a constraint of protobuf>=3.20.0[0] which
    # makes it incompatible with python 3.6 while v1.3.3 was released in a
    # broken state[1]
    #
    # [0] https://github.com/go-macaroon-bakery/py-macaroon-bakery/commit/7f1fe6a2adb2f80db12bccfb81f629d66d106e03  # noqa
    # [1] https://github.com/go-macaroon-bakery/py-macaroon-bakery/pull/92
    'macaroonbakery < 1.3.3',
]

tests_require = [
    'tox >= 2.3.1',
]


class Tox(TestCommand):
    """Tox class."""

    user_options = [('tox-args=', 'a', "Arguments to pass to tox")]

    def initialize_options(self):
        """Initialize options."""
        TestCommand.initialize_options(self)
        self.tox_args = None

    def finalize_options(self):
        """Finalize options."""
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        """Run the tests."""
        # import here, cause outside the eggs aren't loaded
        import tox
        import shlex
        args = self.tox_args
        # remove the 'test' arg from argv as tox passes it to ostestr which
        # breaks it.
        sys.argv.pop()
        if args:
            args = shlex.split(self.tox_args)
        errno = tox.cmdline(args=args)
        sys.exit(errno)


if sys.argv[-1] == 'publish':
    os.system("python setup.py sdist upload")
    os.system("python setup.py bdist_wheel upload")
    sys.exit()


if sys.argv[-1] == 'tag':
    os.system("git tag -a %s -m 'version %s'" % (version, version))
    os.system("git push --tags")
    sys.exit()


setup(
    entry_points={
        'console_scripts': [
            'functest-run-suite = zaza.charm_lifecycle.func_test_runner:main',
            'functest-before-deploy = zaza.charm_lifecycle.before_deploy:main',
            'functest-deploy = zaza.charm_lifecycle.deploy:main',
            'functest-configure = zaza.charm_lifecycle.configure:main',
            'functest-destroy = zaza.charm_lifecycle.destroy:main',
            'functest-prepare = zaza.charm_lifecycle.prepare:main',
            'functest-test = zaza.charm_lifecycle.test:main',
            'current-apps = zaza.model:main',
            'tempest-config = zaza.tempest_config:main',
        ]
    },
    license='Apache-2.0: http://www.apache.org/licenses/LICENSE-2.0',
    packages=find_packages(exclude=["unit_tests"]),
    zip_safe=False,
    cmdclass={'test': Tox},
    install_requires=install_require,
    extras_require={
        'testing': tests_require,
    },
    tests_require=tests_require,
)
