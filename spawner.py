#!/usr/bin/env python3

# Parse the YAML file, start the testrunners in parallel,
# and wait for them.

import os
import sys
import traceback
import subprocess

import utils.parser as parser
import utils.ghupdate as ghupdate


def main():
    "Main entry point."

    try:
        n = parse_suites()
    except SyntaxError as e:
        # print the error to give feedback, but exit nicely
        traceback.print_exc()
        msg = e.msg
        if e.__cause__ is not None:
            msg += ": " + e.__cause__.msg
        update_gh('error', msg)
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
    target_branch = os.environ['github_branch']
    for idx, suite in enumerate(parser.load_suites(yml_file)):
        if target_branch not in suite.get('branches', ['master']):
            print("INFO: %s suite not defined to run for branch %s." %
                  (parser.ordinal(idx + 1), target_branch))
            continue
        suite_dir = 'state/suite-%d/parsed' % nsuites
        parser.flush_suite(suite, suite_dir)
        nsuites += 1

    # return the number of testsuites
    return nsuites


def spawn_testrunners(n):

    testrunner = os.path.join(sys.path[0], "testrunner")

    runners = []
    for i in range(n):
        p = subprocess.Popen([testrunner, str(i)])
        runners.append(p)

    # We don't implement any fail fast here, so just do a
    # naive wait to collect them all.
    failed = False
    for runner in runners:
        if runner.wait() != 0:
            failed = True

    # NB: When we say 'failed' here, we're talking about
    # infrastructure failure. Bad PR code should never cause
    # rc != 0.
    if failed:
        raise Exception("at least one runner failed")


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
