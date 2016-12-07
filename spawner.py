#!/usr/bin/env python3

# Parse the YAML file, start the testrunners in parallel,
# and wait for them.

import os
import sys
import traceback
import threading
import subprocess

from yaml.scanner import ScannerError
from pykwalify.errors import SchemaError

import utils.parser as parser
import utils.common as common
import utils.ghupdate as ghupdate


def main():
    "Main entry point."

    try:
        suites = parse_suites()
    except ScannerError:
        update_gh('error', "Red Hat CI", "YAML syntax error.")
    except SchemaError as e:
        # print the error to give feedback in the logs, but exit nicely
        traceback.print_exc()
        update_gh('error', "Red Hat CI", "YAML semantic error.")
    else:
        n = len(suites)
        if n > 0:
            spawn_testrunners(n)
            inspect_suite_failures(suites)
            update_required_context(suites)
        else:
            print("INFO: No testsuites to run.")


def parse_suites():

    yml_file = os.path.join('checkouts',
                            os.environ['github_repo'],
                            '.redhat-ci.yml')

    # this should have been checked already
    assert os.path.isfile(yml_file)

    suites = []
    branch = os.environ.get('github_branch')
    suite_parser = parser.SuiteParser(yml_file)
    for idx, suite in enumerate(suite_parser.parse()):
        if len(os.environ.get('RHCI_DEBUG_ALWAYS_RUN', '')) == 0:
            branches = suite.get('branches', ['master'])
            if branch is not None and branch not in branches:
                print("INFO: %s suite not defined to run for branch %s." %
                      (common.ordinal(idx + 1), branch))
                continue
        suite_dir = 'state/suite-%d/parsed' % len(suites)
        parser.flush_suite(suite, suite_dir)
        suites.append(suite)

    return suites


def spawn_testrunners(n):

    testrunner = os.path.join(sys.path[0], "testrunner")

    runners = []
    threads = []
    for i in range(n):
        p = subprocess.Popen([testrunner, str(i)],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        t = threading.Thread(target=read_pipe,
                             args=(i, p.stdout))
        t.start()
        runners.append(p)
        threads.append(t)

    # We don't implement any fail fast here, so just do a
    # naive wait to collect them all.
    failed = False
    for runner in runners:
        if runner.wait() != 0:
            failed = True

    for thread in threads:
        thread.join()

    # NB: When we say 'failed' here, we're talking about
    # infrastructure failure. Bad PR code should never cause
    # rc != 0.
    if failed:
        raise Exception("at least one runner failed")


def read_pipe(idx, fd):
    s = fd.readline()
    while s != b'':
        if not s.endswith(b'\n'):
            s += b'\n'
            # pylint: disable=no-member
        sys.stdout.buffer.write((b'[%d] ' % idx) + s)
        s = fd.readline()


def inspect_suite_failures(suites):

    for i, suite in enumerate(suites):
        assert 'rc' not in suite

        # If the rc file doesn't exist but the runner exited
        # nicely, then it means there was a semantic error
        # in the YAML (e.g. bad Docker image, bad ostree
        # revision, etc...).
        if not os.path.isfile("state/suite-%d/rc" % i):
            suite['rc'] = 1
        else:
            with open("state/suite-%d/rc" % i) as f:
                suite['rc'] = int(f.read().strip())

    # It's helpful to have an easy global way to figure out
    # if any of the suites failed, e.g. for integration in
    # Jenkins. Let's write a 'failures' file counting the
    # number of failed suites.
    with open("state/failures", "w") as f:
        f.write("%d" % count_failures(suites))


def count_failures(suites):
    return sum([int(suite['rc'] != 0) for suite in suites])


def update_required_context(suites):

    # only send 'required' context for branches
    if 'github_pull_id' in os.environ:
        return

    required_suites = [suite for suite in suites if suite.get('required')]
    total = len(required_suites)

    if total == 0:
        return

    # let's link to the branch overview itself
    url = 'https://github.com/%s/commits/%s' % (os.environ['github_repo'],
                                                os.environ['github_branch'])

    failed = count_failures(required_suites)
    update_gh('success' if failed == 0 else 'failure', 'required',
              "%d/%d PASSES" % (total - failed, total), url)


def update_gh(state, context, description, url=None):

    try:
        args = {'repo': os.environ['github_repo'],
                'commit': os.environ['github_commit'],
                'token': os.environ['github_token'],
                'state': state,
                'context': context,
                'description': description,
                'url': url}

        ghupdate.send(**args)

        if os.path.isfile('state/is_merge_sha'):
            with open('state/sha') as f:
                args['commit'] = f.read().strip()
            ghupdate.send(**args)

    # it can happen that the commit doesn't even exist
    # anymore, so let's be tolerant of such errors
    except ghupdate.CommitNotFoundException:
        pass


if __name__ == '__main__':
    sys.exit(main())
