#!/usr/bin/env python3

import io
import os
import time
import docker
import shutil
import tarfile
import tempfile
import logging
import threading
import subprocess

from . import TestEnv
from . import CmdResult
from .. import github
from .. import utils

logger = logging.getLogger("papr")


class DockerTestEnv(TestEnv):

    def __init__(self, spec):
        self.spec = spec
        self.client = docker.from_env(version="auto")
        assert self.client.ping(), "Failed to ping daemon"
        self.container = None

    def provision(self):
        # pre-pull the image so that it doesn't count as part of the timeout
        img_fqdn = self.spec['image']
        logger.debug("pulling image '%s'" % img_fqdn)
        try:
            #img = self.client.images.pull(img_fqdn)
            pass
        except:
            raise github.GitHubFriendlyStatusError("Could not pull image %s." %
                                                   img_fqdn)
        # We used to run 'sleep infinity', though that's coreutils centric,
        # e.g. busybox doesn't support it. So now, we just use a Really Long
        # Time, which has the advantage of ensuring the container eventually
        # exits and gets GC'ed in case we crash.
        cmd = ["sleep", "1d"]

        #self.container = self.client.containers.run(img.id, cmd, detach=True)
        self.container = self.client.containers.run('registry.fedoraproject.org/fedora:26', cmd, detach=True)
        logger.debug("started container '%s'" % self.container.id)

    def teardown(self):
        if self.container:
            # Sometimes, the daemon complains about being unable to remove the
            # root filesystem, but the container shortly gets removed
            # afterwards. So let's just keep trying until it's truly gone
            retries = 5
            for i in range(retries):
                try:
                    self.container.remove(force=True)
                    break
                except docker.errors.NotFound:
                    break # we're done!
                except docker.errors.APIError as e:
                    if e.response.status_code != 500 or i == retries - 1:
                        raise
                # *sigh*, this is the sad world we live in
                time.sleep(0.5)

    def run_query_cmd(self, cmd):
        return self.run_cmd(cmd).rc == 0

    def run_checked_cmd(self, cmd, timeout=None):
        r = self.run_cmd(cmd, timeout)
        if r.rc is None:
            raise RuntimeError("Command %s timed out" % cmd)
        elif r.rc != 0:
            raise RuntimeError("Command %s returned rc=%d" % cmd, r.rc)
        return r.output

    def run_cmd(self, cmd, timeout=None):
        # can't just use the obvious self.container.exec_run() here:
        # https://github.com/docker/docker-py/issues/1381
        eid = self.client.api.exec_create(self.container.id, cmd)
        start_time = time.time()

        # This is a bit cumbersome, but there's no simple way to time out
        # while waiting on a generator. Though we could bypass the docker
        # python API and use requests directly...
        gen = self.client.api.exec_start(eid, stream=True)
        # store output in an O_TMPFILE as an easy way to share with thread
        with tempfile.TemporaryFile() as tmpf:
            lock = threading.Lock()
            t = threading.Thread(target=DockerTestEnv._write_out_to_fd,
                                 args=(gen, tmpf, lock))
            t.start()
            t.join(timeout)
            timed_out = t.is_alive()
            # it's very unlikely that the thread is blocked on writing, so
            # we should be able to get the lock quickly (it's more likely
            # to be blocked waiting on the next chunk of output). still, we
            # try to lock if we can to ensure consistent output
            # pylint: disable=unexpected-keyword-arg
            if lock.acquire(blocking=True, timeout=5):
                must_release = True
            tmpf.seek(0)
            out = tmpf.read()
            if must_release:
                lock.release()
            else:
                out = "WARNING: output may be corrupted\n" + out
            if timed_out:
                # There's no way to safely force the generator to abort, so
                # just log it for now. We'll be tearing down the container
                # soon anyway due to the time out.
                logger.debug("left a thread running (%s)" % cmd)

        duration = time.time() - start_time
        d = self.client.api.exec_inspect(eid)
        return CmdResult(None if timed_out else d['ExitCode'], out, duration)

    @staticmethod
    def _write_out_to_fd(out, fd, lock):
        for data in out:
            lock.acquire()
            try:
                fd.write(data)
            except:
                break
            finally:
                lock.release()

    def copy_to_env(self, src, dest):

        # we just leverage `docker cp` here rather than using the put_archive
        # API; the CLI already worked out the semantics for e.g. copying dirs
        # vs dir contents, etc...

        cp_dest = "%s:%s" % (self.container.id, dest)
        utils.checked_cmd(["docker", "cp", src, cp_dest])

        # # previous implementation
        # dirname = os.path.dirname(dest)
        # basename = os.path.basename(dest)

        # # this way, we use O_TMPFILE if we can
        # with tempfile.TemporaryFile() as tmpf:
        #     with tarfile.TarFile(fileobj=tmpf, mode='w') as tar:
        #         tar.add(src, arcname=basename)
        #     tmpf.seek(0)
        #     self.container.put_archive(dirname, tmpf)

    def copy_from_env(self, src, dest, allow_noent=False):
        '''
            Returns True if files were copied, False otherwise.
            Raise exception if allow_noent=False and src not found.
        '''

        if self.run_cmd(['test', '-e', src]).rc != 0:
            if allow_noent:
                return False
            raise Exception("src not found: %s" % src)

        cp_src = "%s:%s" % (self.container.id, src)
        utils.checked_cmd(["docker", "cp", cp_src, dest])

        # # previous implementation
        # # the HTTPResponse can't seek, so just dump it to an O_TMPFILE first
        # try:
        #     tar_stream, stat = self.container.get_archive(src)
        # except docker.errors.NotFound:
        #     if allow_noent:
        #         return False
        #     raise
        # with tempfile.TemporaryFile() as f:
        #     shutil.copyfileobj(tar_stream, f)
        #     f.seek(0)
        #     with tarfile.TarFile(fileobj=f) as tf:
        #         tf.extractall(dest_dir)
        # return True
