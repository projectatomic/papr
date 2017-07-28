#!/usr/bin/env python3

import os
import re
import fcntl
import subprocess
import logging

logger = logging.getLogger("papr")


# http://stackoverflow.com/a/39596504/308136
def ordinal(n):
    suffix = ['th', 'st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'th', 'th']
    if n < 0:
        n *= -1
    n = int(n)

    if n % 100 in (11, 12, 13):
        s = 'th'
    else:
        s = suffix[n % 10]

    return str(n) + s


# normalize timeout str to seconds
def str_to_timeout(s):
    assert re.match('^[0-9]+[smh]$', s)
    timeout = int(s[:-1])
    if s.endswith('m'):
        timeout *= 60
    if s.endswith('h'):
        timeout *= 60 * 60
    return timeout


def checked_cmd(cmd, **kwargs):
    assert 'stdout' not in kwargs and 'stderr' not in kwargs
    try:
        p = subprocess.run(cmd, **kwargs,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    if timed_out:
        raise Exception("command '%s' timed out: %s" % (cmd, p.stdout))
    elif p.returncode != 0:
        raise Exception("command '%s' failed with rc %d: %s" %
                        (cmd, p.returncode, p.stdout))


class Flock:

    def __init__(self, target, shared=False):
        self.target = target
        self.shared = shared
        self.fd = None

    def __enter__(self):
        # NB: unlike flock(1), we don't use O_CREAT
        flags = os.O_RDONLY | os.O_NOCTTY | os.O_CLOEXEC
        self.fd = os.open(self.target, flags)
        lock_op = fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX
        fcntl.flock(self.fd, lock_op)
        return self.fd

    def __exit__(self, type, value, traceback):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)
