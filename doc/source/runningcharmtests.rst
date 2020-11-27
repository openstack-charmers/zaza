Running Charm Tests
===================

The end-to-end tests of a charm are divided into distinct phases. Each phase
can be run in isolation and tests shared between charms.

Running a suite of deployments and tests
----------------------------------------

**functest-run-suite** will read the charms tests.yaml and execute the
deployments and tests outlined there. However, each phase can be run
independently.

Charm Test Phases
-----------------

Charms should ship with bundles that deploy the charm with different
application versions, topologies or config options.  functest-run-suite will
run through each phase listed below in order for each bundle that is to be
tested.

0) Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~

Optionally setting the **MODEL_SETTINGS** environment variable allows model
settings to be applied to the models created by zaza to run tests in. The
settings will be applied on top of those set 
**charm_lifecycle.prepare.MODEL_DEFAULTS** so it can be used to override any
default setting.

**MODEL_SETTINGS** should be a list of key/value pairs delimited by
semicolon e.g.::

    export MODEL_SETTINGS="no-proxy=jujucharms.com"
    export MODEL_CONSTRAINTS="virt-type=kvm"

In addition to overriding Zaza's configuration via environment variables, some
configuration can be done via a .zaza.yaml file in your home directory, eg.::

    ---
    model_settings:
        default-series: xenial
        image-stream: daily
        test-mode: true
        transmit-vendor-metrics: false
        enable-os-upgrade: false
        automatically-retry-hooks: false
        use-default-secgroup: true
    model_constraints:
        mem: '4g'
    secrets:
        setting1: value1
    runtime_config: {}

In addition to the config shown above, some options can only be added
via a .zaza.yaml file, eg.::

    ---
    region: my-region-name

The above configuration is required to run Zaza on a multi cloud / region Juju
controller.


1) Prepare
~~~~~~~~~~

Prepare the environment ready for a deployment. At a minimum create a model
to run the deployment in.

To run manually::

    $ functest-prepare --help
    usage: functest-prepare [-h] -m MODEL_NAME [--log LOGLEVEL]

    optional arguments:
      -h, --help            show this help message and exit
      -m MODEL_NAME, --model-name MODEL_NAME
                            Name of new model
      --log LOGLEVEL        Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]

2) Before Deploy
~~~~~~~~~~~~~~~~

Perform pre-deployment tasks, for example: setup a default model configuration
that is necessary to deploy a bundle.

To run manually::

    $ functest-before-deploy --help
    usage: functest-before-deploy [-h] [-c BEFOREFUNCS [BEFOREFUNCS ...]] [--log LOGLEVEL]

    optional arguments:
      -h, --help
                            show this help message and exit
      -c BEFOREFUNCS, --beforefuncs BEFOREFUNCS
                            Space separated list of config functions
      --log LOGLEVEL        Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]

3) Deploy
~~~~~~~~~

Deploy the target bundle and wait for it to complete. **functest-run-suite** 
will look at the list of bundles in the tests.yaml in the charm to determine
the bundle.

In addition to the specified bundle the overlay template directory will be
searched for a corresponding template (\<bundle\_name\>.j2). If one is found
then the overlay will be rendered using environment variables a specific set
of environment variables as context. Currently these are:

 * FIP\_RANGE
 * GATEWAY
 * NAME\_SERVER
 * NET\_ID
 * OS\_\*
 * VIP\_RANGE

The rendered overlay will be used on top of the specified bundle at deploy time.

To run manually::

    $ functest-deploy --help
    usage: functest-deploy [-h] -m MODEL -b BUNDLE [--no-wait] [--log LOGLEVEL]

    optional arguments:
      -h, --help            show this help message and exit
      -m MODEL, --model MODEL
                            Model to deploy to
      -b BUNDLE, --bundle BUNDLE
                            Bundle name (excluding file ext)
      --no-wait             Do not wait for deployment to settle
      --log LOGLEVEL        Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]


4) Configure
~~~~~~~~~~~~

Post-deployment configuration, for example create network, tenant, image, etc.
Any necessary post-deploy actions go here. **functest-run-suite** will look 
for a list of functions that should be run in tests.yaml and execute each
in turn.

To run manually::

    $ functest-configure --help
    usage: functest-configure [-h] [-c CONFIGFUNCS [CONFIGFUNCS ...]] [--log LOGLEVEL]

    optional arguments:
      -h, --help
                            show this help message and exit
      -c CONFIGFUNCS, --configfuncs CONFIGFUNCS
                            Space separated list of config functions
      --log LOGLEVEL        Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]


5) Test
~~~~~~~

Run tests. These maybe tests in zaza or a wrapper around another testing
framework like rally or tempest.  **functest-run-suite** will look for a list
of test classes that should be run in tests.yaml and execute each in turn.

To run manually::

    $ functest-test --help
    usage: functest-test [-h] [-t TESTS [TESTS ...]] [--log LOGLEVEL]

    optional arguments:
      -h, --help            show this help message and exit
      -t TESTS, --tests TESTS
                            Space separated list of test classes
      --log LOGLEVEL        Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]


6) Collect
~~~~~~~~~~

Collect artifacts useful for debugging any failures or useful for trend
analysis like deprecation warning or deployment time.


7) Destroy
~~~~~~~~~~

Destroy the model::


    $ functest-destroy --help
    usage: functest-destroy [-h] -m MODEL_NAME [--log LOGLEVEL]

    optional arguments:
      -h, --help            show this help message and exit
      -m MODEL_NAME, --model-name MODEL_NAME
                            Name of model to remove
      --log LOGLEVEL        Loglevel [DEBUG|INFO|WARN|ERROR|CRITICAL]

Example
-------

First, grab the charm in question from the charm store::

    charm pull cs:~openstack-charmers-next/vault
    cd vault

Run tests via tox
~~~~~~~~~~~~~~~~~~

To run all the charms functional tests::

    tox -e func

or just the smoke test::

    tox -e func-smoke

Run tests directly with functest commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Setup the virtualenv needs to be created::

    tox -e func-noop
    source .tox/func-noop/bin/activate

All the phases can be run with a single command for a specific bundle::

    $ functest-run-suite -b xenial-mysql

OR each phase can be run by hand,

Prepare phase::

    $ functest-prepare -m testmodel

Pick a specific bundle to test::

    $ functest-deploy -m testmodel -b tests/bundles/xenial-mysql.yaml

Run the configure script to prepare the environment for running tests::

    $ functest-configure -m testmodel

Run test::

    $ functest-test -m testmodel

Destroy the environment::

    $ functest-destroy -m testmodel 

Run tests directly using model maps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Steps defined in the tests.yaml will often be related to a model alias. For
example::

    charm_name: ubuntu
    tests:
     - bionic_model:
       - zaza.charm_tests.noop.tests.NoopTestBionic
     - xenial_model:
       - zaza.charm_tests.noop.tests.NoopTestXenial
     - zaza.charm_tests.noop.tests.NoopTest
    configure:
     - bionic_model:
       - zaza.charm_tests.noop.setup.basic_setup_bionic
     - xenial_model:
       - zaza.charm_tests.noop.setup.basic_setup_xenial
     - zaza.charm_tests.noop.setup.basic_setup

In the above setup two model aliases are in use: 'bionic_model' and
'xenial_model'. To map an existing model to a model alias (and thereby run
the specific step for the alias) pass in the map to the model command. This is
done by specifying 'alias:existing_model_name'. For example if there is an
existing model called 'bio' then to associate that with 'bionic_model' alias
run::

    $ functest-configure -m bionic_model:bio
    $ functest-test -m bionic_model:bio

Multiple model aliases can also be passed. To run the tests associated with
both aliases::

    $ functest-configure -m bionic_model:bio -m xenial_model:xen
    $ functest-test -m bionic_model:bio -m xenial_model:xen
