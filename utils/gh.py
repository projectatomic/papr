#!/usr/bin/env python3

"""
Small utility to facilitate updating GitHub commit CI
status: https://developer.github.com/v3/repos/statuses/

Parameters are passed on the command-line. They can be
prefixed by 'env:' to denote a lookup in an environment
variable. E.g. --token env:token.
"""

import os
import sys
import json
import argparse
import requests
from simplejson.scanner import JSONDecodeError


class CommitNotFoundException(Exception):
    pass


def _main():
    "Main entry point."

    args = _parse_args()
    status(args.repo, args.commit, args.token, args.state,
           args.context, args.description, args.url)


def _parse_args():
    """
    Parses program arguments and optionally resolves
    pointers to environment variables.
    """

    parser = argparse.ArgumentParser()
    required_args = ['repo', 'commit', 'token', 'state']
    optional_args = ['context', 'description', 'url']
    for arg in required_args:
        parser.add_argument('--' + arg, required=True)
    for arg in optional_args:
        parser.add_argument('--' + arg)
    args = parser.parse_args()

    # resolve env vars, possibly to None (only allowed for optional args)
    for arg in required_args + optional_args:
        val = getattr(args, arg)
        if val is not None:
            if val.startswith('env:'):
                new_val = os.environ.get(val[4:])
                if new_val is None and arg in required_args:
                    parser.error(
                        "Parameter '%s' is required, but the given "
                        "environment variable '%s' is missing." % (
                            arg, val[4:]))
                setattr(args, arg, new_val)
            # we allow users to pass "" for optional vars to mean None so that
            # they don't have to resort to e.g. eval
            elif val == "":
                if arg in required_args:
                    parser.error(
                        "Parameter '%s' is required, but the given "
                        "argument is empty." % arg)
                setattr(args, arg, None)

    return args


def status(repo, commit, token, state,
           context=None, description=None, url=None):
    data = _craft_data_dict(state, context, description, url)
    _update_status(repo, commit, token, data)


def _craft_data_dict(state, context, description, url):
    "Creates the data dictionary as required by the API."

    data = {'state': state}
    if context is not None:
        data['context'] = context
    if description is not None:
        data['description'] = description
    if url is not None:
        data['target_url'] = url
    return data


def _update_status(repo, commit, token, data):
    "Sends the status update's data using the GitHub API."

    header = {'Authorization': 'token ' + token}
    api_url = ("https://api.github.com/repos/%s/statuses/%s" %
               (repo, commit))

    if __name__ == '__main__':
        eprint("Updating status of commit", commit, "with data", data)

    try:
        # use data= instead of json= in case we're running on an older requests
        resp = requests.post(api_url, data=json.dumps(data), headers=header)
        body = resp.json()
    except JSONDecodeError:
        eprint("Expected JSON, but received:")
        eprint("---")
        eprint(resp.content)
        eprint("---")
        eprint("Retrying...")
        resp = requests.post(api_url, data=json.dumps(data), headers=header)
        body = resp.json()

    # pylint: disable=no-member
    if resp.status_code != requests.codes.created:
        if (resp.status_code == requests.codes.unprocessable
                and body is not None and 'message' in body
                and "No commit found for SHA" in body['message']):
            raise CommitNotFoundException()

        # Some other error happened.
        errmsg = "Failed to update commit status [HTTP %d]" % resp.status_code
        errmsg += "\n" + str(resp.headers)
        if body is not None:
            errmsg += "\n" + str(body)
        raise Exception(errmsg)


# XXX: add CLI support and deduplicate with status()
def comment(repo, token, issue, text):
    "Creates a comment using the GitHub API."

    token_header = {'Authorization': 'token ' + token}
    api_url = ("https://api.github.com/repos/%s/issues/%d/comments" %
               (repo, issue))

    data = {'body': text}

    # use data= instead of json= in case we're running on an older requests
    resp = requests.post(api_url, data=json.dumps(data), headers=token_header)
    body = resp.json()

    # pylint: disable=no-member
    if resp.status_code != requests.codes.created:
        errmsg = "Failed to update commit status [HTTP %d]" % resp.status_code
        errmsg += "\n" + str(resp.headers)
        if body is not None:
            errmsg += "\n" + str(body)
        raise Exception(errmsg)


def eprint(*args):
    print(*args, file=sys.stderr)


if __name__ == '__main__':
    sys.exit(_main())
