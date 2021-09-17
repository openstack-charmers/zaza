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
        unit, source, destination=".", model=None, install_virtualenv=True,
        run_user=None):
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
    :type install_virtualenv: bool
    :param run_user: The user that will run the module (needed for sudo to
        copy/install files for that user).
    :type run_user: Optional[str]
    :raises: subprocess.CalledProcessError
    """
    install_module_in_venv(
        source,
        destination,
        make_juju_scp_fn(unit, model=model),
        make_juju_ssh_fn(unit, model=model),
        install_virtualenv=install_virtualenv,
        run_user=run_user)


def install_module_instance(
        target, source, destination=".", key_file=None, user=None,
        install_virtualenv=True, run_user=None):
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
    :type install_virtualenv: bool
    :param run_user: The user that will run the module (needed for sudo to
        copy/install files for that user).
    :type run_user: Optional[str]
    :raises: subprocess.CalledProcessError
    """
    install_module_in_venv(
        source,
        destination,
        make_scp_fn(target, key_file=key_file, user=user),
        make_ssh_fn(target, key_file=key_file, user=user),
        install_virtualenv=install_virtualenv,
        run_user=run_user)


def install_module_in_venv(
    source, destination, scp_fn, ssh_fn, python='python3', venv_dir='.venv',
    install_virtualenv=True, run_user=None,
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
    :param install_virtualenv: Install the virtualenv utility on the target if
        needed.
    :type install_virtualenv: bool
    :param run_user: The user that will run the module (needed for sudo to
        copy/install files for that user).
    :type run_user: Optional[str]
    :raises: subprocess.CalledProcessError if any command fails.
    :raises: RuntimeError if a pre-requisit isn't installed.
    """
    cmd_prefix = ["sudo", "-u", run_user] if run_user else []
    # check the destination is a directory and not a file.
    ssh_fn(cmd_prefix + ["test", "-d", destination])
    if source.startswith("file:"):
        # copy the module from local to the destination.
        source = source[len("file:"):]
        extra_path = 'tmp-{}'.format(str(uuid.uuid4())[-12:])
        dest_source = os.path.join(user_directory(ssh_fn), extra_path)
        scp_fn(source, dest_source)
        module = dest_source
    else:
        module = source
    # now check for the virtualenv.
    venv = os.path.join(destination, venv_dir)
    try:
        ssh_fn(cmd_prefix + ["test", "-d", venv])
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            try:
                ssh_fn("which virtualenv")
            except subprocess.CalledProcessError:
                if install_virtualenv:
                    ssh_fn("sudo apt install -y virtualenv")
                else:
                    raise RuntimeError("virtualenv needs to be installed")
            ssh_fn(cmd_prefix + ["virtualenv", "-p",
                                 "`which {}`".format(python), venv])
    cmd = ["{}/bin/pip".format(venv), "install", module]
    ssh_fn(cmd_prefix + cmd)


def make_juju_ssh_fn(unit, sudo=False, model=None):
    """Create the ssh_fn for accessing a juju unit.

    :param unit: the unit identifier to run the ssh command on.
    :type unit: str
    :param sudo: Flag, if True, sets the command to be sudo
    :type sudo: False
    :param model: the (optional) model on which to run the unit on
    :type model: Optional[str]
    :returns: the callable that can be used to ssh onto a unit
    :rtype: Callable[List[Union[str, List[str]]], str]
    """
    def _ssh_fn(command):
        return _run_via_juju_ssh(unit, command, sudo=sudo, model=model)

    return _ssh_fn


def _run_via_juju_ssh(unit_name, cmd, sudo=False, model=None, quiet=True):
    """Run command on unit via ssh - local, that understands sudo and models.

    For executing commands on units when the juju agent is down.

    :param unit_name: Unit Name
    :type unit_name: str
    :param cmd: Command to execute on remote unit
    :type cmd: Union[str, List[str]]
    :param sudo: Flag, if True, sets the command to be sudo
    :type sudo: bool
    :param model: optional model to pass in.
    :type model: Optional[str]
    :param quiet: If quiet, stop any logging from ssh.  This prevents the
        "Connection to <ip address> closed." messages appearing in the logs.
    :type quiet: bool
    :returns: whatever the ssh command returned.
    :rtype: str
    :raises: subprocess.CalledProcessError
    """
    if isinstance(cmd, str):
        cmd = cmd.split(" ")
    if sudo and cmd[0] != "sudo":
        cmd.insert(0, "sudo")
    _cmd = ['juju', 'ssh']
    if model is not None:
        _cmd.append('--model={}'.format(model))
    _cmd.append(unit_name)
    if quiet:
        _cmd.extend(['-o', 'LogLevel=QUIET'])
    _cmd.append('--')
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

    def _scp_fn(source, destination, recursive=True, copy_from=False):
        scp_opts = '-r' if recursive else ''
        if copy_from:
            logging.debug(
                "Getting remote %s to local %s from %s",
                source, destination, unit)
            return zaza.model.scp_from_unit(unit, source, destination,
                                            model_name=model, user=user,
                                            proxy=proxy,
                                            scp_opts=scp_opts)
        else:
            logging.debug(
                "Putting local %s to remote %s on %s",
                source, destination, unit)
            return zaza.model.scp_to_unit(unit, source, destination,
                                          model_name=model, user=user,
                                          proxy=proxy,
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

    def _scp_fn(source, dest, recursive=True, copy_from=False):
        _dest = "{}{}".format(destination, dest)
        _cmd = cmd.copy()
        if recursive:
            _cmd.append('-r')
        if copy_from:
            _cmd.extend([_dest, source])
            logging.debug(
                "Getting remote %s to local %s from %s",
                source, destination, target)
        else:
            _cmd.extend([source, _dest])
            logging.debug(
                "Putting local %s to remote %s on %s",
                source, destination, target)
        subprocess.check_call(_cmd)

    return _scp_fn


def create_user(ssh_fn, name):
    """Create a user on an instance using the ssh_fn and name.

    The ssh_fn is a function that takes a command and runs it on the remote
    system.  It must be sudo capable so that a user can be created and the
    remote directory for the user be determined.  The directory for the user is
    created in /var/lib/{name}

    :param ssh_fn: a sudo capable ssh_fn that can run commands on the unit.
    :type ssh_fn: Callable[[str], str]
    :param name: the name of the user to create.
    :type name: str
    :returns: the directory of the new user.
    :rtype: str
    """
    dir_ = "/var/lib/{name}".format(name=name)
    cmd = ["sudo", "useradd", "-r", "-s", "/bin/false", "-d", dir_, "-m", name]
    ssh_fn(cmd)
    return dir_.strip()


def user_exists(ssh_fn, name):
    """Test is a user exists.

    The ssh_fn is a function that takes a command and runs it on the remote
    system.  It requires the the ssh_fn raises an exception if the command
    fails.

    :param ssh_fn: a ssh_fn that can run commands on the unit.
    :type ssh_fn: Callable[[str], str]
    :param name: the name of the user to test if exists.
    :type name: str
    :returns: True if the user exists
    :rtype: bool
    """
    cmd = ["grep", "-c", "^{name}:".format(name=name), "/etc/passwd"]
    try:
        ssh_fn(cmd)
    except Exception:
        return False
    return True


def user_directory(ssh_fn, name=None):
    """Get the directory for the user.

    The ssh_fn is a function that takes a command and runs it on the remote
    system.

    If :param:`name` is None, then the user for the ssh_fn is detected,
    otherwise the home dir or specified user is detected.

    :param ssh_fn: a ssh_fn that can run commands on the unit.
    :type ssh_fn: Callable[[str], str]
    :param name: the name of the user to get the directory for.
    :type name: Option[str]
    :returns: True if the user exists
    :rtype: bool
    """
    if name is None:
        cmd = ["echo", "$HOME"]
    else:
        cmd = ["echo", "~{name}".format(name=name)]
    return ssh_fn(cmd).strip()


class SystemdControl:
    """Provide a mechanism to control an daemon as a systemd process.

    The control file will be stored in /etc/systemd/system

    It is assumed to be a simple daemon that can be stopped and started using
    typical control signals.


    """

    SYSTEMD_FILE = textwrap.dedent("""
        [Unit]
        Description=SystemdControl file for {name}

        [Service]
        ExecStart={exec_start}
        User={name}
        Environment=PYTHONUNBUFFERED=1
        Restart=on-failure
        RestartSec=5s

        [Install]
        WantedBy=default.target
        """)

    def __init__(
            self, ssh_fn, scp_fn, name, execute):
        """Initialise a SystemdControl object.

        :param ssh_fn: a function that runs commands on the instance; this
            needs to have sudo access.
        :type ssh_fn: Callable[[str], str]
        :param scp_fn: a function that can copy files to the instance.
        :type scp_fn: Callable[[str, str, bool], None]
        :param name: name of the unit (short, no spaces)
        :type name: str
        :param execute: the command+options that the systemd unit will execute
            to run the program.
        :type execute: str
        """
        self.ssh_fn = ssh_fn
        self.scp_fn = scp_fn
        self.name = name
        self.execute = execute
        self._enabled = False
        self._installed = False
        self._home_var = None
        self._stopped = True

    @property
    def _systemd_dir(self):
        return "/etc/systemd/system"

    @property
    def _systemd_filename(self):
        return "{}.service".format(self.name)

    @property
    def _systemd_file(self):
        return os.path.join(self._systemd_dir, self._systemd_filename)

    @property
    def _home(self):
        if self._home_var is not None:
            return self._home_var
        self._home_var = user_directory(self.ssh_fn)
        return self._home_var

    def install(self):
        """Install the systemd control file on the instance.

        Install the systemd control file.  To do this:

         1. render it to a local file.
         2. copy that file to the ssh user's directory (as a temp name)
         3. sudo mv that file to the _systemd_dir dir.
        """
        systemd_ctrl_file = self.SYSTEMD_FILE.format(
            name=self.name, exec_start=self.execute)

        remote_temp_file = os.path.join(self._home, self._systemd_filename)
        with tempfile.TemporaryDirectory() as td:
            fname = os.path.join(td, "control")
            with open(fname, "wt") as f:
                f.write(systemd_ctrl_file)
            self.scp_fn(fname, remote_temp_file)
            self.ssh_fn(["sudo", "mv", remote_temp_file, self._systemd_file])
            self.ssh_fn(["sudo", "systemctl", "daemon-reload"])
        self._installed = True

    def _systemctl(self, command):
        _command = ["sudo", "systemctl", command, self.name]
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
            self._stopped = False

    def stop(self):
        """Stop the systemd unit instance on the instance."""
        if not self._installed or self._stopped:
            return
        if self.is_running():
            self._systemctl("stop")
            self._stopped = True

    def restart(self):
        """Restart the systemd unit on the instance."""
        if not self._installed:
            return
        if self.is_running():
            self._systemctl("restart")
        else:
            self._systemctl("start")
        self._stopped = False

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
        :rtype: bool
        """
        if not self._installed or self._stopped:
            return False
        try:
            command = ["sudo", "systemctl", "show", "-p", "SubState",
                       "--value", "--no-pager", self.name]
            output = self.ssh_fn(command)
        except subprocess.CalledProcessError as e:
            logging.debug("is_running() check failed: {}"
                          .format(str(e)))
            self._stopped = True
            return False
        _running = "running" in output.strip()
        self._stopped = not(_running)
        return _running

    def remove(self):
        """Stop the unit, disable the unit, and remove the control file."""
        if self._installed:
            self.stop()
            self.disable()
            self.ssh_fn(["sudo", "rm", self._systemd_file])
        self._installed = False
