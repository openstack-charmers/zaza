#!/usr/bin/env python3

# TODO move this to an example usage of the Collection events module

import asyncio
import logging
import os
import pathlib
import time

import zaza.events
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

events = logging_manager.get_logger()
events.log(zaza.events.START_TEST, comment="hello alex")
events.log(zaza.events.COMMENT, comment="test sleeping for 120 seconds")
events.log(zaza.events.END_TEST, comment="Test ended")

# Add a ConnCheck data-plane source.
conncheck_manager = zaza.events.plugins.conncheck.get_plugin_manager()
# Note that this sets the collection on the conncheck_manager instance.
collection.add_logging_manager(conncheck_manager)

# Hack for my stuff
# use a directory for conncheck
home = os.path.expandvars("$HOME")
if home == "/home/alex":
    conncheck_source = (
        "file:/home/alex/Projects/Canonical/git/github.com/openstack-charmers/"
        "conncheck")
else:
    conncheck_source = (
        "file:/home/ubuntu/git/github.com/openstack-charmers/"
        "conncheck")
conncheck_manager.configure(module_source=conncheck_source)
print(conncheck_manager.module_source)
print(conncheck_manager.manager.module_source)
assert conncheck_manager.manager.module_source == conncheck_source

# let's add some instances
apps = zaza.model.sync_deployed()
assert 'ubuntu' in apps
app = 'ubuntu'
instances = [
    conncheck_manager.add_instance("juju:{}".format(unit.name))
    for unit in sorted(zaza.model.get_units(app), key=lambda m: m.name)]

# put a UDP and HTTP listener on each unit.
# This automatically installs the Conncheck module on each instance.
for instance in instances:
    instance.add_listener('udp', 8081)
    instance.add_listener('http', 8080)

# add UDP and HTTP speakers to each of the other units in a circle
num_instances = len(instances)
for i, instance in enumerate(instances):
    next_instance = instances[(i + 1) % num_instances]
    instance.add_speaker('udp', 8081, next_instance)
    instance.add_speaker('http', 8080, next_instance)
# start them speaking.
events.log(zaza.events.COMMENT,
           comment="ConnCheck instances configuring")
for instance in instances:
    instance.start()
events.log(zaza.events.COMMENT,
           comment="ConnCheck configured")

# let's do the conncheck logging
# with events.block("ConnCheck logging") as block:

for n in range(10):
    print("Sleeping for 5 seconds: {}".format(n))
    time.sleep(5)

for instance in instances:
    instance.stop()

# And let's clean-up the logs and then just write them to the log.  Now
# gather all the stuff together, flush, close logs, and collect them.
collection.finalise()

# Access all the log files:
for (name, type_, filename) in collection.log_files():
    print("Collect logs for {} type({}) {}".format(name, type_, filename))

# stream the events to the log.
with open("combined.logs", "wt") as f:
    with collection.events(precision="us") as events:
        for event in events:
            print(event)
            print(event[1], file=f)

# and really just clean-up now.
collection.clean_up()

# Deal with [1] in Python3.5
# [1] https://bugs.python.org/issue28628
asyncio.get_event_loop().close()
