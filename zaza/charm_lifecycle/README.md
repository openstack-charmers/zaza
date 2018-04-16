# Enabling Charm Functional Tests with Zaza

The end-to-end tests of a charm are divided into distinct phases. Each phase
can be run in isolation and tests shared between charms.

# Running a suite of deployments and tests

**functest-run-suite** will read the charms tests.yaml and execute the
deployments and tests outlined there. However, each phase can be run
independently.

## Charm Test Phases

Charms should ship with bundles that deploy the charm with different
application versions, topologies or config options.  functest-run-suite will
run through each phase listed below in order for each bundle that is to be
tested.

### 1) Prepare

Prepare the environment ready for a deployment. At a minimum create a model
to run the deployment in.

To run manually:

```
$ functest-prepare --help
usage: functest-prepare [-h] -m MODEL_NAME

optional arguments:
  -h, --help            show this help message and exit
  -m MODEL_NAME, --model-name MODEL_NAME
                        Name of new model
```

### 2) Deploy

Deploy the target bundle and wait for it to complete. **functest-run-suite** 
will look at the list of bundles in the tests.yaml in the charm to determine
the bundle.

In addition to the specified bundle the overlay template directory will be
searched for a corresponding template (\<bundle\_name\>.j2). If one is found
then the overlay will be rendered using environment variables matching
AMULET\* or ZAZA_TEMPLATE\* as a context. The rendered overlay will be used on
top of the specified bundle at deploy time.

To run manually:

```
$ functest-deploy --help
usage: functest-deploy [-h] -m MODEL -b BUNDLE [--no-wait]

optional arguments:
  -h, --help            show this help message and exit
  -m MODEL, --model MODEL
                        Model to deploy to
  -b BUNDLE, --bundle BUNDLE
                        Bundle name (excluding file ext)
  --no-wait             Do not wait for deployment to settle
```

### 3) Configure

Post-deployment configuration, for example create network, tenant, image, etc.
Any necessary post-deploy actions go here. **functest-run-suite** will look 
for a list of functions that should be run in tests.yaml and execute each
in turn.

To run manually:

```
 functest-configure --help
usage: functest-configure [-h] [-c CONFIGFUNCS [CONFIGFUNCS ...]]

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIGFUNCS [CONFIGFUNCS ...], --configfuncs CONFIGFUNCS [CONFIGFUNCS ...]
                        Space sperated list of config functions
```

### 4) Test

Run tests. These maybe tests in zaza or a wrapper around another testing
framework like rally or tempest.  **functest-run-suite** will look for a list
of test classes that should be run in tests.yaml and execute each in turn.

To run manually:

```
usage: functest-test [-h] [-t TESTS [TESTS ...]]

optional arguments:
  -h, --help            show this help message and exit
  -t TESTS [TESTS ...], --tests TESTS [TESTS ...]
                        Space sperated list of test classes
```

### 5) Collect

Collect artifacts useful for debugging any failures or useful for trend
analysis like deprecation warning or deployment time.


### 6) Destroy

Destroy the model.

```
functest-destroy --help
usage: functest-destroy [-h] -m MODEL_NAME

optional arguments:
  -h, --help            show this help message and exit
  -m MODEL_NAME, --model-name MODEL_NAME
                        Name of model to remove
```

# Enabling zaza tests in a charm


 * Add zaza in the charms test-requirements.txt
 * tox.ini should include a target like:

```
[testenv:func]
basepython = python3
commands =
    functest-run-suite --keep-model

[testenv:func-smoke]
basepython = python3
commands =
    functest-run-suite --keep-model --smoke
```

 * Bundles which are to be used for the tests:

```
tests/bundles/base-xenial.yaml
tests/bundles/base-xenial-ha.yaml
tests/bundles/base-bionic.yaml
```

 * Bundle overlay templates

```
tests/bundles/overlays/xenial-ha-mysql.yaml.j2
```

 * A tests/tests.yaml file that describes the bundles to be run and
   the tests

```
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
```

# Adding tests to zaza

The setup and tests for a charm should live in zaza, this enables the code to
be shared between multiple charms. To add support for a new charm create a
directory, named after the charm, inside **zaza/charm_tests**. Within the new
directory define the tests in **tests.py** and any setup code in **setup.py**
This code can then be referenced in the charms **tests.yaml**

eg to add support for a new congress charm create a new directory in zaza

```
mkdir zaza/charm_tests/congress
```

Add setup code into setup.py

```
$ cat zaza/charm_tests/congress/setup.py
def basic_setup():
    congress_client(run_special_setup)
```

Add test code into tests.py

```
class CongressTest(unittest.TestCase):

    def test_policy_create(self):
        policy = congress.create_policy()
        self.assertTrue(policy)
```

These now need to be refenced in the congress charms tests.yaml. Additional
setup is needed to run a useful congress tests, so congress' tests.yaml might
look like:

```
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
```
