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

"""Upload a collection's events to a provider.

This is the main entry point to uploading.
"""

from collections.abc import Iterable, Mapping
import logging

from zaza.global_options import get_option

from .influxdb import upload as upload_influxdb


logger = logging.getLogger(__name__)


def upload_collection_by_config(collection, context=None):
    """Upload a collection's events using a configured set of uploaders.

    :param collection: the collection whose logs to upload.
    :type collection: zaza.events.collection.Collection
    :param context: a context of dictionary keys for filling in values
    :type context: Optional[Dict[str, str]]
    """
    uploads = get_option('zaza-events.upload', [])
    if isinstance(uploads, str):
        uploads = (uploads, )
    if not isinstance(uploads, Iterable):
        logger.error("No where to upload logs? %s", uploads)
        return
    for upload in uploads:
        if not isinstance(upload, Mapping):
            logger.error(
                "Ignoring upload; it doesn't seem correcly formatted?",
                upload)
            continue
        try:
            upload_type = upload['type']
        except KeyError:
            logger.error("No type provided for upload, ignoring: %s",
                         upload)
            continue
        if not isinstance(upload_type, str):
            logger.error("upload type is not a str, ignoring: %s",
                         upload_type)
            continue

        upload_type = upload_type.lower()

        # TODO: this would be nicer as a dict lookup to make it more
        # flexible, but for the moment, we only support InfluxDB
        if upload_type == "influxdb":
            upload_influxdb(upload, collection, context)
        else:
            logger.error("Unknown type %s for uploading; ignoring",
                         upload_type)
