Enabling zaza tests in a charm
==============================

Update requirements and tox
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add zaza in the charms test-requirements.txt::

    git+https://github.com/openstack-charmers/zaza.git#egg=zaza


Add targets to tox.ini should include a target like::

    [testenv:func]
    basepython = python3
    commands =
        functest-run-suite --keep-model

    [testenv:func-smoke]
    basepython = python3
    commands =
        functest-run-suite --keep-model --smoke

Add Bundles
~~~~~~~~~~~

The bundles live in tests/bundles of the built charm, eg::

    tests/bundles/xenial.yaml
    tests/bundles/xenial-ha.yaml
    tests/bundles/bionic.yaml


The bundle may include overlay templates which are, currently, populated from
environment variables. For example the xenial-ha template needs a VIP but
the VIP will depend on the setup of the juju provider so will be different
between test environments. To accommodate this an overlay is added::

    tests/bundles/overlays/xenial-ha.yaml.j2

The overlay is in jinja2 format and the variables correspond to environment
variables::

    applications:
      vault:
        options:
            vip: '{{ OS_VIP00 }}'

It is also possible to provide overlay templates tailored for specific juju
provider types, this can be useful to do any provider specific morphing of
a bundle. To use this feature use the following directory layout::

    tests/bundles/overlays/xenial.yaml.j2
    tests/bundles/overlays/lxd/xenial.yaml.j2

With the above directory layout the overlay template in the lxd sub-directory
will be used when tests are executed with juju on a LXD provider and the
overlay template in the top level directory will be used for any other
provider types.

Bundle templates can be placed in the `tests/bundles` directory. It is usually
preferable to use overlay templates rather than bundle templates. Overlays
can be used to neatly capture settings that a user might want to change
on a per-cloud basis. However, if a bundle template is required place it
in tests/bundles with a `j2` extension.

Add tests.yaml
~~~~~~~~~~~~~~

A tests/tests.yaml file that describes the bundles to be run and the tests::

    charm_name: vault
    tests:
      - zaza.charm_tests.vault.VaultTest
    configure:
      - zaza.charm_tests.vault.setup.basic_setup
    gate_bundles:
      - base-xenial
      - base-bionic
    dev_bundles:
      - base-xenial-ha
    smoke_bundles:
      - base-bionic

When deploying zaza will wait for the deployment to settle and for the charms
to display a workload status which indicates that they are ready. Sometimes
one or more of the applications being deployed may have a non-standard workload
status target state or message. To inform the deployment step what to
wait for an optional target\_deploy\_status stanza can be added::

    target_deploy_status:
      vault:
        workload-status: blocked
        workload-status-message: Vault needs to be initialized
      ntp:
        workload-status-message: Go for it

Adding tests to zaza
~~~~~~~~~~~~~~~~~~~~

The setup and tests for a charm should live in zaza, this enables the code to
be shared between multiple charms. To add support for a new charm create a
directory, named after the charm, inside **zaza/charm_tests**. Within the new
directory define the tests in **tests.py** and any setup code in **setup.py**
This code can then be referenced in the charms **tests.yaml**

e.g. to add support for a new congress charm create a new directory in zaza::

    mkdir zaza/charm_tests/congress

Add setup code into setup.py::

    $ cat zaza/charm_tests/congress/setup.py
    def basic_setup():
        congress_client(run_special_setup)

Add test code into tests.py::

    class CongressTest(unittest.TestCase):

        def test_policy_create(self):
            policy = congress.create_policy()
            self.assertTrue(policy)

These now need to be referenced in the congress charms tests.yaml. Additional
setup is needed to run a useful congress tests, so congress' tests.yaml might
look like::

    charm_name: congress
    configure:
      - zaza.charm_tests.nova.setup.flavor_setup
      - zaza.charm_tests.nova.setup.image_setup
      - zaza.charm_tests.neutron.setup.create_tenant_networks
      - zaza.charm_tests.neutron.setup.create_ext_networks
      - zaza.charm_tests.congress.setup.basic_setup
    tests:
      - zaza.charm_tests.keystone.KeystoneBasicTest
      - zaza.charm_tests.congress.CongressTest
    gate_bundles:
      - base-xenial
      - base-bionic
    dev_bundles:
      - base-xenial-ha

Deploying bundles using --force
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to allow early testing of new Ubuntu series the `juju deploy` command
has a `--force` option.  This allows deployment of charms that don't specify
the series being used, or for a new series that juju doesn't support yet.

Force deploying can be achieved in two ways, either on the command line, or via
an `tests_options.force_deploy` entry in the `tests.yaml` file.

For the command line a `--force` param is provided:

    functest-run-suite --keep-model --dev --force
    functest-deploy <other options> --force

In the `tests.yaml` the option is added as a list item:

    charm_name: keystone
    smoke_bundles:
    - focal-ussuri

    ...

    tests_options:
      force_deploy:
        - focal-ussuri

In the above case, focal-ussuri will be deployed using the --force parameter.
i.e. the `tests_options.force_deploy['focal-ussuri']` option applies to the
`focal-ussuri` bundle whether it appears in any of the bundle sections.

Augmenting behaviour of configure steps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Individual configuration steps or the library helper they use may define
configuration step options that you may use to tweak behaviour from tests.yaml.

An example is the Neutron `basic_overcloud_network` configure job which for
compatibility with existing scenario tests makes use of `juju_wait` when
configuring the deployed cloud.

This does not work well if the model you are testing has applications with
non-standard workload status messaging.

To replace the use of `juju_wait` with Zaza's configurable wait code:

    charm_name: neutron-openvswitch
    smoke_bundles:
    - focal-ussuri-dvr-snat-migrate-ovn

    ...

    configure_options:
      configure_gateway_ext_port_use_juju_wait: false
