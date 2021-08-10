# Copyright 2021 Canonical Ltd.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Manage uploading events to InfluxDB."""

import itertools
import logging

import requests

from zaza.utilities import expand_vars


logger = logging.getLogger(__name__)


def upload(upload_spec, collection, context=None):
    """Upload a collection of events to an InfluxDB instance.

    This uses a POST to upload data to a named database at a URL with a
    particular timestamp-resolution.  If present, the user and password are
    used to do the upload.  A batch size of events is also used.  Events
    have to be in InfluxDB Line Protocol format, in the collection.

        type: InfluxDB
        url: ${INFLUXDB_URL}
        user: ${INFLUXDB_USER}
        password: ${INFLUXDB_PASSWORD}
        database: charm_upgrade
        timestamp-resolution: us
        batch-size: 1000
        raise-exceptions: false

    Note that this won't generate an exception (e.g. there's no database,
    etc.), unless raise-exceptions is true.  It will just log to the file.

    Note that the timestamp-resolution is one of: ns, us, ms, s.

    The line protocol for 1.8 is one of n, u, ms, s, m, h.  Thus, this
    function maps ns -> n, and us -> u as part of the upload.  m and h are
    not supported.

    :param upload_spec: the upload specification of where to send the logs.
    :type upload_spec: Dict[str, str]
    :param collection: the collection whose logs to upload.
    :type collection: zaza.events.collection.Collection
    :param context: a context of dictionary keys for filling in values
    :type context: Optional[Dict[str, str]]
    """
    assert upload_spec['type'].lower() == "influxdb"
    raise_exceptions = upload_spec.get('raise-exceptions', False)
    user = upload_spec.get('user', None)
    password = upload_spec.get('password', None)
    timestamp_resolution = upload_spec.get('timestamp-resolution', 'u')
    batch_size = upload_spec.get('batch-size', 1000)
    if context is None:
        context = {}

    try:
        url = upload_spec['url']
    except KeyError:
        logger.error("No url supplied to upload for InfluxDB.")
        if raise_exceptions:
            raise
        return
    try:
        database = upload_spec['database']
    except KeyError:
        logger.error("No database supplied to upload for InfluxDB.")
        if raise_exceptions:
            raise
        return

    url = expand_vars(context, url)
    database = expand_vars(context, database)

    # map the precision to InfluxDB.
    try:
        precision = {'ns': 'n',
                     'us': 'u',
                     'ms': 'ms',
                     's': 's'}[timestamp_resolution]
    except KeyError:
        logger.error("Precision isn't one of ns, us, ms or s: %s",
                     timestamp_resolution)
        if raise_exceptions:
            raise
        return

    if not url.endswith("/"):
        url = "{}/".format(url)
    post_url = "{}write?db={}&precision={}".format(
        url, database, precision)
    if user:
        post_url = "{}&u={}".format(post_url, expand_vars(context, user))
    if password:
        post_url = "{}&p={}".format(post_url, expand_vars(context, password))

    # Now got all the possible information to be able to do the uplaods.
    logger.info(
        "Starting upload to InfluxDB, database: %s, user: %s, "
        "precision: %s, batch_size: %s",
        database, user, timestamp_resolution, batch_size)

    with collection.events(precision=timestamp_resolution) as events:
        while True:
            batch_events = itertools.islice(events, batch_size)
            batch = "\n".join(b[1] for b in batch_events)
            if not batch:
                break
            # Essentially: curl -i -XPOST 'http://172.16.1.95:8086/write?
            #               db=mydb&precision=u' --data-binary @batch.logs
            try:
                result = requests.post(post_url, data=batch)
            except Exception as e:
                logger.error("Error raised when uploading batch: %s",
                             str(e))
                if raise_exceptions:
                    raise
                return
            if result.status_code not in (requests.codes.ok,
                                          requests.codes.no_content,
                                          requests.codes.accepted):
                logger.error(
                    "Batch upload failed.  status_code: %s",
                    result.status_code)
                if raise_exceptions:
                    result.raise_for_status()
                logger.error("Abandoning batch upload to InfluxDB")
                return

    logger.info(
        "Finished upload to InfluxDB, database: %s, user: %s, "
        "precision: %s, batch_size: %s",
        database, user, timestamp_resolution, batch_size)
