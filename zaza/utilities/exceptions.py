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


class NoKeystoneFound(Exception):
    """No Keystone found in machines."""

    pass


class SeriesNotFound(Exception):
    """Series not found in status."""

    pass


class OSVersionNotFound(Exception):
    """OS Version not found."""

    pass


class ReleasePairNotFound(Exception):
    """Release pair was not found in OPENSTACK_RELEASES_PAIRS."""

    pass
