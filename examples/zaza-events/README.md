# zaza-events example

The enclosed example in `test.py` shows how to use zaza.events outside of the
zaza framework.

This is an example of how to use zaza.events.collection.Collection outside of
the zaza tests.yaml integration.  The key concepts here are:

  - Use the collection to combine events logged here, and with the ConnCheck
    dataplane testing module.
  - Stream the events to a file.  Note that it's possible to also use the
  - zaza.events.uploaders.influxdb.upload() directly to upload the events to a
    InfluxDB database.

Note it is *much* easier to use the built in zaza integration if deploying
models and running tests against them.
