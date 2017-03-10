#!/usr/bin/env python3

# Parse the YAML file, start the testrunners in parallel,
# and wait for them.

import os
import sys
import time
import traceback
import threading
import subprocess

import boto3
import jinja2

# XXX: switch to relative imports when we're a proper module
from papr import PKG_DIR
import papr.utils.parser as parser
import papr.utils.common as common
import papr.utils.gh as gh


def main():
    "Main entry point."

    try:
        suites = parse_suites()
    except parser.ParserError as e:
        # print the error to give feedback in the logs, but
        # exit nicely since this is not an infra failure
        traceback.print_exc()
        gh_status('error', "Red Hat CI", "Invalid YAML file.")
        if os.environ.get('github_pull_id'):
            gh_comment(':boom: Invalid `.papr.yml`: {}.'.format(e.msg))
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
                            '.papr.yml')

    # try new name, fall back to old name until projects migrate over
    for name in ['.papr.yml', '.papr.yaml', '.redhat-ci.yml']:
        yml_file = os.path.join('checkouts', os.environ['github_repo'], name)
        if os.path.isfile(yml_file):
            break
    else:
        # this should have been checked in main, so should never happen
        assert False, "No valid YAML file found"

    # are we supposed to run only some testsuites?
    only_contexts = os.environ.get('github_contexts')
    if only_contexts is not None:
        only_contexts = only_contexts.split('|')

    suites = []
    branch = os.environ.get('github_branch')
    suite_parser = parser.SuiteParser(yml_file)
    for idx, suite in enumerate(suite_parser.parse()):
        if len(os.environ.get('RHCI_DEBUG_ALWAYS_RUN', '')) == 0:
            branches = suite.get('branches', ['master'])
            if branch and branch not in branches:
                print("INFO: %s suite not defined to run for branch %s." %
                      (common.ordinal(idx + 1), branch))
                continue
            if not branch and not suite.get('pulls', True):
                print("INFO: %s suite not defined to run on pull requests." %
                      common.ordinal(idx + 1))
                continue
            if only_contexts and suite['context'] not in only_contexts:
                print("INFO: %s suite not in github_contexts env var." %
                      common.ordinal(idx + 1))
                continue
        suite_dir = 'state/suite-%d/parsed' % len(suites)
        parser.flush_suite(suite, suite_dir)
        suites.append(suite)

    return suites


def spawn_testrunners(n):

    testrunner = os.path.join(PKG_DIR, "testrunner")

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
    failed = []
    for i, runner in enumerate(runners):
        if runner.wait() != 0:
            failed.append(i)

    for thread in threads:
        thread.join()

    # NB: When we say 'failed' here, we're talking about
    # infrastructure failure. Bad PR code should never cause
    # rc != 0.
    if failed:
        raise Exception("the following runners failed: %s" % str(failed))


def read_pipe(idx, fd):
    # NB: We can't trust the output from the testrunner, so
    # just read it and write it back in binary mode.
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

    # Prepare a fallback URL in case something goes really wrong in the tester.
    # We just link back to the branch/PR for now, though we should probably
    # just capture the same text we used to update the commit status.
    if 'github_pull_id' in os.environ:
        fallback_url = ('https://github.com/%s/pull/%s' %
                        (os.environ['github_repo'],
                         os.environ['github_pull_id']))
    else:
        fallback_url = ('https://github.com/%s/commits/%s' %
                        (os.environ['github_repo'],
                         os.environ['github_branch']))

    # don't send 'required' context if we're only targeting some testsuites
    if 'github_contexts' in os.environ:
        return

    required_suites = [suite for suite in suites if suite.get('required')]
    total = len(required_suites)

    if total == 0:
        return

    # OK, let's upload a very basic index file that just
    # links to the results of all the required suites

    results_suites = []
    for i, suite in enumerate(suites):
        name = suite['context']
        if os.path.isfile("state/suite-%d/url" % i):
            with open("state/suite-%d/url" % i) as f:
                url = f.read().strip()
        else:
            # something went really wrong in the tester, just use fallback url
            url = fallback_url
        result = (suite['rc'] == 0)
        results_suites.append((name, result, url))

    tpl_fname = os.path.join(PKG_DIR, 'utils', 'required-index.j2')

    s3_key = '%s/%s/%s.%s/%s' % (os.environ['s3_prefix'],
                                 os.environ['github_repo'],
                                 os.environ['github_commit'],
                                 # rough equivalent of date +%s%N
                                 int(time.time() * 1e9),
                                 'index.html')

    with open(tpl_fname) as tplf:
        tpl = jinja2.Template(tplf.read(), autoescape=True)
        data = tpl.render(suites=results_suites)
        upload_to_s3(s3_key, data, 'text/html')

    url = 'https://s3.amazonaws.com/%s' % s3_key

    failed = count_failures(required_suites)
    gh_status('success' if failed == 0 else 'failure', 'required',
              "%d/%d PASSES" % (total - failed, total), url)


def gh_status(state, context, description, url=None):

    try:
        args = {'repo': os.environ['github_repo'],
                'commit': os.environ['github_commit'],
                'token': os.environ['github_token'],
                'state': state,
                'context': context,
                'description': description,
                'url': url}

        gh.status(**args)

        if os.path.isfile('state/is_merge_sha'):
            with open('state/sha') as f:
                args['commit'] = f.read().strip()
            gh.status(**args)

    # it can happen that the commit doesn't even exist
    # anymore, so let's be tolerant of such errors
    except gh.CommitNotFoundException:
        pass


def gh_comment(text):

    args = {'repo': os.environ['github_repo'],
            'token': os.environ['github_token'],
            'issue': int(os.environ['github_pull_id']),
            'text': text}

    gh.comment(**args)


def upload_to_s3(bucket_key, data, type):
    s3 = boto3.resource("s3")
    bucket, key = bucket_key.split('/', 1)
    s3.Object(bucket, key).put(Body=data, ContentType=type)


if __name__ == '__main__':
    sys.exit(main())
