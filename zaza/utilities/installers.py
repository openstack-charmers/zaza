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

"""Utils to help with running conchecky on instances."""

import logging
import subprocess
import os
import textwrap
import tempfile
import uuid

import zaza.model


def install_module_on_juju_unit(
        unit, source, destination=".", model=None, install_virtualenv=True):
    """Install the module defined by source on the unit in a venv.

    :param unit: the unit to install it on.
    :type unit: str
    :param source: the source (as described in install_module_in_venv)
    :type source: str
    :param destination: where to put it (default the ubuntu user's home)
    :type destination: str
    :param model: the (optional) model on which to run the unit on
    :type model: Optional[str]
    :param install_virtualenv: Install the virtualenv on the target if needed.
    :type install_virtualenv: boolean
    :raises: subprocess.CalledProcessError
    """
    install_module_in_venv(
        source,
        destination,
        make_juju_scp_fn(unit, model=model),
        make_juju_ssh_fn(unit, model=model),
        install_virtualenv=install_virtualenv)


def install_module_instance(
        target, source, destination=".", key_file=None, user=None,
        install_virtualenv=True):
    """Install the module defined by source on the unit in a venv.

    :param target: the target hostname (e.g. 192.168.1.1)
    :type target: str
    :param source: the source (as described in install_module_in_venv)
    :type source: str
    :param destination: where to put it (default the ubuntu user's home)
    :type destination: str
    :param key_file: the optional key_file (to use -i option)
    :type key_file: Optional[str]
    :param user: the optional user (for user@hostname:...)
    :type user: Optional[str]
    :param install_virtualenv: Install the virtualenv on the target if needed.
    :type install_virtualenv: boolean
    :raises: subprocess.CalledProcessError
    """
    install_module_in_venv(
        source,
        destination,
        make_scp_fn(target, key_file=key_file, user=user),
        make_ssh_fn(target, key_file=key_file, user=user),
        install_virtualenv=install_virtualenv)


def install_module_in_venv(
    source, destination, scp_fn, ssh_fn, python='python3', venv_dir='.venv',
    install_virtualenv=True,
):
    """Install a module at a location using a venv.

    Install the pip module described by :paramref:`source` into a venv at
    :paramref:`venv_dir`.  The :paramref:`scp_fn` and :paramref:`ssh_fn` are
    functions that can copy files and run commands.  They must have the
    destination encoded in them.  They have call signatures of:

        def scp_fn(source_path_local, dest_path_remote, recursive=True)

        def ssh_fn(command_str)

    A venv is created if the :paramref:`venv_dir` doesn't exist, using the
    :paramref:`python` version as:

        virtualenv -p `which $python` $venv_dir

    Note: this means that virtualenv needs to be installed at the destination.

    The function may raise subprocess.CalledProcessError if any of the
    commands fail.  Suggestion is to wrap the call in a try: except: and log
    the error and then fail.

    If the :paramref:`source` is prefixed with 'file:' then the remaining
    string is assumed to be a path on the local file system and this will be
    copied to a destination at the :paramref:`destination` so that it can be
    pip installed.  This is the only time that the :paramref:`scp_fn` is used.

    Note that if the function fails part way through, then the destination may
    be left in an unknown state.

    :param source: a pip installable source.
    :type source: Path
    :param destination: the destination path for the venv.  Must be writable by
        the user of the scp/ssh encoded functions.
    :type destination: Path
    :param scp_fn: A function that can copy to the destination.
    :type scp_fn: Callable[[str, str, Optional[bool]]]
    :param ssh_fn: A function that can run arbitrary commands at the
        destination.
    :type ssh_fn: Callable[[str], str]
    :param python: the name of the python interpreter for the virtualenv.
    :type python: str
    :param venv_dir: The name of the virtualenv at the destination path.
    :type venv_dir: str
    :param install_virtualenv: Install the virtualenv on the target if needed.
    :type install_virtualenv: boolean
    :raises: subprocess.CalledProcessError if any command fails.
    :raises: RuntimeError if a pre-requisit isn't installed.
    """
    # check the destination is a directory and not a file.
    ssh_fn("test -d {}".format(destination))
    if source.startswith("file:"):
        source = source[len("file:"):]
        extra_path = 'tmp-{}'.format(str(uuid.uuid4())[-12:])
        dest_source = os.path.join(destination, extra_path)
        # copy the module from local to the destination.
        scp_fn(source, dest_source)
        module = dest_source
    else:
        module = source
    # now check for the virtualenv.
    venv = os.path.join(destination, venv_dir)
    try:
        ssh_fn("test -d {}".format(venv))
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            try:
                ssh_fn("which virtualenv")
            except subprocess.CalledProcessError:
                if install_virtualenv:
                    ssh_fn("sudo apt install -y virtualenv")
                else:
                    raise RuntimeError("virtualenv needs to be installed")
            ssh_fn("virtualenv -p `which {}` {}".format(python, venv))
    # Now install the module
    ssh_fn("{}/bin/pip install {}".format(venv, module))


def make_juju_ssh_fn(unit, sudo=False, model=None):
    """Create the ssh_fn for accessing a juju unit.

    :param unit: the unit identifier to run the ssh command on.
    :type unit: str
    :param sudo: Flag, if True, sets the command to be sudo
    :type sudo: False
    :param model: the (optional) model on which to run the unit on
    :type model: Optional[str]
    :returns: the callable that can be used to ssh onto a unit
    :rtype: Callable[[str], str]
    """
    def _ssh_fn(command):
        return _run_via_juju_ssh(unit, command, sudo=sudo, model=model)

    return _ssh_fn


def _run_via_juju_ssh(unit_name, cmd, sudo=None, model=None):
    """Run command on unit via ssh - local, that understands sudo and models.

    For executing commands on units when the juju agent is down.

    :param unit_name: Unit Name
    :type unit_name: str
    :param cmd: Command to execute on remote unit
    :type cmd: str
    :param sudo: Flag, if True, sets the command to be sudo
    :type sudo: False
    :returns: whatever the ssh command returned.
    :rtype: str
    :raises: subprocess.CalledProcessError
    """
    if sudo is None:
        sudo = False
    if sudo and "sudo" not in cmd:
        cmd = "sudo {}".format(cmd)
    _cmd = ['juju', 'ssh']
    if model is not None:
        _cmd.append('--model={}'.format(model))
    _cmd.extend([unit_name, '--'])
    if isinstance(cmd, str):
        cmd = cmd.split(" ")
    _cmd.extend(cmd)
    logging.debug("Running %s on %s", _cmd, unit_name)
    output = subprocess.check_output(_cmd).decode()
    logging.debug("Returned: '%s'", output)
    return output


def make_juju_scp_fn(unit, user=None, model=None, proxy=False):
    """Create a scp_fn for accessing the juju unit.

    :param unit: the unit identifier to run the ssh command on.
    :type unit: str
    :param user: the user to run as.
    :type user: str
    :param model: the (optional) model on which to run the unit on
    :type model: Optional[str]
    :param proxy: Proxy through the Juju API server
    :type proxy: bool
    :returns: the callable that can be used to ssh onto a unit
    :rtype: Callable[[str, str, bool], None]
    """
    if user is None:
        user = 'ubuntu'

    def _scp_fn(source, destination, recursive=True):
        scp_opts = '-r' if recursive else ''
        logging.debug("Copying %s to %s on %s", source, destination, unit)
        return zaza.model.scp_to_unit(unit, source, destination,
                                      model_name=model, user=user, proxy=proxy,
                                      scp_opts=scp_opts)

    return _scp_fn


def make_ssh_fn(target, key_file=None, user=None):
    """Create a ssh_fn for accessing a random unit.

    :param target: the target hostname (e.g. 192.168.1.1)
    :type target: str
    :param key_file: the optional key_file (to use -i option)
    :type key_file: Optional[str]
    :param user: the optional user (for user@hostname:...)
    :type user: Optional[str]
    :returns: the callable that can be used to ssh
    :rtype: Callable[[str], Any]
    """
    cmd = ['ssh']
    if key_file:
        cmd.extend(['-i', key_file])
    cmd.extend(['-o', 'StrictHostKeyChecking=no', '-q'])
    if user:
        destination = "{}@{}".format(user, target)
    else:
        destination = target
    cmd.extend([destination, '--'])

    def _ssh_fn(command):
        if isinstance(command, str):
            command = command.split(" ")
        _cmd = cmd + command
        logging.debug("Running %s on %s", _cmd, target)
        return subprocess.check_output(_cmd).decode()

    return _ssh_fn


def make_scp_fn(target, key_file=None, user=None):
    """Create a scp_fn for accessing a random unit.

    :param target: the target hostname (e.g. 192.168.1.1)
    :type target: str
    :param key_file: the optional key_file (to use -i option)
    :type key_file: Optional[str]
    :param user: the optional user (for user@hostname:...)
    :type user: Optional[str]
    :returns: the callable that can be used to ssh
    :rtype: Callable[[str, str, bool], None]
    """
    cmd = ['scp']
    if key_file:
        cmd.extend(['-i', key_file])
    cmd.extend(['-o', 'StrictHostKeyChecking=no', '-q', '-B'])
    if user:
        destination = "{}@{}:".format(user, target)
    else:
        destination = "{}:".format(target)

    def _scp_fn(source, dest, recursive=True):
        _dest = "{}{}".format(destination, dest)
        _cmd = cmd.copy()
        if recursive:
            _cmd.append('-r')
        _cmd.extend([source, _dest])
        logging.debug("Copying %s to %s on %s", source, destination, target)
        subprocess.check_call(_cmd)

    return _scp_fn


class UserSystemdControl:
    """Provide a mechanism to control an daemon as a user process.

    The control file will be stored in $HOME/.config/systemd/user/<name>.

    --user commands will be provided to run it.

    It is assumed to be a simple daemon that can be stopped and started using
    typical control signals.
    """

    SYSTEMD_FILE = textwrap.dedent("""
        [Unit]
        Description=UserSystemdControl file for {name}

        [Service]
        ExecStart={exec_start}
        Environment=PYTHONUNBUFFERED=1
        Restart=on-failure
        RestartSec=5s

        [Install]
        WantedBy=default.target
        """)

    def __init__(
            self, ssh_fn, scp_fn, name, execute, autostart=True):
        """Initialise a UserSystemdControl object.

        :param ssh_fn: a function that runs commands on the instance.
        :type ssh_fn: Callable[[str], Any]
        :param scp_fn: a function that can copy files to the instance.
        :type scp_fn: Callable[[str, str, bool], None]
        :param name: name of the unit (short, no spaces)
        :type name: str
        :param execute: the command+options that the systemd unit will execute
            to run the program.
        :type execute: str
        :param autostart: Default True; whether to automatically start the
            unit.
        :type autostart: boolean
        """
        self.ssh_fn = ssh_fn
        self.scp_fn = scp_fn
        self.name = name
        self.execute = execute
        self.autostart = autostart
        self._enabled = False
        self._installed = False
        self._home_var = None

    @property
    def _user_systemd_dir(self):
        return os.path.join(self._home, ".config/systemd/user")

    @property
    def _user_systemd_file(self):
        return os.path.join(self._user_systemd_dir,
                            "{}.service".format(self.name))

    @property
    def _home(self):
        if self._home_var is not None:
            return self._home_var
        self._home_var = self.ssh_fn("echo $HOME").strip()
        return self._home_var

    @property
    def _exec_start(self):
        if "$HOME" in self.execute:
            return self.execute.replace("$HOME", self._home)
        return self.execute

    def install(self):
        """Install the systemd control file on the instance."""
        systemd_ctrl_file = self.SYSTEMD_FILE.format(
            name=self.name, exec_start=self._exec_start)
        with tempfile.TemporaryDirectory() as td:
            fname = os.path.join(td, "control")
            with open(fname, "wt") as f:
                f.write(systemd_ctrl_file)
            # self.ssh_fn("mkdir -p {}".format(self._user_systemd_dir))
            self.ssh_fn(["mkdir", "-p", self._user_systemd_dir])
            self.scp_fn(fname, self._user_systemd_file)
            self.ssh_fn(["systemctl", "--user", "daemon-reload"])
        self._installed = True

    def _systemctl(self, command):
        # _command = ("systemctl --user {command} {name}"
                    # .format(command=command, name=self.name))
        _command = ["systemctl", "--user", command, self.name]
        logging.debug("Running %s", _command)
        return self.ssh_fn(_command)

    def start(self):
        """Start the systemd unit instance on the instance."""
        if not self._installed:
            self.install()
        if not self._enabled:
            self.enable()
        if not self.is_running():
            self._systemctl("start")

    def stop(self):
        """Stop the systemd unit instance on the instance."""
        if not self._installed:
            return
        if self.is_running():
            self._systemctl("stop")

    def restart(self):
        """Restart the systemd unit on the instance."""
        if not self._installed:
            return
        if self.is_running():
            self._systemctl("restart")
        else:
            self._systemctl("start")

    def enable(self):
        """Enable the systemd unit on the instance."""
        if not self._installed:
            self.install()
        self._systemctl("enable")
        self._enabled = True

    def disable(self):
        """Disable the systemd unit on the instance."""
        self._systemctl("disable")
        self._enabled = False

    def is_running(self):
        """Return True if we think we are running.

        :returns: True if the systemd unit seems to be running on the unit.
        :rtype: boolean
        """
        if not self._installed:
            return False
        try:
            command = ["systemctl", "--user", "show", "-p", "SubState",
                       "--value", "--no-pager", self.name]
            output = self.ssh_fn(command)
        except subprocess.CalledProcessError as e:
            logging.debug("is_running() check failed: {}"
                          .format(str(e)))
            return False
        return "running" in output.strip()

    def remove(self):
        """Stop the unit, disable the unit, and remove the control file."""
        if self._installed:
            self.stop()
            self.disable()
            self.ssh_fn(["rm", self._systemd_file])
        self._installed = False
