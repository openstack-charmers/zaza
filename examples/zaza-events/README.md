# zaza-events example

## Framework example

The directory `tests-extended/tests.yaml` provides an example of zaza-events
using 2 Ubuntu units in a very small bundle.  The bundle is:

```yaml
series: focal
applications:
  ubuntu:
    charm: cs:ubuntu
    num_units: 2
```

The `tests.yaml` for this bundle are:

```yaml
charm_name: none
gate_bundles:
- conncheck-focal

target_deploy_status:
  ubuntu:
    workload-status-message-regex: "^$"

tests:
- zaza.charm_tests.conncheck.tests.TestConncheckIntegration

tests_options:
  plugins:
    - zaza.plugins.events.configure
  zaza-events:
    log-format: InfluxDB
    keep-logs: false
    collection-name: DEFAULT
    collection-description: ""
    raise-exceptions: true
    log-collection-name: "testdb-{bundle}-{date}"
    modules:
      - conncheck:
          source: "git+http://github.com/openstack-charmers/conncheck"
          raise-exceptions: true
      - logging:
          logger-name: DEFAULT
          log-to-stdout: false
          log-to-python-logging: true
          python-logging-level: info
          logger-name: DEFAULT
          raise-exceptions: true
    upload:
      - type: InfluxDB
        url: ${TEST_INFLUXDB_URL}
        # user: ${TEST_INFLUXDB_USER}
        # password: ${TEST_INFLUXDB_PASSWORD}
        database: testdb
        timestamp-resolution: ns
```


This assumes that there is an InfluxDB available at the enviroment varaible
`${TEST_INFLUXDB_URL}` to upload the records to.


The actual test is specified in `zaza/charm_tests/conncheck/tests.py`.

The test can be launched by:

```bash
$ tox -e func-target-extended -- conncheck-focal
```

This will:

1. Deploy a model with 2 focal ubuntu units.
2. Install the [ConnCheck](https://github.com/openstack-charmers/conncheck)
   module on each of the instances.
3. Set a UDP listener on the first instance.
4. Set a UDP speaker on the 2nd instance.
5. Let them run for a while
6. Reboot the listener, so that the speaker doesn't get any replies.
7. Wait a while.
8. Finalise all the logs
9. Upload the events as a whole to the InfluxDB database.


## Non Framework example

The enclosed example in the same directory as this file, `test.py`, shows how
to use zaza.events outside of the zaza framework.

This is an example of how to use zaza.events.collection.Collection outside of
the zaza tests.yaml integration.  The key concepts here are:

  - Use the collection to combine events logged here, and with the ConnCheck
    dataplane testing module.
  - Stream the events to a file.  Note that it's possible to also use the
  - zaza.events.uploaders.influxdb.upload() directly to upload the events to a
    InfluxDB database.

Note it is *much* easier to use the built in zaza integration if deploying
models and running tests against them.
