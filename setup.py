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
    'aiohttp<4.0.0',  # aiohttp/_http_parser.c:16227:5: error: lvalue required as increment operand
    'oslo.config<6.12.0',  # pin at stable/train to retain Py3.5 support
    'async_generator',

    # Newer versions require a Rust compiler to build, see
    # * https://github.com/openstack-charmers/zaza/issues/421
    # * https://mail.python.org/pipermail/cryptography-dev/2021-January/001003.html
    'cryptography<3.4',

    'hvac<0.7.0',
    'jinja2',
    'juju-wait',
    'PyYAML',
    'tenacity>8.2.0',
    'python-libmaas',

    # https://github.com/go-macaroon-bakery/py-macaroon-bakery/issues/94
    'macaroonbakery != 1.3.3',
]
if os.environ.get("TEST_JUJU3"):
    install_require.append('juju')
else:
    install_require.append('juju<3.0.0')

tests_require = [
    'tox >= 2.3.1',
]

extras_require = {
    'testing': tests_require,
}


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
    tests_require=tests_require,
    extras_require=extras_require,
)
