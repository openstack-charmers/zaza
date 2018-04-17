# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

version = "0.0.1.dev1"
install_require = [
    'hvac',
    'jinja2',
    'juju',
    'juju-wait',
    'PyYAML',
]

tests_require = [
    'tox >= 2.3.1',
]


class Tox(TestCommand):
    user_options = [('tox-args=', 'a', "Arguments to pass to tox")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.tox_args = None

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
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
    name='zaza',
    version=version,
    description='Provides test automation for Openstack Charms',
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Topic :: System",
        "Topic :: System :: Installation/Setup",
        "Topic :: System :: Software Distribution",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "License :: OSI Approved :: Apache Software License",
    ],
    entry_points={
        'console_scripts': [
            'functest-run-suite = zaza.charm_lifecycle.func_test_runner:main',
            'functest-deploy = zaza.charm_lifecycle.deploy:main',
            'functest-configure = zaza.charm_lifecycle.configure:main',
            'functest-destroy = zaza.charm_lifecycle.destroy:main',
            'functest-prepare = zaza.charm_lifecycle.prepare:main',
            'functest-test = zaza.charm_lifecycle.test:main',
            'current-apps = zaza.model:main',
            'tempest-config = zaza.tempest_config:main',
        ]
    },
    url='https://github.com/openstack-charmers/zaza',
    author='Chris MacNaughton',
    author_email='chris.macnaughton@canonical.com',
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
