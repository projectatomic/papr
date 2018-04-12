#!/usr/bin/env python3

import os
import logging
# XXX import tempfile

from . import site
from . import parser
from . import test

logger = logging.getLogger("papr")


def add_cli_parsers(subparsers):
    runtest = subparsers.add_parser('runtest', help="run a test")
    runtest.add_argument('--conf', metavar='SITE.YAML', default='site.yaml',
                         help="Site configuration file (default: site.yaml)")
    runtest.add_argument('--repo', metavar='OWNER/REPO',
                         help="GitHub repo to test", required=True)
    runtest.add_argument('--expected-sha1', metavar='SHA1',
                         help="Expected SHA1 of commit to test")
    runtest.add_argument('--suite', metavar='CONTEXT', action='append',
                         help="Testsuites to run (defaults to all)")
    branch_or_pull = runtest.add_mutually_exclusive_group(required=True)
    branch_or_pull.add_argument('--branch', help="GitHub branch to test")
    branch_or_pull.add_argument('--pull', metavar='ID', type=int,
                                help="GitHub pull request ID to test")
    runtest.set_defaults(func=_cmd_runtest)


def _cmd_runtest(args):

    # initialize global site-specific information
    site.init(args.conf)

    if args.branch is not None:
        tst = test.BranchTest(args.repo, args.branch)
    else:
        tst = test.PullTest(args.repo, args.pull)

    head_sha1 = tst.checkout_ref()
    if args.expected_sha1 is not None and args.expected_sha1 != head_sha1:
        # graciously accept ref race conditions; we're meant to be run in
        # an automated flow, which means that another run with the correct
        # expected sha1 is imminent
        logger.info("SHA1 mismatch for %s: expected %s, got %s",
                    tst.ref, args.expected_sha1, head_sha1)
        logger.info("exiting quietly...")
        return

    try:
        tst.find_papr_yaml()
    except Exception as e:
        logger.exception("exiting quietly...")
        return

    try:
        tst.parse_suites()

        if args.suite:
            found_ctxs = [suite['context'] for suite in tst.suites]
            tst.filter_suites(args.suite)
            if len(tst.suites) != len(args.suite):
                # user probably did a typo; help them
                bad_ctxs = [ctx for ctx in args.suite if ctx not in found_ctxs]
                raise Exception("Undefined contexts: %s (found: %s)" %
                                (bad_ctxs, found_ctxs))

    except parser.ParserError as e:

        # print the error to give feedback in the logs, but exit nicely
        # (i.e. don't reraise) since this is not an infra failure

        basename = os.path.basename(tst.yamlf)
        msg = "Invalid YAML file `%s`" % basename
        logger.exception(msg)
        tst.update_github_status('error', msg + '.')
        tst.write_github_comment(':boom: {}: {}.\n\nYou can use '
                                 '`papr validate {}` to validate your YAML '
                                 'file.'.format(msg, e.msg, basename))
        return

    except Exception as e:
        tst.update_github_status('error', 'An internal error occurred.')
        raise

    if len(tst.suites) == 0:
        logger.info("no active suites to run, exiting quietly...")
        return

    tst.run_suites()
