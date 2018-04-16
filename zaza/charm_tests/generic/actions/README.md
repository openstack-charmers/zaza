# Testing your charm actions with zaza generic action test harness

## Simple action tests
To test charm actions your `tests.yaml` may look like this:
```
charm_name: hello-zaza
tests:
  - zaza.charm_tests.generic.actions
```

By default the test will list your charm actions, run them and check for
successfull result.

If your charm has actions that require parameters the default test mode will
produce a test failure.  This is by design to force such actions to have
tailored test setups.

## Advanced action tests
For some charms it may be necessary to have more advanced tests. The actions
may need to be run in a particular order, with specific parameters or it may
be important to check for a specific result.

This can be accomplished with the generic actions test harness by providing
this information in the `tests.yaml`.

Advanced charm actions test example:
```
charm_name: hello-zaza
tests:
  - zaza.charm_tests.generic.actions:
    - hello-action1: {parameterA: valueA, parameterB: valueB}
      expectSuccess: response
    - hello-action2:
      expectFailure: response
```
