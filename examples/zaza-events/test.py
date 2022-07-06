#!/usr/bin/env python3

# This is an example of how to use zaza.events.collection.Collection outside of
# the zaza tests.yaml integration.  The key concepts here are:
#
# - Use the collection to combine events logged here, and with the ConnCheck
#   dataplane testing module.
# - Stream the events to a file.  Note that it's possible to also use the
# - zaza.events.uploaders.influxdb.upload() directly to upload the events to a
#   InfluxDB database.
#
# Note it is *much* easier to use the built in zaza integration if deploying
# models and running tests against them.

import asyncio
import logging
import os
import pathlib
import time

import zaza
import zaza.events
from zaza.events import Events
import zaza.events.plugins.logging
import zaza.events.plugins.conncheck

rootLogger = logging.getLogger()
rootLogger.setLevel(logging.INFO)

pathlib.Path('/tmp/collection').mkdir(parents=True, exist_ok=True)

collection = zaza.events.get_collection()
collection.configure(collection="abc-collection", description="a test",
                     logs_dir="/tmp/collection")

logging_manager = zaza.events.plugins.logging.get_plugin_manager()

collection.add_logging_manager(logging_manager)

# add stdout logging of the logs
zaza.events.plugins.logging.add_stdout_to_logger()

events = logging_manager.get_event_logger_instance()
events.log(Events.START_TEST, comment="hello")

# Add a ConnCheck data-plane source.
conncheck_manager = zaza.events.plugins.conncheck.get_plugin_manager()
# Note that this sets the collection on the conncheck_manager instance.
collection.add_logging_manager(conncheck_manager)

# Set the source for the conncheck library; download it first!
conncheck_source = (
    "file:/home/ubuntu/git/github.com/openstack-charmers/"
    "conncheck")
conncheck_manager.configure(module_source=conncheck_source)
assert conncheck_manager.manager.module_source == conncheck_source

# let's add some instances
apps = zaza.model.sync_deployed()
assert 'ubuntu' in apps
app = 'ubuntu'
instances = [
    conncheck_manager.add_instance("juju:{}".format(unit.name))
    for unit in sorted(zaza.model.get_units(app), key=lambda m: m.name)]

# One listener, one http sender
instances[0].add_listener('udp', 8080)
instances[1].add_speaker('udp', 8080, instances[0])

# start them speaking.
with events.span("Configure ConnCheck instances"):
    for instance in instances:
        instance.start()

# let's do the conncheck logging
# with events.block("ConnCheck logging") as block:

for n in range(10):
    print("Sleeping for 5 seconds: {}".format(n))
    time.sleep(5)

with events.span("Finalise ConnCheck instances"):
    for instance in instances:
        instance.finalise()

# And let's clean-up the logs and then just write them to the log.  Now
# gather all the stuff together, flush, close logs, and collect them.
events.log(Events.END_TEST, comment="Test ended")
collection.finalise()

# Access all the log files:
for (name, type_, filename) in collection.log_files():
    print("Collect logs for {} type({}) {}".format(name, type_, filename))

# stream the events to the log.
with open("combined.logs", "wt") as f:
    with collection.events(precision="us") as events:
        for event in events:
            print(event[1], file=f)

# and really just clean-up now.
collection.clean_up()

zaza.clean_up_libjuju_thread()
# Deal with [1] in Python3.5
# [1] https://bugs.python.org/issue28628
asyncio.get_event_loop().close()
