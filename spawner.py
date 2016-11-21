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
        n = parse_suites()
    except ScannerError:
        update_gh('error', "YAML syntax error.")
    except SchemaError as e:
        # print the error to give feedback in the logs, but exit nicely
        traceback.print_exc()
        update_gh('error', "YAML semantic error.")
    else:
        if n > 0:
            spawn_testrunners(n)
            count_failures(n)
        else:
            print("INFO: No testsuites to run.")


def parse_suites():

    yml_file = os.path.join('checkouts',
                            os.environ['github_repo'],
                            '.redhat-ci.yml')

    # this should have been checked already
    assert os.path.isfile(yml_file)

    nsuites = 0
    branch = os.environ.get('github_branch')
    for idx, suite in enumerate(parser.load_suites(yml_file)):
        if len(os.environ.get('RHCI_DEBUG_ALWAYS_RUN', '')) == 0:
            branches = suite.get('branches', ['master'])
            if branch is not None and branch not in branches:
                print("INFO: %s suite not defined to run for branch %s." %
                      (common.ordinal(idx + 1), branch))
                continue
        suite_dir = 'state/suite-%d/parsed' % nsuites
        parser.flush_suite(suite, suite_dir)
        nsuites += 1

    # return the number of testsuites
    return nsuites


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


def count_failures(n):

    # It's helpful to have an easy global way to figure out
    # if any of the suites failed, e.g. for integration in
    # Jenkins. Let's write a 'failures' file counting the
    # number of failed suites.

    failed = 0
    for i in range(n):
        # If the rc file doesn't exist but the runner exited
        # nicely, then it means there was a semantic error
        # in the YAML (e.g. bad Docker image, bad ostree
        # revision, etc...).
        if not os.path.isfile("state/suite-%d/rc" % i):
            failed += 1
        else:
            with open("state/suite-%d/rc" % i) as f:
                if int(f.read().strip()) != 0:
                    failed += 1

    with open("state/failures", "w") as f:
        f.write("%d" % failed)


def update_gh(state, description):

    args = {'repo': os.environ['github_repo'],
            'commit': os.environ['github_commit'],
            'token': os.environ['github_token'],
            'state': state,
            'context': 'Red Hat CI',
            'description': description}

    ghupdate.send(**args)

    if os.path.isfile('state/is_merge_sha'):
        with open('state/sha') as f:
            args['commit'] = f.read()
        ghupdate.send(**args)


if __name__ == '__main__':
    sys.exit(main())
