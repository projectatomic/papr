#!/usr/bin/env python3

import os
import collections

PKG_DIR = os.path.dirname(os.path.realpath(__file__))

# rc is None if timed out
# outf is a file handle
CmdResult = collections.namedtuple('CmdResult', ['rc', 'outf', 'duration'])


class TestEnv:
    """
    A testing environment. Abstracts details such as provisioning, teardown,
    running commands, and file transfer.
    """

    def provision(self):
        """
        Provision test environment based on a spec.
        """
        raise Exception("not implemented")

    def teardown(self):
        """
        Teardown test environment.
        """
        raise Exception("not implemented")

    def run_checked_cmd(self, cmd):
        """
        Run command and raise exception if it returns non-zero. On success,
        return output as a string. Only use for commands with bounded time and
        bounded UTF-8 output.
        """
        raise Exception("not implemented")

    def run_cmd(self, cmd, timeout=None):
        """
        Run command and return a CmdResult tuple.
        """
        raise Exception("not implemented")

    def copy_to_env(self, src, dest):
        """
        Copy src on local machine to dest in test environment.
        """
        raise Exception("not implemented")

    def copy_from_env(self, src, dest, allow_noent=False):
        """
        Copy src in test environment to dest on local machine.
        """
        raise Exception("not implemented")
