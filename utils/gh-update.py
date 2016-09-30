#!/bin/python

'''
    Small utility to facilitate updating GitHub commit CI
    status: https://developer.github.com/v3/repos/statuses/

    Parameters are passed on the command-line. They can be
    prefixed by 'env:' to denote a lookup in an environment
    variable. E.g. --token env:token.
'''


import os
import sys
import json
import argparse
import requests


def main():
    "Main entry point."

    args = parse_args()
    if args is None:
        return 1

    data = craft_data_dict(args.state,
                           args.context,
                           args.description,
                           args.url)

    if not update_status(args.repo,
                         args.commit,
                         args.token,
                         data):
        return 1


def parse_args():

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
                    print "Parameter '%s' is required, but the given" % arg,
                    print "environment variable '%s' is missing." % val[4:]
                    return None
                setattr(args, arg, new_val)
            # we allow users to pass "" for optional vars to mean None so that
            # they don't have to resort to e.g. eval
            elif val == "":
                if arg in required_args:
                    print "Parameter '%s' is required, but the given" % arg,
                    print "argument is empty."
                    return None
                setattr(args, arg, None)

    return args


def craft_data_dict(state, context, description, url):

    "Creates the data dictionary as required by the API."

    data = {'state': state}
    if context is not None:
        data['context'] = context
    if description is not None:
        data['description'] = description
    if url is not None:
        data['target_url'] = url
    return data


def update_status(repo, commit, token, data):

    "Sends the status update's data using the GitHub API."

    token_header = {'Authorization': 'token ' + token}
    api_url = ("https://api.github.com/repos/%s/statuses/%s" %
               (repo, commit))

    print "Updating status of commit", commit, "with data", data

    # use data= instead of json= in case we're running on an older requests
    resp = requests.post(api_url, data=json.dumps(data), headers=token_header)

    if resp.status_code != requests.codes.created: # pylint: disable=no-member
        print "Failed to update commit status [HTTP %d]" % resp.status_code
        print resp.headers
        print resp.json()
        return False

    return True

if __name__ == '__main__':
    sys.exit(main())
