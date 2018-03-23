# Zaza

*A python library for testing OpenStack Charms, and perhaps any Charm.*

### About

One challenge with all legacy charm test tools, is they each blur the lines of function, making it difficult to separate deploy-time helpers from test-execution assertions and such.

The first philosophy of Zaza is to distill all helpers, methods, classes into logical buckets to address the needs of: [prepare, deploy, configure, test, collect, destroy].

### Layout

To recall and resurrect previous notions, and to guide contributors, here is roughly where we see things landing:

#### prepare
 - model foo
 - no controller foo, that is a pre-requisite to zaza usage:  have a controller ready.

#### deploy
 - juju deploy a bundle or a stack of composite bundles, etc.
 - wait logic and helpers

#### configure
 - post-deployment configuration.  add network, tenant, image, etc.
 - any necessary post-deploy actions go here

#### test
 - call tests as declared in the charm test dirs
 - future: wrappers for ceph teuthology, rally, tempest, i/o with the tempest charm, or other test frameworks TBD
 - very little test assertion code would live in zaza directly, unless its a shared test

#### collect
 - juju crashdump and/or lolo logpuller redeaux
 - any other artifact/log collection needed

#### destroy
 - always destroy the model, unless some sort of dont-destroy bit is set
 - never destroy the controller
