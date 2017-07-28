#!/usr/bin/env python3

import logging
import threading

from . import TestEnv

logger = logging.getLogger("papr")


class ClusterTestEnv(TestEnv):

    def __init__(self, Host, Container, spec):
        self.spec = spec

        self.hosts = []
        for host_spec in spec['hosts']:
            self.hosts.append(Host(host_spec))

        if 'container' in self.spec:
            self.container = Container(self.spec['container'])
            self.controller = self.container
        else:
            self.container = None
            self.controller = self.hosts[0]

    def provision(self):
        threads = []
        for host in self.hosts:
            threads.append(threading.Thread(target=host.provision))
            threads[-1].start()
        if self.container is not None:
            self.container.provision()
        for t in threads:
            t.join()

    def teardown(self):
        for host in self.hosts:
            host.teardown()
        if self.container is not None:
            self.container.teardown()

    def run_query_cmd(self, cmd):
        return self.run_cmd(cmd).rc == 0

    def run_checked_cmd(self, cmd, timeout=None):
        return self.controller.run_checked_cmd(cmd, timeout)

    def run_cmd(self, cmd, timeout=None):
        return self.controller.run_cmd(cmd, timeout)

    def copy_to_env(self, src, dest):
        return self.controller.copy_to_env(src, dest)

    def copy_from_env(self, src, dest_dir, allow_noent=False):
        return self.controller.copy_from_env(src, dest_dir, allow_noent)
