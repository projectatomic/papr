#!/usr/bin/env python3

import os
import time
import uuid
import tempfile
import subprocess

from . import TestEnv
from . import CmdResult
from . import ocp


class ContainerTestEnv(TestEnv):

    def __init__(self, spec):
        self.spec = spec
        self.name = None

    def provision(self):
        self.name = ocp.create(self._generate_pod())
        ocp.wait_for_pod(self.name)

    def teardown(self):
        if self.name:
            ocp.delete('pod', self.name)

    def run_query_cmd(self, cmd):
        return self.run_cmd(cmd).rc == 0

    def run_checked_cmd(self, cmd):
        r = self.run_cmd(cmd)
        out = r.outf.read().decode('utf-8')
        if r.rc != 0:
            raise RuntimeError(f"cmd {cmd} exited with rc={r.rc}: {out}")
        return out

    def run_cmd(self, cmd, timeout=None):
        tmpf = tempfile.TemporaryFile()
        start_time = time.time()
        try:
            rc = ocp.exec(self.name, cmd, tmpf, timeout).returncode
        except subprocess.TimeoutExpired:
            rc = None
        tmpf.seek(0)
        duration = time.time() - start_time
        return CmdResult(rc, tmpf, duration)

    def copy_to_env(self, src, dest):
        ocp.cp_to_pod(self.name, src, dest)

    def copy_from_env(self, src, dest, allow_noent=False):
        if not self._path_exists(src):
            if allow_noent:
                return False
            raise RuntimeError(f"src {src} does not exist")
        ocp.cp_from_pod(self.name, src, dest)
        return True

    def _path_exists(self, path):
        return self.run_query_cmd(['test', '-e', path])

    def _generate_pod(self):
        pod = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "generateName": "papr-testpod-",
                "labels": {
                    "app": "papr"
                },
                ## if running in ocp, add owner reference
                ## XXX: need to figure out easy way to self introspect that info
                #"ownerReferences": [
                #    {
                #        "apiVersion": "v1",
                #        "blockOwnerDeletion": True,
                #        "kind": "Pod",
                #        "name": "papr-master-pod",
                #        "uid": "57163e1c-23e8-11e8-aed5-28d244a18c12"
                #    }
                #]
            },
            "spec": {
                "restartPolicy": "Never",
                "containers": [
                    {
                        "name": "test-pod",
                        #"imagePullPolicy": "Always", XXX
                        "imagePullPolicy": "IfNotPresent",
                        "command": ["sleep", "infinity"],
                        "securityContext": {
                            'runAsUser': 0
                        }
                    }
                ]
            }
        }

        pod["spec"]["containers"][0]["image"] = self.spec["image"]
        return pod
