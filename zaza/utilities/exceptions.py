# Copyright 2018 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Module of exceptions that zaza may raise."""


class MissingOSAthenticationException(Exception):
    """Exception when some data needed to authenticate is missing."""

    pass


class CloudInitIncomplete(Exception):
    """Cloud init has not completed properly."""

    pass


class SSHFailed(Exception):
    """SSH failed."""

    pass


class NeutronAgentMissing(Exception):
    """Agent binary does not appear in the Neutron agent list."""

    pass


class NeutronBGPSpeakerMissing(Exception):
    """No BGP speaker appeared on agent."""

    pass


class ApplicationNotFound(Exception):
    """Application not found in machines."""

    def __init__(self, application):
        """Create Application not found exception.

        :param application: Name of the application
        :type application: string
        :returns: ApplicationNotFound Exception
        """
        msg = ("{} application was not found in machines.".
               format(application))
        super(ApplicationNotFound, self).__init__(msg)


class SeriesNotFound(Exception):
    """Series not found in status."""

    pass


class OSVersionNotFound(Exception):
    """OS Version not found."""

    pass


class ReleasePairNotFound(Exception):
    """Release pair was not found in OPENSTACK_RELEASES_PAIRS."""

    pass
