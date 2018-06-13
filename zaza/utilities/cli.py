"""Module containing utilities for working with commandline tools."""

import logging
import os


def parse_arg(options, arg, multiargs=False):
    """Parse argparse argments.

    :param options: Argparse options
    :type options: argparse object
    :param arg: Argument attribute key
    :type arg: string
    :param multiargs: More than one arugment or not
    :type multiargs: boolean
    :returns: Argparse atrribute value
    :rtype: string
    """
    if arg.upper() in os.environ:
        if multiargs:
            return os.environ[arg.upper()].split()
        else:
            return os.environ[arg.upper()]
    else:
        return getattr(options, arg)


def setup_logging():
    """Do setup for logging.

    :returns: Nothing: This fucntion is executed for its sideffect
    :rtype: None
    """
    logFormatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")
    rootLogger = logging.getLogger()
    rootLogger.setLevel('INFO')
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(consoleHandler)
