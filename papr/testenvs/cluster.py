#!/usr/bin/env python3

import logging
import threading

from . import TestEnv
from . import container
from . import host

#: module level logging
logger = logging.getLogger("papr")


class ClusterTestEnv(TestEnv):
    """
    Represents a single cluster test environment.
    """

    def __init__(self, spec):
        """
        Initializes a single cluster test environment object.

        :param spec: Cluster "spec".
        :type spec: dict
        """
        self.spec = spec

        self.hosts = []
        for host_spec in spec['hosts']:
            self.hosts.append(host.HostTestEnv(host_spec))

        if 'container' in self.spec:
            self.container = container.ContainerTestEnv(self.spec['container'])
            self.controller = self.container
        else:
            self.container = None
            self.controller = self.hosts[0]

    def provision(self):
        """
        Provision each container in it's own in parellel.
        """
        threads = []
        for h in self.hosts:
            threads.append(threading.Thread(target=h.provision))
            threads[-1].start()
        if self.container is not None:
            self.container.provision()
        for t in threads:
            t.join()

    def teardown(self):
        """
        Tears down resources.
        """
        for h in self.hosts:
            h.teardown()
        if self.container is not None:
            self.container.teardown()

    def run_query_cmd(self, cmd):
        """
        Runs a command and returns if the command was successful.

        :param cmd: Command to execute.
        :type cmd: str
        :returns: True on success, False on failure
        :rtype: bool
        """
        return self.run_cmd(cmd).rc == 0

    def run_checked_cmd(self, cmd, timeout=None):
        """
        Runs a command and returns the stdout.

        :param cmd: Command to execute.
        :type cmd: str
        :param timeout: How long to wait for the command.
        :type timeout: int
        :returns: The output of the command
        :rtype: str
        """
        return self.controller.run_checked_cmd(cmd, timeout)

    def run_cmd(self, cmd, timeout=None):
        """
        Runs a command and returns an structured response.

        :param cmd: Command to execute.
        :type cmd: str
        :param timeout: How long to wait for the command.
        :type timeout: int
        :returns: Result as named tuple
        :rtype: collections.namedtuple
        """
        return self.controller.run_cmd(cmd, timeout)

    def copy_to_env(self, src, dest):
        """
        Copies a file into the test environment.

        :param src: The source of the file
        :type src: str
        :param dest: The dest in the test environment for the file
        :type dest: str
        :returns: None
        :type: None
        """
        return self.controller.copy_to_env(src, dest)

    def copy_from_env(self, src, dest_dir, allow_noent=False):
        """
        Copies a from the test environment to the current host.

        :param src: The source of the file in the test environment
        :type src: str
        :param dest_dir: The dest on the current host
        :type dest_dir: str
        :param allow_noent: Don't raise RuntimeError if the file doesn't exist
        :type allow_noent: bool
        :returns: True if copy succeeds
        :type: bool
        :raises: RuntimeError
        """
        return self.controller.copy_from_env(src, dest_dir, allow_noent)
