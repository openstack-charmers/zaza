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

"""Manage a ConnCheck set of data-plane checkers.

The basic problem being solved here is:

 1. How to configure and install a ConnCheck module on an instance.
 2. Finalise a test (i.e. removing an instance)
 3. Getting and finalising the log files for that instance.

The metadata for a single ConnCheck instance is:

 - instance name
 - speakers
 - listeners

A single ConnCheck has multiple instances.  Each has configuration for what it
needs to connect to.
"""

from enum import Enum
import collections
import logging
import os
import re
import subprocess
import tempfile
import yaml

from zaza.events.plugins import PluginManagerBase
from zaza.events.formats import LogFormats
from zaza.utilities import ConfigurableMixin
import zaza.utilities.installers


_conncheck_plugin_managers = dict()


def get_plugin_manager(name="DEFAULT"):
    """Return the Collection Plugin manager for conncheck logging.

    :param name: the name of the conncheck manager to be associated with
        the plugin.
    :type name: str
    :returns: the conncheck plugin manager
    :rtype: LoggerPluginManager
    """
    global _conncheck_plugin_managers
    try:
        return _conncheck_plugin_managers[name]
    except KeyError:
        _conncheck_plugin_managers[name] = ConnCheckPluginManager(
            managed_name=name)
        return _conncheck_plugin_managers[name]


class ConnCheckPluginManager(PluginManagerBase):
    """Manage a ConnCheckManager as part of a Collection.

    Note that the ConnCheckManager is not a Plugin so that it can be used
    independently of a Collection.
    """

    def __init__(self, managed_name="DEFAULT", **kwargs):
        """Initialise the ConnCheckPluginManager base.

        Every plugin must have a managed_name, which is the plugin thing being
        managed.  By default, there is always a "DEFAULT" managed item that is
        being used.

        The Collection will also configure the collection name and the logs_dir
        when the Plugin is added to the collection.

        :param kwargs: attribute=value pairs for configuring the plugin.
        :type kwargs: Dict[str, Any]
        :param managed_name: the name of the thing being managed.
        :type managed_name: str
        """
        self.module_source = None
        self.tags = None
        self._conncheck_manager = None
        super().__init__(managed_name=managed_name, **kwargs)
        self._conncheck_manager = ConnCheckManager()

    def configure(self, **kwargs):
        """Configure the plugin.

        This calls the parent configure() function to configure the public
        attributes of the class, and if the wrapped ConnCheckManager is set,
        then calls configure_plugin() on that to ensure that the wrapped
        manager gets to see the attributes that may have been changed.

        :param kwargs: attribute=value pairs
        :type kwargs: Dict[str, Any]
        """
        super().configure(**kwargs)
        if self._conncheck_manager is not None:
            # update the wrapped manager with any changes.
            self.configure_plugin()

    def configure_plugin(self):
        """Configure the ConnCheckManager plugin.

        This configures the container ConnCheckManager, which is also derived
        from ConfigurableMixin.
        """
        self.manager.configure(
            collection=self.collection,
            logs_dir=self.logs_dir,
            module_source=self.module_source,
            tags=self.tags)

    @property
    def manager(self):
        """Return the container conncheck manager.

        :returns: the wrapped ConnCheckManager
        :rtype: ConnCheckManager
        :raises AssertionError: if the manager is not set-up yet.
        """
        assert self._conncheck_manager is not None
        return self._conncheck_manager

    def add_instance(self, spec, **kwargs):
        """Add an instance according to the spec.

        This just calls the ConnCheckManager.add_instance method.
        """
        return self.manager.add_instance(spec, **kwargs)

    def get_instance(self, spec):
        """Get an ConnCheckInstanceBase derived instance.

        This calls the ConnCheckManager.get_instance method.
        """
        return self.manager.get_instance(spec)

    def start(self, spec=None):
        """Start the instances in the ConnCheckManager."""
        self.manager.start(spec)

    def stop(self, spec=None):
        """Stop the instances in the ConnCheckManager."""
        self.manager.stop(spec)

    def finalise(self):
        """Stop all the instances and consolidate all the logs."""
        self.manager.finalise()

    def log_files(self):
        """Return the log files from the instances in the ConnCheckManager."""
        return self.manager.log_files()

    def clean_up(self):
        """Call the clean_up method on the ConnCheckManager."""
        self.manager.clean_up()


class ConnCheckManager(ConfigurableMixin):
    """Manage a ConnCheck set of instances."""

    _spec_handlers = {}

    def __init__(self, **kwargs):
        """Create a new ConnCheck modules.

        sources for conncheck module:

         * conncheck (default)
         * <other> pip installable spec (e.g. git+https://...
         * file:<path locally>
        """
        super().__init__(**kwargs)
        self.collection = None
        self.logs_dir = None
        self.tags = None
        self.module_source = "conncheck"
        self.configure(**kwargs)
        self._finalised = False
        self._instances = collections.OrderedDict()
        self._log_files = collections.OrderedDict()

    def add_instance(self, spec, **kwargs):
        """Add an instance to the manager.

        The :paramref:`spec` determines what kind of instance it is.
        Currently, ConnCheckManager can work with a juju unit or a juju machine
        or a ssh address.  The spec is defined as:

        - juju:nova-compute/0
        - juju:0
        - juju:0/lxd/4
        - ssh:192.168.1.0

        The keyword args depend on type of instance.

        :param spec: the spec for the instance.
        :type spec: str
        :param kwargs: key=value pairs to configure an instance
        :returns: an instance
        :rtype: ConnCheckInstanceBase derived class.
        :raises: RuntimeError if an spec already exists.
        """
        if spec in self._instances:
            raise RuntimeError("Instance {} already added.".format(spec))
        if 'module_source' not in kwargs:
            kwargs['module_source'] = self.module_source
        if 'collection' not in kwargs:
            kwargs['collection'] = self.collection
        instance = self.make_instance_with(spec, **kwargs)
        self._instances[spec] = instance
        return instance

    def get_instance(self, spec):
        """Return the instance for the spec.

        :param spec: the specification of the instance (e.g. machine ssh:addr)
        :type spec: str
        :returns: the instance associated with the spec.
        :rtype: ConnCheckInstanceBase
        :raises KeyError: if no instance belonging to the spec exists.
        """
        return self._instances[spec]

    def start(self, spec=None):
        """Start all or a specified instance.

        :param spec: optional single instance to start.
        :type spec: Optional[str]
        :raises: KeyError if spec doesn't exist (and is specified).
        """
        if spec is None:
            instances = self._instances.values()
        else:
            instances = [self.get_instance(spec)]
        for instance in instances:
            instance.start()

    def stop(self, spec=None):
        """Stop all or a specified instance.

        :param spec: optional single instance to start.
        :type spec: Optional[str]
        :raises: KeyError if spec doesn't exist (and is specified).
        """
        if spec is None:
            instances = self._instances.values()
        else:
            instances = [self.get_instance(spec)]
        for instance in instances:
            instance.stop()

    def finalise(self):
        """Finalise all the instances.

        Finalising an instance means that it should stop activity, close its
        log files and then exit.
        """
        if self._finalised:
            return
        self.stop()
        for instance in self._instances.values():
            instance.finalise()
        self._finalised = True

    def log_files(self):
        """Return an iterator of (name, log format, filename).

        :returns: A list/iterator of tuples of (name, log format, filename)
        :rtype: Iterator[Tuple[str, str, str]]
        """
        self.finalise()
        for spec, instance in self._instances.items():
            try:
                yield (spec, instance.log_format, self._log_files[spec])
            except KeyError:
                self._log_files[spec] = instance.get_logfile_to_local(
                    self.logs_dir)
                yield (spec, instance.log_format, self._log_files[spec])

    def clean_up(self):
        """Stop all the instances, and clean-up."""
        self.finalise()

    @classmethod
    def register_spec_handler(cls, spec_root, handler_fn):
        """Register a handler for a spec_root.

        :param spec_root: the spec root the handler handlers.
        :type spec_root: str
        :param handler_fn: the function that takes the spec.
        :type handler_fn: Callable[[str, ...], ConnCheckInstanceBase]
        """
        if spec_root in cls._spec_handlers:
            raise RuntimeError(
                "Spec '{}'/{} already has a handler: {}"
                .format(spec_root, handler_fn, cls._spec_handlers[spec_root]))
        cls._spec_handlers[spec_root] = handler_fn

    def make_instance_with(self, spec, **kwargs):
        """Using the spec root, make a ConnCheckInstanceBase via a handler_fn.

        The strips the first part before the ':' and finds the handler fn and
        then calls it with the reamining spec.

        :param spec: the full spec.
        :type spec: str
        :param kwargs: key=value pairs to configure an instance with.
        :type kwargs: Dict[str, Any]
        :returns: The instance for the spec.
        :rtype: ConnCheckInstanceBase
        :raises ValueError: if the spec doesn't seem to be like a spec.
        :raises KeyError: if the spec type doesn't exist.
        """
        if ':' not in spec:
            raise ValueError("The spec {} doesn't seem to contain a root?"
                             .foramt(spec))
        root, _spec = spec.split(':', 1)
        try:
            handler_fn = self._spec_handlers[root]
        except KeyError:
            raise KeyError("The spec root {} doesn't have a handler."
                           .format(root))
        return handler_fn(_spec, **kwargs)


class ConnCheckInstanceBase(ConfigurableMixin):
    """Class serves as a base for ConnCheckInstance<Root> classes."""

    TYPES = ('udp', 'http')

    def __init__(self, **kwargs):
        """Initialise a ConnCheckInstanceBase.

        The kwargs are used to configure the public attributes of the object
        using the :class:`ConfigurableMixin` class.

        :param kwargs: attribute=value pairs to configure the instance.
        :type kwargs: Dict[str, Any]
        """
        self.name = None
        self.log_format = None
        self.config_file = "config.yaml"
        self.log_file = "conncheck.log"
        self.install_dir = "."
        self.module_source = None
        self.collection = None
        self.install_user = "conncheck"
        self._listeners = {}
        self._speakers = {}
        self._installed = False
        self._ssh_fn = None
        self._scp_fn = None
        self._systemd = None
        self.configure(**kwargs)
        self._conncheck_home_dir_cache = None
        if self.log_format is None:
            self.log_format = LogFormats.InfluxDB

    def _validate_not_existing_listener(self, type_, port):
        """Validate that the (type_, port) combination doesn't already exist.

        :param type_: the type of listener, one of :self:`TYPES`
        :type type_: str
        :param port: the port to listen on.
        :type port: int
        :raises RuntimeError: if the (type_, port) already exists.
        """
        assert type_ in self.TYPES
        id_ = (type_, port)
        if id_ in self._listeners:
            raise RuntimeError("Listener type:{}, port:{} already exists."
                               .format(type_, port))

    def add_listener(self, *args, **kwargs):
        """Add a listener."""
        raise NotImplementedError()

    def add_listener_spec(self, type_, port, address, reply_size=1024):
        """Add a listener to listeners, by spec.

        :param type_: either 'udp' or 'http'
        :type type_: str
        :param address: the address to contact.
        :type address: str
        :param port: the port to connect to.
        :type port: int
        :param reply_size: the size of reply to make, default 1KiB
        :type reply_size: int
        """
        self._validate_not_existing_listener(type_, port)
        id_ = (type_, port)
        name = self.name or self.machine_or_unit_spec
        self._listeners[id_] = {
            'name': "{}:listen:{}:{}:{}".format(name, type_, address, port),
            'ipv4': address,
            'port': port,
            'protocol': type_,
            'reply-size': reply_size,
        }
        self.write_configuration()

    def add_speaker(self, type_, port, instance=None, address=None,
                    wait=5, interval=10, send_size=1024):
        """Add a speaker to an instance.

        The speaker (udp or http) eally does need the address or the instance,
        and the instance needs to know the address it is listening on if no
        address is passed.  Best thing to do is pass an address.

        :param type_: either 'udp' or 'http'
        :type type_: str
        :param port: the port to connect to.
        :type port: int
        :param instance: Optional instance to use for address.
        :type address: Optional[str]
        :param address: Optional address to contact.
        :type address: Optional[str]
        :param wait: The time to wait for a reply
        :type wait: int
        :param interval: The time between send requests.
        :type interval: int
        :param send_size: the size of the send packet (if appropriate)
        :type send_size: int
        :raises ValueError: if the type isn't recognised.
        """
        # need the address of the unit
        if address is None:
            address = self._get_remote_address(instance, type_, port)
        self.add_speaker_spec(type_, port, address, wait=wait,
                              interval=interval, send_size=send_size)

    def _validate_not_existing_speaker(self, type_, address, port):
        """Validate that there isn't already a speaker to address:port.

        :param type_: either 'udp' or 'http'
        :type type_: str
        :param address: the address to contact.
        :type address: str
        :param port: the port to connect to.
        :type port: int
        :raises RuntimeError: if an existing speaker of the same spec exits.
        """
        assert type_ in self.TYPES
        id_ = (type_, address, port)
        if id_ in self._speakers:
            raise RuntimeError("Speaker type:{}, to {}:{} already exists."
                               .format(type_, address, port))

    def add_speaker_spec(self, type_, port, address, wait=5, interval=10,
                         send_size=1024):
        """Add a speaker to the speakers.

        :param type_: either 'udp' or 'http'
        :type type_: str
        :param address: the address to contact.
        :type address: str
        :param port: the port to connect to.
        :type port: int
        :param wait: The time to wait for a reply
        :type wait: int
        :param interval: The time between send requests.
        :type interval: int
        :param send_size: the size of the send packet (if appropriate)
        :type send_size: int
        :raises ValueError: if the type isn't recognised.
        """
        id_ = (type_, address, port)
        self._validate_not_existing_speaker(*id_)
        name = self.name or self.machine_or_unit_spec
        if type_ == 'udp':
            spec = {
                'name': "{}:send:{}:{}:{}".format(name, type_, address, port),
                'ipv4': address,
                'port': port,
                'protocol': type_,
                'send-size': send_size,
                'wait': wait,
                'interval': interval,
            }
        elif type_ == 'http':
            spec = {
                'name': "{}:request:{}:{}:{}".format(
                    name, type_, address, port),
                'url': "http://{}:{}/{{uuid}}".format(address, port),
                'protocol': type_,
                'wait': wait,
                'interval': interval,
            }
        else:
            raise ValueError("Can't write a spec for protocol: {}"
                             .format(type_))
        self._speakers[id_] = spec
        self.write_configuration()

    def _get_remote_address(self, instance, type_, port):
        """Try to get the remote address; raise exception if not possible.

        :param instance: the instance that hopefully has the port and type_
        :type instance: ConnCheckInstanceBase
        :param type_: the type of listener
        :type type_: str
        :param port: the port of the listener to connect to.
        :type port: int
        :returns: the address (or url) for the listener
        :rtype: str
        :raises KeyError: if the (type_, port) doesn't exist.
        """
        id_ = (type_, port)
        return instance._listeners[id_]['ipv4']

    @property
    def _conncheck_home_dir(self):
        """Get the home directory of the conncheck user on the instance.

        Note that it is cached.  This shouldn't present an issue as the
        directory should stay the same once the home directory is created.

        :returns: the home directory of the conncheck user.
        :rtype: str
        """
        if self._conncheck_home_dir_cache:
            return self._conncheck_home_dir_cache
        self._conncheck_home_dir_cache = (
            zaza.utilities.installers.user_directory(
                self._ssh_fn, "conncheck"))
        return self._conncheck_home_dir_cache

    def install(self):
        """Install the module on the unit.

        This uses the instance variable `module_source` (which can be
        configured using configure() or at the instantiation of the object) to
        install the module onto the unit.
        """
        # ensure the conncheck user exists.
        if not zaza.utilities.installers.user_exists(
                self._ssh_fn, "conncheck"):
            conncheck_home_dir = zaza.utilities.installers.create_user(
                self._ssh_fn, "conncheck")
        else:
            conncheck_home_dir = self._conncheck_home_dir
        if not self.install_dir.startswith("/"):
            destination = os.path.join(conncheck_home_dir, self.install_dir)
        else:
            destination = self.install_dir
        zaza.utilities.installers.install_module_in_venv(
            self.module_source, destination, self._scp_fn, self._ssh_fn,
            run_user="conncheck")
        systemd_cmd = (
            "{home}/.venv/bin/conncheck -c {home}/{config} --log DEBUG"
            .format(home=conncheck_home_dir, config=self.config_file))
        self._systemd = zaza.utilities.installers.SystemdControl(
            self._ssh_fn, self._scp_fn, "conncheck", systemd_cmd,
            autostart=True)
        self._systemd.install()
        self._installed = True

    def _verify_systemd_not_none(self):
        """Raise an AssertionError if the systemd unit hasn't been defined."""
        assert self._systemd is not None, "Must install systemd first."

    @property
    def remote_log_filename(self):
        """Return the remote log filename on the unit.

        This is a definition of the remote home directory and the log file.

        :returns: the log filename of the remote unit.
        :rtype: str
        """
        return os.path.abspath(os.path.join(self._conncheck_home_dir,
                                            self.log_file))

    @property
    def local_log_filename(self):
        """Return the local name for the log file.

        This is to make it unique so that it doesn't clash with other units.

        :returns: the local filename
        :rtype: str
        """
        raise NotImplementedError()

    def get_logfile_to_local(self, local_dir):
        """Get the logile from the instance to the local directory.

        This fetches the remote log-file to a local directory (given).  The
        file/name is returned (but can be got again with local_log_filename())

        :param local_dir: the place to store the log file to.
        :type local_dir: str
        :returns: the file name (local_dir/local_log_filename())
        :rtype: str
        """
        local_filename = os.path.abspath(
            os.path.join(local_dir, self.local_log_filename))
        self._scp_fn(self.remote_log_filename, local_filename, copy_from=True)
        return local_filename

    def write_configuration(self):
        """Write the configuration to the unit.

        This writes the configuration to the unit.  If it is running, then it
        restarts the process on the unit (via the systemd unit).
        """
        if not self._installed:
            self.install()
        name = self.name or self.machine_or_unit_spec
        config = {
            'name': name,
            'file-log-path': self.remote_log_filename,
            'collection': self.collection,
            'log-format': self.log_format,
            'listeners': list(self._listeners.values()),
            'speakers': list(self._speakers.values()),
        }
        # write the file to the unit
        with tempfile.TemporaryDirectory() as tdir:
            fname = os.path.join(tdir, "config.yaml")
            with open(fname, "wt") as f:
                yaml.dump(config, f)
            self._scp_fn(fname, self.config_file)
            # now move it to the conncheck home dir
            self._ssh_fn(["sudo", "mv", self.config_file,
                          "{}/{}".format(self._conncheck_home_dir,
                                         self.config_file)])
        if self.is_running():
            self.restart()

    def is_running(self):
        """Return True if we think we are running.

        :returns: True if the ConnCheck instance is running on the unit.
        :rtype: bool
        """
        self._verify_systemd_not_none()
        return self._systemd.is_running()

    def start(self):
        """Start the ConnCheck instance installed on the remote unit."""
        self._verify_systemd_not_none()
        self._systemd.start()

    def stop(self):
        """Stop the ConnCheck instance on the remote unit."""
        if self._systemd is not None:
            self._systemd.stop()
        else:
            logging.debug(
                "Calling stop on %s but no _systemd controller.", self)

    def restart(self):
        """Restart the ConnCheck instance on the remote unit."""
        self._verify_systemd_not_none()
        self._systemd.restart()

    def finalise(self):
        """Finalise the instance; essentially stop it logging."""
        if self._installed:
            self.stop()
            self._systemd.disable()

    def clean_up(self):
        """Clean-up the ConnCheck on the remote unit."""
        if self._installed:
            self.stop()
            self._systemd.disable()
            self._systemd.remove()
        # TODO: remove the module.


class ConnCheckInstanceJuju(ConnCheckInstanceBase):
    """Handle ConnCheck instances on Juju units and machines."""

    class JujuTypes(Enum):
        MACHINE = 1
        UNIT = 2

    def __init__(self, machine_or_unit_spec, **kwargs):
        """Create a instance for a Juju instance.

        **kwargs can contain:

         - model: the model to use, or None for the default one.
         - default_space: the default space to use for listeners, speakers.
         - log_format: the log format, default is InfluxDB
         - sudo: whether to use sudo for ssh on the unit (default false)
         - user: which user to use; leave as None for default 'ubuntu'
        """
        self.machine_or_unit_spec = machine_or_unit_spec
        self._validate_spec()
        self.model = None
        self.default_space = None
        self.sudo = None
        self.user = None
        super().__init__(**kwargs)
        self._ssh_fn = zaza.utilities.installers.make_juju_ssh_fn(
            self.machine_or_unit_spec, sudo=self.sudo, model=self.model)
        self._scp_fn = zaza.utilities.installers.make_juju_scp_fn(
            self.machine_or_unit_spec, user=self.user, model=self.model)

    @property
    def local_log_filename(self):
        """Return the local name for the log file.

        This is to make it unique so that it doesn't clash with other units.

        :returns: the local filename
        :rtype: str
        """
        return "{}.log".format(
            self.machine_or_unit_spec.replace("/", "_").replace(":", "-"))

    def _validate_spec(self):
        """The spec can either be a single number, or an LXD specification.

         - machine  - int
         - LXD machine - int/lxd/int
         - unit - unit-name/int

        If it's not one of those then it raises an Exception.

        :raises ValueError: If the spec can't be matched.
        """
        valid_matchers = (
            (r"^(\d+)$", self.JujuTypes.MACHINE),
            (r"^(\d+\/(?:lxd|LXD)\/\d+)$", self.JujuTypes.MACHINE),
            (r"^([a-zA-Z0-9-]+\/\d+)$", self.JujuTypes.UNIT))
        for matcher, type_ in valid_matchers:
            if re.match(matcher, self.machine_or_unit_spec):
                self._juju_type = type_
                return
        raise ValueError(
            "Juju machine/unit spec of '{}' doesn't appear to be valid"
            .format(self.machine_or_unit_spec))

    def add_listener(
            self, type_, port, address=None, space=None, cidr=None,
            reply_size=1024):
        """Add a listen of a type and port.

        Note, the simplest thing to do is to bind the listener to every
        address, by passing an address of '0.0.0.0'.

        :param type_: either 'udp' or 'http'
        :type type_: str
        :param port: the port to connect to.
        :type port: int
        :param address: the address to contact.
        :type address: str
        :param space: Optionally the Juju space to get an address in.
        :type space: Optional[str]
        :param cidr: The cidr to evaluate the address to.
        :type cidr: str
        :param reply_size: the size of the reply packet (if appropriate)
        :type reply_size: int
        :raises ValueError: if the type isn't recognised.
        """
        self._validate_not_existing_listener(type_, port)
        # need the address of the unit (perhaps using the space)
        if address is None:
            address = self._get_address(space, cidr)
        self.add_listener_spec(type_, port, address, reply_size=reply_size)

    def _get_address(self, space=None, cidr=None):
        """Try to find the address in a space, optionally using a cidr.

        :param space: Optionally the Juju space to get an address in.
        :type space: Optional[str]
        :param cidr: The cidr to evaluate the address to.
        :type cidr: str
        :returns: the address found.
        :rtype: str
        :raises RuntimeError: if it's the 'wrong' type of juju unit.
        """
        if space is None:
            # if there's no space to use, then just use juju-info and hope for
            # the best; network-get has to have a space/binding to work with.
            space = "juju-info"
        if self._juju_type == self.JujuTypes.UNIT:
            return self._get_address_unit(space, cidr)
        elif self._juju_type == self.JujuTypes.MACHINE:
            return self._get_address_machine(cidr)
        raise RuntimeError(
            "Don't know how to get the address for a Juju unit: {}"
            .format(self.machine_or_unit_spec))

    def _get_address_unit(self, space=None, cidr=None):
        """Helper to ask the unit what it's address is.

        :param space: Optionally the Juju space to get an address in.
        :type space: Optional[str]
        :param cidr: The cidr to evaluate the address to.
        :type cidr: str
        :returns: the address found.
        :rtype: str
        :raises RuntimeError: if it's the 'wrong' type of juju unit.
        """
        try:
            # We have to juju run the network-get as it needs to be in the HOOK
            # context.
            cmd = ("juju run -u {} -- network-get --format yaml --bind-address"
                   " {}".format(self.machine_or_unit_spec, space))
            output = subprocess.check_output(cmd.split(' ')).decode()
        except subprocess.CalledProcessError:
            logging.error("Couldn't get network address for %s in binding: %s",
                          self.machine_or_unit_spec, space)
            raise
        result = yaml.safe_load(output)
        if isinstance(result, str):
            return result

        # it's obviously, not a bare string.
        logging.error("Mutliple results returned for getting address.\n%s",
                      output)
        # TODO: how do we deal with multiple addresses?
        raise NotImplementedError(
            "Don't know what to do with multiple addresses.\n{}"
            .format(output))

    def _get_address_machine(self, cidr=None):
        """Try to get the machine address to listen on.

        This is hard, as it's not clear how to do it well.
        # TODO
        """
        raise NotImplementedError()

ConnCheckManager.register_spec_handler('juju', ConnCheckInstanceJuju)


class ConnCheckInstanceSSH(ConnCheckInstanceBase):
    """Handle ConnCheck instances on SSH reachable units."""

    def __init__(self, address, key_file, **kwargs):
        """Create a instance of ConnCheck on an SSH unit.

        **kwargs can contain:

         - log_format: the log format, default is InfluxDB
         - user: which user to use; leave as None for default 'ubuntu'

        :param address: the address of the unit (to talk to)
        :type address: str
        :param key_file: the ssh private key to construct the ssh and scp
        functions from
        :type key_file: str
        """
        self.address = address
        self.key_file = key_file
        self.sudo = None
        self.user = None
        super().__init__(**kwargs)
        self._ssh_fn = zaza.utilities.installers.make_ssh_fn(
            self.address, key_file=self.key_file, user=self.user)
        self._scp_fn = zaza.utilities.installers.make_scp_fn(
            self.address, key_file=self.key_file, user=self.user)

    @property
    def local_log_filename(self):
        """Return the local name for the log file.

        This is to make it unique so that it doesn't clash with other units.

        :returns: the local filename
        :rtype: str
        """
        return "{}.log".format(
            self.address.replace(".", "-").replace("/", "_").replace("@", "_"))

    def add_listener(
            self, type_, port, address=None, reply_size=1024):
        """Add a listen of a type and port.

        Note, the simplest thing to do is to bind the listener to every
        address, by passing an address of '0.0.0.0'.

        :param type_: either 'udp' or 'http'
        :type type_: str
        :param port: the port to connect to.
        :type port: int
        :param address: Optional the address to contact.
        :type address: Optional[str]
        :param reply_size: the size of the reply packet (if appropriate)
        :type reply_size: Optional[int]
        :raises ValueError: if the type isn't recognised.
        """
        self._validate_not_existing_listener(type_, port)
        # need the address of the unit (perhaps using the space)
        if address is None:
            address = "0.0.0.0"
        self.add_listener_spec(type_, port, address, reply_size=reply_size)


ConnCheckManager.register_spec_handler('ssh', ConnCheckInstanceSSH)
