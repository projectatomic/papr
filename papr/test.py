#!/usr/bin/env python3

import os
import time
import logging
import subprocess
import jinja2

import multiprocessing as mp

from . import PKG_DIR
from . import git
from . import github
from . import parser
from . import testrun
from . import site

logger = logging.getLogger("papr")


class Test():

    def __init__(self, repo):
        self.repo = repo
        self.checkout_dir = os.path.join(site.cachedir, "checkouts", self.repo)
        self.git = git.Git(self.checkout_dir, "https://github.com/" + repo)
        self.github = github.GitHub(repo)
        self.git.update()
        # branch/PR head; but for PRs we actually test the merge commit
        self.rev = None
        # what we actually test, same as rev except for PRs with no conflicts
        self.test_rev = None
        self.yamlf = None
        self.suites = None
        self.results = {}

    def find_papr_yaml(self):

        if self.yamlf:
            return

        # try new name, fall back to old name until projects migrate over
        for name in ['.papr.yml', '.papr.yaml', '.redhat-ci.yml']:
            f = os.path.join(self.checkout_dir, name)
            if os.path.isfile(f):
                self.yamlf = f
                return

        raise Exception("No PAPR YAML file found in repo root!")

    def parse_suites(self):

        assert self.yamlf
        self.suites = []

        suite_parser = parser.SuiteParser(self.yamlf)
        for idx, suite in enumerate(suite_parser.parse()):
            if self._is_active_suite(suite):
                self.suites.append(suite)

    def _is_active_suite(self, suite):
        raise Exception("not implemented")

    def filter_suites(self, target_suites):
        assert self.suites
        self.suites = [s for s in self.suites if s['context'] in target_suites]

    def run_suites(self):
        assert self.suites
        self._spawn_suites()
        self._update_required_context()

    def _spawn_suites(self):

        '''
            This is the part where things get interesting. We spawn one child
            process for each suite. I spent some time debating and researching
            between threads vs. procs. To summarize: multiprocessing allows us
            to avoid the GIL, which is relevant to us because although we spend
            most of our time waiting on tests to finish, we still have a lot of
            business logic chunks interspersed between those wait()s. Scaling
            up to e.g. 8 testsuites (which at least one GitHub repo hooked up
            to PAPR has right now) would have made the GIL's shortcomings even
            more obvious. Also, we don't actually have much data that we need
            back from suite runs, which would've been threading's advantage.
        '''

        procs = {}
        pipes = {}
        for suite in self.suites:
            parent_pipe, child_pipe = mp.Pipe()
            run = testrun.TestSuiteRun(self, suite, child_pipe)
            p = mp.Process(target=run.run)
            procs[p] = suite
            p.start()
            pipes[suite['context']] = parent_pipe

        # We don't implement any fail fast here, so just do a
        # naive wait to collect them all.
        failed = []
        for p, suite in procs.items():
            p.join()
            ctx = suite['context']
            if p.exitcode != 0:
                failed.append(ctx)
            else:
                self.results[ctx] = pipes[ctx].recv()
                logger.debug('results for suite "%s": %s' %
                             (ctx, self.results[ctx]))

        # NB: When we say 'failed' here, we're talking about
        # infrastructure failure. Bad PR code should never cause
        # rc != 0.
        if len(failed) > 0:
            raise Exception("the following suites failed: %s" % str(failed))

    def _update_required_context(self):

        # only send 'required' context for branches for now
        if not isinstance(self, BranchTest):
            return

        required_suites = [s for s in self.suites if s.get('required')]
        total = len(required_suites)
        if total == 0:
            return

        # OK, let's upload a very basic index file that just
        # links to the results of all the required suites
        logger.debug("inspecting %d required suites" % total)

        failures = 0
        results_suites = []
        for suite in required_suites:
            name = suite['context']
            result = self.results[name]
            if not result['completed']:
                passed = False
            else:
                passed = (result['rc'] == 0
                          if not result['timed_out'] else False)
            if not passed:
                failures += 1
            results_suites.append((name, passed, result['publish_url']))

        tpl_fname = os.path.join(PKG_DIR, 'templates', 'required-index.j2')
        with open(tpl_fname) as tplf:
            tpl = jinja2.Template(tplf.read(), autoescape=True)

        data = tpl.render(suites=results_suites)
        dest = '%s/%s.%s/%s' % (self.repo, self.rev,
                                int(time.time() * 1e9), 'index.html')
        url = site.publisher.publish_filedata(data, dest, 'text/html')
        self.update_github_status('success' if failures == 0 else 'failure',
                                  "%d/%d PASSES" % (total - failures, total),
                                  'required', url)

    # this is called by the individual testsuites
    def publish(self, dir):
        # use a timestamp to allow re-running at the same rev w/o overwriting
        dest_dir = "%s/%s.%s" % (self.repo, self.rev, int(time.time() * 1e9))
        return site.publisher.publish_dir(dir, dest_dir)

    def update_github_status(self, status, msg, context=None, url=None):
        raise Exception("not implemented")


class BranchTest(Test):

    def __init__(self, repo, branch):
        super().__init__(repo)
        self.branch = branch
        self.url = f"https://github.com/{self.repo}/commits/{self.branch}"

    def checkout_ref(self):
        '''Check out the target branch and return the SHA1 of HEAD'''
        self.git.fetch(self.branch)
        self.git.checkout("FETCH_HEAD")
        self.rev = self.git.get_head()
        self.test_rev = self.rev
        return self.rev

    def update_github_status(self, status, msg, context=None, url=None):
        self.github.status(self.rev, status, context, msg, url)

    def write_github_comment(self, msg):
        # nowhere to easily comment for branch tests
        # XXX: or should we comment on the commit itself?
        pass

    def _is_active_suite(self, suite):
        # XXX: should query github for default branch
        branches = suite.get('branches', ['master'])
        if self.branch not in branches:
            logger.debug("not running suite '%s' on branch '%s'",
                         suite['context'], self.branch)
            return False
        return True

    def get_env_vars(self):
        return {'REPO': self.repo,
                'COMMIT': self.rev,
                'BRANCH': self.branch}

    def write_log_header(self, f):
        f.write(f"### Revision: {self.rev} (branch {self.branch})\n")
        f.write(f"### URL: {self.url}\n")


class PullTest(Test):

    def __init__(self, repo, pull_id):
        super().__init__(repo)
        self.pull_id = pull_id
        self.is_merge_rev = False
        self.url = f"https://github.com/{self.repo}/pull/{self.pull_id}"

    def checkout_ref(self):
        '''Check out the target pull request and return the SHA1 of HEAD'''

        # try to fetch the merge commit, otherwise, just use the head
        try:
            self.git.fetch("refs/pull/%d/merge" % self.pull_id)
            self.rev = self.git.get_rev("FETCH_HEAD^2")
            self.test_rev = self.git.get_rev("FETCH_HEAD")
            self.is_merge_rev = True
        except subprocess.CalledProcessError:
            self.git.fetch("refs/pull/%d/head" % self.pull_id)
            self.rev = self.git.get_rev("FETCH_HEAD")
            self.test_rev = self.rev
            self.is_merge_rev = False

        self.git.checkout("FETCH_HEAD")
        return self.rev

    def update_github_status(self, status, msg, context=None, url=None):
        self.github.status(self.rev, status, context, msg, url)
        # also update merge commit; this is useful for homu's status-based
        # exemptions: https://github.com/servo/homu/pull/54
        if self.is_merge_rev:
            self.github.status(self.test_rev, status, context, msg, url)

    def write_github_comment(self, msg):
        self.github.comment(self.pull_id, msg)

    def _is_active_suite(self, suite):
        if not suite.get('pulls', True):
            logger.debug("not running suite '%s' on PR %d",
                         suite['context'], self.pull_id)
            return False
        return True

    def get_env_vars(self):
        d = {'REPO': self.repo,
             'COMMIT': self.rev,
             'PULL_ID': str(self.pull_id)}
        if self.is_merge_rev:
            d['MERGE_COMMIT'] = self.test_rev
        return d

    def write_log_header(self, f):
        f.write(f"### Revision: {self.rev} (PR #{self.pull_id})\n")
        f.write(f"### URL: {self.url}")
        if not self.is_merge_rev:
            f.write(" (WARNING: not merge commit, check for conflicts)")
        f.write("\n")
