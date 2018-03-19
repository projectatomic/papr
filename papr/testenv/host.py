#!/usr/bin/env python3

import os
import collections

from . import TestEnv


class HostTestEnv(TestEnv):

    def __init__(self, spec):
        pass

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
