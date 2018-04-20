#!/usr/bin/env python3

import json
import time
import logging
import subprocess

logger = logging.getLogger("papr")


# This is a thin `oc` CLI wrapper. We should evaluate porting this to
# https://github.com/openshift/openshift-restclient-python.

def create(obj):
    p = subprocess.run(["oc", "create", "-o", "name", "-f", "-"],
                       input=json.dumps(obj), stdout=subprocess.PIPE,
                       encoding='utf-8', check=True)
    name = p.stdout.strip()  # e.g. "pod/mypod"
    logger.debug(f"created OCP object {name}")
    return name[name.index('/')+1:]  # e.g. "mypod"


def delete(kind, name):
    logger.debug(f"deleting OCP {kind} {name}")
    subprocess.run(["oc", "delete", kind, name], check=True)


def exec(pod, cmd, outf=None, timeout=None):
    logger.debug(f"running {cmd} in {pod}")
    oc_cmd = ["oc", "exec", pod, "--"] + cmd
    return subprocess.run(oc_cmd, timeout=timeout,
                          stdout=outf, stderr=subprocess.STDOUT)


# wait for a pod to be scheduled, die after 6h
def wait_for_pod(pod, timeout=3600*6):
    # use dirty polling 🙉 🙈
    logger.debug(f"waiting for {pod} to be running")
    interval = 5  # check every 5s
    for i in range(0, timeout, interval):
        time.sleep(interval)
        p = subprocess.run(["oc", "get", "pod", pod,
                            "-o=jsonpath={.status.phase}"],
                           check=True, stdout=subprocess.PIPE,
                           encoding='utf-8')
        phase = p.stdout.strip()
        if phase == 'Running':
            return
        elif phase == 'Pending':
            continue
        else:
            raise RuntimeError(f"{pod} in unknown phase '{phase}'")
    raise RuntimeError(f"{pod} in phase '{phase}' after {timeout}s")


def cp_to_pod(pod, src, dest):
    logger.debug(f"copying {src} to {dest} on {pod}")
    subprocess.run(["oc", "cp", src, f"{pod}:{dest}"], check=True)


def cp_from_pod(pod, src, dest):
    logger.debug(f"copying {src} on {pod} to {dest}")
    subprocess.run(["oc", "cp", f"{pod}:{src}", dest], check=True)
