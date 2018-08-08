"""Module containing Ceph related utilities."""


def get_ceph_osd_id_cmd(osd_id):
    """Get ceph OSD command.

    Produce a shell command that will return a ceph-osd id.
    :returns: Command for ceph OSD.
    :rtype: string
    """
    return ("`initctl list | grep 'ceph-osd ' | "
            "awk 'NR=={} {{ print $2 }}' | "
            "grep -o '[0-9]*'`".format(osd_id + 1))
