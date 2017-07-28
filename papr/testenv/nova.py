#!/usr/bin/env python3

import os
import io
import stat
import time
import uuid
import socket
import shutil
import logging
import tarfile
import tempfile
import threading
import subprocess
import collections

import paramiko
import novaclient.client

from .. import github
from .. import utils
from .. import site

from . import PKG_DIR
from . import TestEnv
from . import CmdResult

logger = logging.getLogger("papr")

# XXX: We just use a global var so we don't have to re-auth multiple times in
# the cluster case -- we use a lock for the authentication part; the rest of
# the API should be multi-threading safe.
NOVA = None
NOVA_LOCK = threading.Lock()


class NovaTestEnv(TestEnv):

    def __init__(self, spec):
        self.spec = spec
        self.ssh = None
        self.sftp = None
        self.server = None
        self.private_ip = None
        self.floating_ip = None
        self.name = self.spec.get('name', None)
        self.site_config = site.config['backends']['host'].get('config')
        global NOVA, NOVA_LOCK
        with NOVA_LOCK:
            if NOVA is None:
                if self.site_config.get('auth-from-env'):
                    auth_url = os.environ['OS_AUTH_URL']
                    username = os.environ['OS_USERNAME']
                    password = os.environ['OS_PASSWORD']
                    tenant_name = os.environ['OS_TENANT_NAME']
                else:
                    auth_url = self.site_config['auth-url']
                    username = self.site_config['auth-username']
                    password = self.site_config['auth-password']
                    tenant_name = self.site_config['auth-tenant']
                NOVA = novaclient.client.Client(2,
                    auth_url=auth_url, tenant_name=tenant_name,
                    username=username, password=password)
                NOVA.authenticate()
        self.nova = NOVA

    def provision(self):
        img = self._find_image()
        flavor = self._calculate_best_flavour()
        userdata = self._get_userdata()
        self.nova_name = self._generate_unique_name()
        self.server = self._create_server(img, flavor, userdata)
        self._create_ssh_session()
        if 'ostree' in self.spec:
            if not self._on_atomic_host():
                raise github.GitHubFriendlyStatusError(
                    "Can't specify 'ostree' on non-AH.")
            self._handle_ostree()

    def teardown(self):
        if self.sftp is not None:
            self.sftp.close()
        if self.ssh is not None:
            self.ssh.close()
        if self.floating_ip is not None:
            if self.server is not None:
                self.server.remove_floating_ip(self.floating_ip)
            self.floating_ip.delete()
        if self.server is not None:
            self.server.delete()

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
        transport = self.ssh.get_transport()
        chn = transport.open_session()
        # we build a pty here as an easy way to combine stdout & stderr
        chn.get_pty()
        chnf = chn.makefile('rb')
        # timeout after 3 seconds wait in recv() to check stop flag
        chn.settimeout(3)
        # this is how SSH works unfortunately
        chn.exec_command(' '.join(cmd))
        start_time = time.time()
        with tempfile.TemporaryFile() as tmpf:
            stop_event = threading.Event()
            t = threading.Thread(target=NovaTestEnv._write_out_to_fd,
                                 args=(chnf, tmpf, stop_event))
            t.start()

            timed_out = False
            t.join(timeout)
            if t.is_alive():
                timed_out = True
                stop_event.set()
                t.join()

            tmpf.seek(0)
            out = tmpf.read()
        if not timed_out:
            rc = chn.recv_exit_status()
        duration = time.time() - start_time
        return CmdResult(None if timed_out else rc, out, duration)

    @staticmethod
    def _write_out_to_fd(out, fd, stop_event):
        while not stop_event.is_set():
            try:
                data = out.readline()
                if data == b'':
                    break
                if not data.endswith(b'\n'):
                    data += b'\n'
                fd.write(data)
            except socket.timeout:
                pass

    def copy_to_env(self, src, dest):

        # We used to pipe through tar on the VM here, but now we just use rsync
        # here since its semantics are nearly identical to `docker cp`.

        rsync_dest = "root@%s:%s" % (self._get_connection_ip(), dest)
        utils.checked_cmd(["rsync", "-az", "--no-owner", "--no-group", "--rsh",
                           """ssh -o StrictHostKeyChecking=no \
                                  -o PasswordAuthentication=no \
                                  -o UserKnownHostsFile=/dev/null \
                                  -i """ + self.site_config['privkey'],
                           src, rsync_dest])

        # # previous implementation
        # dirname = os.path.dirname(dest)
        # basename = os.path.basename(dest)

        # # there's an sftp client available as part of paramiko, though given
        # # that we'll be transferring whole git repos, it seems more efficient
        # # to just use tar rather than calling put() thousands of times
        # stdin, stdout, stderr = \
        #         self.ssh.exec_command("tar -C '%s' -x" % dirname)
        # with tarfile.TarFile(fileobj=stdin, mode='w') as tar:
        #     tar.add(src, arcname=basename)
        # stdin.close()
        # # block until tar finishes
        # if stdin.channel.recv_exit_status() != 0:
        #     logger.error("tar error: %s" % stderr.read())
        #     raise Exception("failed to invoke tar")

    def copy_from_env(self, src, dest, allow_noent=False):

        if self.run_cmd(['test', '-e', src]).rc != 0:
            if allow_noent:
                return False
            raise Exception("src not found: %s" % src)

        rsync_src = "root@%s:%s" % (self._get_connection_ip(), src)
        utils.checked_cmd(["rsync", "-az", "--no-owner", "--no-group", "--rsh",
                           """ssh -o StrictHostKeyChecking=no \
                                  -o PasswordAuthentication=no \
                                  -o UserKnownHostsFile=/dev/null \
                                  -i """ + self.site_config['privkey'],
                           rsync_src, dest])

        # # previous implementation
        # dirname = os.path.dirname(src)
        # basename = os.path.basename(src)

        # # we use sftp for checking if the file exists, but just use tar for the
        # # actual transfer
        # self.sftp.chdir(dirname)
        # try:
        #     st = self.sftp.lstat(basename)
        # except FileNotFoundError:
        #     if allow_noent:
        #         return False
        #     raise

        # stdin, stdout, stderr = self.ssh.exec_command("tar -C '%s' -c '%s'" %
        #                                               (dirname, basename))
        # # tar needs to seek, so dump in a tempfile
        # with tempfile.TemporaryFile() as tmpf:
        #     shutil.copyfileobj(stdout, tmpf)
        #     tmpf.seek(0)
        #     with tarfile.TarFile(fileobj=tmpf) as tar:
        #         tar.extractall(dest_dir)
        #     # block until tar finishes
        #     if stdout.channel.recv_exit_status() != 0:
        #         logger.error("tar error: %s" % stderr.read())
        #         raise Exception("failed to invoke tar")
        # return True

    def _find_image(self):
        # it's possible multiple images match, e.g. during automated
        # image uploads, in which case let's just pick the first one
        return self.nova.images.findall(name=self.spec['distro'])[0]

    def _calculate_best_flavour(self):

        # defaults
        specs = self.spec.get('specs', {'ram': 2048, 'cpus': 1,
                                        'disk': 20, 'secondary-disk': 0})


        # go through all the flavours and determine which one to use
        flavors = [f for f in self.nova.flavors.findall()
                   if (f.ram >= specs['ram'] and
                       f.vcpus >= specs['cpus'] and
                       f.disk >= specs['disk'] and
                       f.ephemeral >= specs['secondary-disk'])]

        if len(flavors) == 0:
            raise github.GitHubFriendlyStatusError(
                "No flavor satisfies minimum requirements.")

        # OK, now we need to pick the *least* resource-hungry flavor
        # from the list of flavors that fit the min reqs. This is
        # inevitably subjective, but here we prioritize vcpus, then
        # ram, then disk.
        def filter_flavors(flavors, attr):
            minval = min([getattr(f, attr) for f in flavors])
            return [f for f in flavors if getattr(f, attr) == minval]

        flavors = filter_flavors(flavors, 'vcpus')
        flavors = filter_flavors(flavors, 'ram')
        flavors = filter_flavors(flavors, 'disk')
        flavors = filter_flavors(flavors, 'ephemeral')

        self._debug("choosing flavor '%s'" % flavors[0])
        return flavors[0]

    def _get_userdata(self):
        with open(os.path.join(PKG_DIR, "data/user-data")) as f:
            return f.read()

    def _generate_unique_name(self):

        # This is not strictly necessary; OpenStack allows multiple nodes to
        # have the same name. Though it just makes debugging much easier this
        # way.

        def gen_name():
            prefix = self.site_config.get('node-prefix')
            rand = uuid.uuid4().hex[:8]
            if prefix is not None:
                return "%s-%s" % (prefix, rand)
            return rand

        def server_exists(name):
            return len(self.nova.servers.findall(name=name)) > 0

        max_tries = 10
        name = gen_name()
        while server_exists(name) and max_tries > 0:
            name = gen_name()
            max_tries -= 1

        if max_tries == 0:
            raise Exception("can't find unique name")

        return name

    def _create_server(self, image, flavor, userdata):

        # we take this from the env right now, but it belongs in the site.yaml
        network_name = self.site_config['network']
        network = self.nova.networks.find(label=network_name)

        # if BUILD_ID is defined, let's add it so that it's easy to
        # trace back a node to the exact Jenkins build.
        meta = None
        if 'BUILD_ID' in os.environ:
            meta = {'BUILD_ID': os.environ['BUILD_ID']}

        self._debug("booting server '%s'" % self.nova_name)
        server = self.nova.servers.create(self.nova_name,
            meta=meta, image=image, userdata=userdata, flavor=flavor,
            key_name=self.site_config['keyname'],
            nics=[{'net-id': network.id}])

        # XXX: check if there's a more elegant way to do this
        # XXX: implement timeout
        while server.status == 'BUILD':
            server.get()
        if server.status != 'ACTIVE':
            try:
                server.delete()
            except:
                pass
            raise Exception("server not ACTIVE (state: %s)" % server.status)

        self.private_ip = server.networks[network.label][0]
        self._debug("private IP for %s is %s" % (self.nova_name,
                                                  self.private_ip))

        self.floating_ip = None
        if 'floating-ip-pool' in self.site_config:
            pool = self.site_config['floating-ip-pool']
            fip = self.nova.floating_ips.create(pool)
            server.add_floating_ip(fip)
            self.floating_ip = fip
            self._debug("floating IP for %s is %s" % (
                self.nova_name, self.floating_ip.ip))

        return server

    def _get_connection_ip(self):
        # use floating ip if present, otherwise private ip
        return self.floating_ip.ip if self.floating_ip else self.private_ip

    def _ssh_wait(self):
        sshwait = os.path.join(PKG_DIR, 'utils/sshwait')
        self._debug("waiting for SSH to be up on %s..." % self.nova_name)
        utils.checked_cmd([sshwait, self._get_connection_ip()], timeout=120)
        self._debug("SSH is up on %s!" % self.nova_name)

    def _get_private_key(self):
        with open(self.site_config['privkey']) as f:
            return paramiko.RSAKey.from_private_key(f)

    def _create_ssh_session(self):
        self._ssh_wait()
        if self.ssh is None:
            self.ssh = paramiko.client.SSHClient()
            self.ssh.set_missing_host_key_policy(
                paramiko.client.AutoAddPolicy())
        self.ssh.connect(self._get_connection_ip(),
                         pkey=self._get_private_key(),
                         username="root", look_for_keys=False)
        self.sftp = self.ssh.open_sftp()

    def _handle_ostree(self):

        ostree = self.spec['ostree']
        if type(ostree) is str:
            assert ostree == "latest"  # should've been checked by schema
            ostree = {}                # canonicalize to a dict
        assert type(ostree) is dict

        need_reboot = True
        allow_rc_77 = False
        if 'remote' not in ostree and 'branch' not in ostree:
            if 'revision' in ostree:
                action = ["deploy", ostree['revision']]
            else:
                action = ["upgrade", "--upgrade-unchanged-exit-77"]
            allow_rc_77 = True
        else:
            refspec = ""

            if 'remote' in ostree:
                self.run_checked_cmd(["ostree", "remote", "add", "papr",
                                      "--no-gpg-verify", ostree['remote']])
                refspec += "papr:"

            if 'branch' in ostree:
                refspec += ostree['branch']

            assert refspec != ""
            action = ["rebase", refspec]
            if 'revision' in ostree:
                action += [ostree['revision']]

        r = self.run_cmd(action)
        if r.rc == 77 and allow_rc_77:
            need_reboot = False
        elif r.rc != 0:
            logger.debug("Failed to deploy ostree: %s" % r.output)
            raise github.GitHubFriendlyStatusError('Failed to deploy ostree.')

        if need_reboot:
            self._reboot()

    def _on_atomic_host(self):
        return self.run_cmd(["test", "-f", "/run/ostreed"]).rc == 0

    def _reboot(self):
        sin, sout, serr = self.ssh.exec_command('/sbin/reboot')
        # wait for channel to close
        while not sout.channel.closed:
            time.sleep(1)
        self._create_ssh_session()

    def _debug(self, msg):
        if self.name is not None:
            logger.debug("%s [%s]" % (msg, self.name))
        else:
            logger.debug(msg)
