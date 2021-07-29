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

"""namespace file for zaza.events.plugin."""


from zaza.utilities import ConfigurableMixin


class PluginManagerBase(ConfigurableMixin):
    """Base class for communicating plugins to the Collection class."""

    def __init__(self, managed_name="DEFAULT", **kwargs):
        """Initialise the PluginManager base.

        Every plugin must have a managed_name, which is the plugin thing being
        managed.  By default, there is always a "DEFAULT" managed item that is
        being used.

        The Collection will also configure the collection name and the logs_dir
        when the Plugin is added to the collection.

        :param managed_name: the name of the thing being managed.
        :type managed_name: str
        """
        self.managed_name = managed_name
        self.collection_object = None
        self.configure(**kwargs)

    def configure_plugin(self):
        """Configure the plugin to work with the Collection.

        This is caused as a consequence of the .add_source() method on the
        collection.  It provides the plugin with the opportunity to configure
        the plugin (and what it manages).  e.g. to open log files, configure
        resources, etc.

        The 'collection_object' value will be set (via a configure() call prior
        to this call).

        The properties 'collection', 'logs_dir' and 'log_format' will be set up
        by this stage.
        """
        raise NotImplementedError()

    @property
    def collection(self):
        """Return the collection.

        :returns: the Collection that 'owns' this pluyin.
        :rtype: zaza.events.Collection
        """
        return self.collection_object.collection

    @property
    def logs_dir(self):
        """Return the optional logs_dir.

        :returns: the directory where logs can be placed. Owned/managed by the
            collection.
        :rtype: Path
        """
        return self.collection_object.logs_dir

    @property
    def log_format(self):
        """Return the format for the collection.

        :returns: the format of the logs from the whole collection, one of
            zaza.events.formats.LogFormats
        :rtype: str
        """
        return self.collection_object.log_format

    def finalise(self):
        """Override this method; finalise the logger, collect logs.

        This functions purpose is to:

         - finalise/stop/flush logs to any associated log files.
         - ensure that they are accessible; probably by copying to the local
           machine.
         - shutdown, clean-up, any activity on instances, etc.
         - gather all associated log files.
        """
        raise NotImplementedError()

    def log_files(self):
        """Return the list (or iterator) of log files.

        :returns: A list/iterator of tuples of (name, filename)
        :rtype: Iterator[Tuple[str, str]]
        """
        raise NotImplementedError()

    def clean_up(self):
        """Clean-up any log files, resources, etc."""
        raise NotImplementedError()
