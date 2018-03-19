import argparse
import logging

from . import LOGGING_FORMAT_PREFIX
from . import cmd_runtest
from . import cmd_validate

logger = logging.getLogger("papr")

logging.basicConfig(format=(LOGGING_FORMAT_PREFIX + "%(message)s"))


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true',
                        help="Print debugging information")

    subparsers = parser.add_subparsers(dest='cmd', metavar='<command>',
                                       title='subcommands')
    subparsers.required = True

    cmd_runtest.add_cli_parsers(subparsers)
    cmd_validate.add_cli_parsers(subparsers)

    args = parser.parse_args()

    if args.debug:
        # we just use the root logger for now
        logger.setLevel(logging.DEBUG)
        logger.debug("debug logging turned on")
    else:
        logger.setLevel(logging.INFO)

    return args.func(args)
