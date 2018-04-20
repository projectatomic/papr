#!/usr/bin/env python3

import os
import re
import glob
import time
import shutil
import logging
import tempfile

from . import site
from . import utils
from . import github
from . import LOGGING_FORMAT_PREFIX

from .testenvs import container

logger = logging.getLogger("papr")

CHECKOUT_DIR = "/var/tmp/checkout"


class CmdTimeoutError(RuntimeError):
    pass


class CmdFailureError(RuntimeError):

    def __init__(self, rc):
        super().__init__()
        self.rc = rc


class TestSuiteRun:

    def __init__(self, test, suite_dict, pipe):
        self.test = test
        self.suite = TestSuite(suite_dict)
        self.name = suite_dict['context']
        self.testenv = None
        self.testenv_info = {}
        self.env_vars = {}
        # this is the dir we'll upload
        self.result_dir = tempfile.mkdtemp(prefix="papr-run.")
        # pipe to communicate back to parent
        self.pipe = pipe
        # dict we send back to parent
        self.run_results = {'completed': False, 'rc': 0,
                            'timed_out': False, 'publish_url': None}

    def run(self):

        # we're now running in our own process!
        # let's prepend the suite context in logging output
        for handler in logging.root.handlers:
            handler.setFormatter(logging.Formatter(
                LOGGING_FORMAT_PREFIX + "[%s] %%(message)s" % self.name
            ))

        # set up the publisher with our info for the indexer template
        site.publisher.set_template_vars(
            self.name, self.test.url, self.test.test_rev)

        spec = self.suite.get_testenv_spec()
        if self.suite.is_containerized():
            self.testenv = container.ContainerTestEnv(spec)
        # XXX not supported for now
        # elif self.suite.is_virtualized():
        #     self.testenv = host.HostTestEnv(spec)
        # elif self.suite.is_clustered():
        #     self.testenv = cluster.ClusterTestEnv(spec)
        else:
            raise Exception("unknown test environment")

        try:
            self._provision()
            self._prepare()
            self._run_tests()
            self._fetch_artifacts()
            self._publish_results()
            self._final_github_update()
            self.run_results['completed'] = True
        except github.GitHubFriendlyStatusError as e:
            self.update_github_status('failure', e.message)
        finally:
            shutil.rmtree(self.result_dir)
            self.testenv.teardown()
            self.pipe.send(self.run_results)

    def _provision(self):
        s = self.suite.get_testenv_type()
        self.update_github_status('pending', "Scheduling %s..." % s)
        self.testenv.provision()

    def _prepare(self):

        # self._inject_site_repos()

        # self._make_rpmmd_cache()

        # self._inject_extra_repos()

        self._copy_checkout()
        self._init_env_vars()

    def _run_tests(self):
        try:
            timeout = self.suite.get_timeout()
            buildcmds = self._assemble_build_api_cmds()
            testcmds = self.suite.get('tests', [])

            assert len(buildcmds) > 0 or len(testcmds) > 0

            if buildcmds:
                self.update_github_status('pending', "Building...")
                duration = self._run_logged_shell_cmds(buildcmds, "build.log",
                                                       CHECKOUT_DIR, timeout)
                timeout -= duration
                assert timeout > 0

            if testcmds:
                self.update_github_status('pending', "Running tests...")
                duration = self._run_logged_shell_cmds(testcmds, "output.log",
                                                       CHECKOUT_DIR, timeout)
                timeout -= duration
                assert timeout > 0

        except CmdFailureError as e:
            logger.debug("tests failed with rc %d" % e.rc)
            self.run_results['rc'] = e.rc
        except CmdTimeoutError:
            logger.debug("tests timed out")
            self.run_results['timed_out'] = True

    def _copy_checkout(self):
        self.testenv.run_checked_cmd(["mkdir", "-p", CHECKOUT_DIR])
        # XXX: wrap broken `oc cp` madness more sanely
        # https://github.com/openshift/origin/issues/17275
        self.testenv.copy_to_env(self.test.checkout_dir+'/.', CHECKOUT_DIR+'/')

    def _init_env_vars(self):
        # user-defined vars from YAML
        self.env_vars.update(self.suite.get_env_vars())
        vars = self.test.get_env_vars()
        # keep injecting under old name until all projects migrate
        for prefix in ["RHCI_", "PAPR_"]:
            for var, val in vars.items():
                self.env_vars[prefix + var] = val

    def _run_logged_shell_cmds(self, cmds, logfile, dir=None, timeout=None):

        total_duration = 0
        full_logfile = self._create_log_file(logfile)

        # write in binary mode since we directly pipe cmd output
        with open(full_logfile, mode='a+b') as f:
            for cmd in cmds:
                f.write(f">>> {cmd}\n".encode('utf-8'))
                r = self._run_shell_cmd(cmd, dir, timeout)
                shutil.copyfileobj(r.outf, f)
                f.write(b"\n")
                if timeout:
                    timeout -= r.duration
                total_duration += r.duration
                if r.rc is None or (timeout is not None and timeout < 0):
                    f.write(b"### TIMED OUT AFTER %ds\n" % r.duration)
                    raise CmdTimeoutError()
                else:
                    if r.rc != 0:
                        f.write(b"### EXITED WITH CODE %d AFTER %ds\n" %
                                (r.rc, r.duration))
                        raise CmdFailureError(r.rc)
                    else:
                        f.write(b"### COMPLETED IN %ds\n" % r.duration)

        return total_duration

    def _run_shell_cmd(self, cmd, dir=None, timeout=None):
        '''
        Write out a small shell script, send it, and execute it. It's easier
        and more portable to invoke and makes redirection simpler.
        '''
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8') as tmpf:
            tmpf.write("set -euo pipefail\nexec 2>&1\n")
            if dir:
                tmpf.write(f"cd '{dir}'\n")
            if self.env_vars:
                for k, v in self.env_vars.items():
                    tmpf.write(f'export {k}="{v}"\n')
            tmpf.write(cmd)
            tmpf.flush()
            # XXX: work around broken `oc cp` behaviour
            self.testenv.copy_to_env(tmpf.name, "/var/tmp/")
            fn = os.path.basename(tmpf.name)
            return self.testenv.run_cmd(["sh", f"/var/tmp/{fn}"], timeout)

    def _create_log_file(self, name):
        fullname = os.path.join(self.result_dir, name)
        with open(fullname, mode='w', encoding='utf-8') as f:
            f.write("### Date: %s\n" %
                    time.strftime("%a %b %d %H:%M:%S %Z %Y"))
            self.test.write_log_header(f)
            f.write("### Suite: %s\n" % self.name)
            # add build id to make it easy to trace back to Jenkins run
            if 'BUILD_ID' in os.environ:
                f.write("### BUILD_ID %s\n" % os.environ["BUILD_ID"])
        # XXX: should just return fd here, though callers want context mgrs
        return fullname

    def _assemble_build_api_cmds(self):
        cmds = []
        if not self.suite.uses_build_api():
            return cmds

        config_opts, build_opts, install_opts = self.suite.get_build_api_opts()

        def has_file(file):
            path = os.path.join(self.test.checkout_dir, file)
            return os.path.isfile(path)

        # https://github.com/cgwalters/build-api

        if not has_file('configure'):
            if has_file('autogen.sh'):
                cmds.append('NOCONFIGURE=1 ./autogen.sh')
            elif has_file('autogen'):
                cmds.append('NOCONFIGURE=1 ./autogen')

        cmds.append('./configure %s' % config_opts)
        ncpus = self.testenv.run_checked_cmd(['getconf', '_NPROCESSORS_ONLN'])
        cmds.append('make all --jobs %s %s' % (ncpus, config_opts))
        cmds.append('make install %s' % install_opts)
        return cmds

    def _fetch_artifacts(self):
        artifacts = self.suite.get('artifacts', [])
        if not artifacts:
            return
        dir = os.path.join(self.result_dir, "artifacts")
        if not os.path.isdir(dir):
            os.mkdir(dir)
        copied_one = False
        for artifact in artifacts:
            src = os.path.join(CHECKOUT_DIR, artifact)
            dest = os.path.join(dir, artifact)
            if self.testenv.copy_from_env(src, dest, allow_noent=True):
                copied_one = True
        if not copied_one:
            # nuke it so we don't upload an empty dir
            shutil.rmtree(dir)

    def _publish_results(self):
        self.run_results['publish_url'] = self.test.publish(self.result_dir)

    def _on_atomic_host(self):
        if self.suite.is_container_controlled():
            return False
        return self.testenv.run_query_cmd(["test", "-f", "/run/ostreed"])

    def update_github_status(self, state, msg, url=None):
        self.test.update_github_status(state, msg, self.name, url)

    def _final_github_update(self):
        if self.run_results['timed_out']:
            self.update_github_status('failure', 'Test timed out.',
                                      self.run_results['publish_url'])
        elif self.run_results['rc'] != 0:
            self.update_github_status('failure', 'Test failed with rc %d.' %
                                      self.run_results['rc'],
                                      self.run_results['publish_url'])
        else:
            self.update_github_status('success', 'All tests passed.',
                                      self.run_results['publish_url'])

    def _inject_site_repos(self):
        if 'repos' not in site.config:
            return
        for repo in site.config['repos']:
            if repo['distro_id'] != self._get_testenv_os_info('ID'):
                pass
            if 'distro_version_id' in repo:
                version_id = repo['distro_version_id']
                if version_id != self._get_testenv_os_info('VERSION_ID'):
                    pass
            repofile = repo['repo']
            self.testenv.copy_to_env(repofile, '/etc/yum.repos.d')

    def _make_rpmmd_cache(self):

        id = self._get_testenv_os_info('ID')
        version_id = self._get_testenv_os_info('VERSION_ID')

        if id == "" or version_id == "":
            logger.debug("Missing ID or VERSION_ID? Not injecting rpmmd cache")
            return

        mgr = "dnf" if id == "fedora" else "yum"
        testenv_cachedir = os.path.join("/var/cache", mgr)

        # XXX we just lock the whole cache dir since it's sometimes easier in
        # python to delete whole directories instead of contents of directories
        lockd = os.path.join(site.cachedir, "rpmmd")
        os.makedirs(lockd, exist_ok=True)

        cachedir = os.path.join(lockd, id, version_id)

        # if we have the cache for this id & version_id, inject it -- we copy
        # to a tmpdir first so that we don't have to keep it locked for long if
        # the testenv connection is slow
        if os.path.isdir(cachedir):
            with tempfile.TemporaryDirectory() as tmpd:
                tmp_copy = os.path.join(tmpd, "rpmmd-%s-%s" % (id, version_id))
                with utils.Flock(lockd, shared=True):
                    shutil.copytree(cachedir, tmp_copy, symlinks=True)
                self.testenv.copy_to_env(tmp_copy + "/.", testenv_cachedir)

        # update the cache
        logger.debug("running makecache")
        retries = 5
        for i in range(retries):
            r = self.testenv.run_cmd([mgr, 'makecache'])
            # r = self.testenv.run_cmd(['touch', '/var/cache/dnf/foo.solv'])
            if r.rc == 0:
                break
        else:
            out = r.outf.read().decode('utf-8')
            logger.debug(f"could not makecache: {out}")
            raise github.GitHubFriendlyStatusError("Could not makecache.")

        if not self.suite.can_trust_rpmmd():
            return

        # update our own cache with env cache only we can trust it
        with tempfile.TemporaryDirectory() as tmpd:
            self.testenv.copy_from_env(testenv_cachedir, tmpd)
            new_cache = os.path.join(tmpd, mgr)
            assert os.path.isdir(new_cache)

            # but only keep non-system solvs & repodata
            # NB: yum only keeps repo metadata there, so no need to prune
            if mgr == "dnf":
                for entry in glob.glob(new_cache + "/*"):
                    if (not os.path.isdir(entry) and
                            not entry.endswith(".solv") and
                            not entry.endswith(".solvx")):
                        logger.debug("deleting: %s" % entry)
                        os.remove(entry)
                system_solv = os.path.join(new_cache, '@System.solv')
                if os.path.isfile(system_solv):
                    logger.debug("deleting @System.solv")
                    os.remove(system_solv)

            with utils.Flock(lockd, shared=False):
                if os.path.isdir(cachedir):
                    shutil.rmtree(cachedir)
                # only create up to the dirname or copytree will barf
                os.makedirs(os.path.dirname(cachedir), exist_ok=True)
                shutil.copytree(new_cache, cachedir)

#    def _inject_extra_repos(self):
#        pass

    def _get_testenv_os_info(self, var):
        if var not in self.testenv_info:
            if self.testenv.run_query_cmd(['test', '-f', '/etc/os-release']):
                val = self.testenv.run_checked_cmd([
                    'sh', '-c', '. /etc/os-release && echo -n $%s' % var])
            self.testenv_info[var] = val
        return self.testenv_info[var]


class TestSuite:

    '''
        A thin wrapper around the raw dict to make queries nicer.
    '''

    def __init__(self, suite_dict):
        self.dict = suite_dict

    def is_containerized(self):
        return 'container' in self.dict

    def is_virtualized(self):
        return 'host' in self.dict

    def is_clustered(self):
        return 'cluster' in self.dict

    def is_container_controlled(self):
        if self.is_containerized():
            return True
        if self.is_clustered() and 'container' in self.dict['cluster']:
            return True
        return False

    def is_host_controlled(self):
        return not self.is_container_controlled()

    def get_testenv_spec(self):
        if self.is_containerized():
            return self.dict['container']
        elif self.is_virtualized():
            return self.dict['host']
        elif self.is_clustered():
            return self.dict['cluster']
        else:
            assert False

    def get_env_vars(self):
        return self.dict.get('env', {})

    def uses_build_api(self):
        return 'build' in self.dict

    def get_build_api_opts(self):
        assert self.uses_build_api()
        v = self.dict['build']

        if type(v) is bool and v:
            return ('', '', '')
        elif type(v) is dict:
            return (v.get('config-opts', ''),
                    v.get('build-opts', ''),
                    v.get('install-opts', ''))

    def get_testenv_type(self):
        if self.is_containerized():
            return "container"
        elif self.is_virtualized():
            return "host"
        elif self.is_clustered():
            return "cluster"
        else:
            assert False

    def can_trust_rpmmd(self):

        # we trust all the distros we offer
        if self.is_host_controlled():
            return True

        # find the image name
        if self.is_containerized():
            img = self.dict['container']['image']
        else:
            assert self.is_clustered()
            img = self.dict['cluster']['container']['image']

        # only trust official containers
        if (img.startswith('registry.fedoraproject.org') or
                img.startswith('registry.centos.org') or
                re.match('^(fedora|centos):[0-9]+$', img)):
            return True
        return False

    def get_timeout(self):
        return utils.str_to_timeout(self.dict.get('timeout', '2h'))

    def get(self, k, default=None):
        return self.dict.get(k, default)
