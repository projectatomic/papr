#!/usr/bin/env python3

import os
import collections

PKG_DIR = os.path.dirname(os.path.realpath(__file__))

# rc is None if timed out
CmdResult = collections.namedtuple('CmdResult', ['rc', 'output', 'duration'])


class TestEnv:

    def provision(self):
        raise Exception("not implemented")

    def teardown(self):
        raise Exception("not implemented")

    def run_checked_cmd(self, cmd, timeout=None):
        raise Exception("not implemented")

    def run_cmd(self, cmd, timeout=None):
        raise Exception("not implemented")

    def copy_to_env(self, src, dest):
        raise Exception("not implemented")

    def copy_from_env(self, src, dest, allow_noent=False):
        raise Exception("not implemented")
