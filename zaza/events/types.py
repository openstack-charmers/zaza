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

"""Types for logging."""

import enum
import itertools

from zaza.notifications import NotifyEvents


class LogFormats:
    """Format default types."""

    CSV = 'CSV'
    LOG = 'LOG'
    InfluxDB = 'InfluxDB'


# Events that are standardised.

class _Events(enum.Enum):
    """zaza.events as an enum for type safety.

    Note: as this class is derivied from zaza.notifications.NotifyEvents it
    also has those events as well.
    """

    # Core events
    START_TEST = "start"
    COMMENT = "comment"
    EXCEPTION = "exception-in-span"
    END_TEST = "end"


# Enums can't be extended, so we use this little trick.
Events = enum.Enum('Events', [(i.name, i.value)
                              for i in itertools.chain(NotifyEvents, _Events)])


class Span(enum.Enum):
    """Span possibilities."""

    BEFORE = "before"
    WITHIN = "within"
    AFTER = "after"


# Meaning of the fields:
#    'collection' - the collection (loosely measurement in InfluxDB parlance)
#    'timestamp'  - the timestamp
#    'event'      - the event (from :class:`Events` above)
#    'span'       - either before, after, or absent - used for spans
#    'unit'       - the unit 'DEFAULT' is typically zaza tests.
#    'item'       - the item - test dependent (e.g. could be a juju unit name)
#    'comment'    - a comment field
#    'tags'       - any additional tags that are of interest.
#    'uuid'       - used to pair up/collect common sequences of events.

FIELDS = (
    'collection',
    'timestamp',
    'event',
    'span',
    'unit',
    'item',
    'comment',
    'tags',
    'uuid',
)
