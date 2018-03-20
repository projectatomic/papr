#!/usr/bin/env python3

# There's a couple of nice libraries out there that will wrap the whole GitHub
# API for you, though it feels like a lot of overhead and added deps (of deps)
# when we just need two simple access points (status & comment). Might make
# more sense later on if for some reason we need to use more GitHub APIs.

import os
import requests
from simplejson.scanner import JSONDecodeError
import logging

from . import site

logger = logging.getLogger("papr")


GITHUB_API_URL = "https://api.github.com"


class GitHubApiError(Exception):

    def __init__(self, url, response, message):
        self.url = url
        self.response = response
        self.message = message


class GitHubCommitNotFoundError(Exception):
    pass


class GitHubFriendlyStatusError(Exception):

    '''
        This can be used to percolate up a specific status update for an error.
        It is used when a user-provided value may not be correct.
    '''

    def __init__(self, message):
        self.message = message


class GitHub:

    def __init__(self, repo):
        self.repo = repo

        # try to fetch token from site config
        self.token = None
        if 'github' in site.config:
            if site.config['github'].get('auth-from-env', False):
                self.token = os.environ['GITHUB_TOKEN']
            else:
                self.token = site.config['github'].get('auth-token', None)

    def status(self, commit, state, context=None, description=None, url=None):

        assert state in ["pending", "success", "error", "failure"]

        data = {'state': state}
        if context is not None:
            data['context'] = context
        if description is not None:
            data['description'] = description
        if url is not None and (url.startswith('http://') or
                                url.startswith('https://')):
            data['target_url'] = url

        try:
            self._post("statuses/%s" % commit, data)
        # check if it's actually because the commit wasn't found
        except GitHubApiError as e:
            body = e.response.body()

            # This is hacky, but for some reason for the status API, GitHub
            # doesn't give semantically valid fields we could look up to check
            # what the error was (as described in
            # https://developer.github.com/v3/#client-errors). We could
            # alternatively just check that the commit exists beforehand but
            # there'd still be a race condition.
            # pylint: disable=no-member
            if (e.response.status_code == requests.codes.unprocessable
                    and body is not None and 'message' in body
                    and "No commit found for SHA" in body['message']):
                raise GitHubCommitNotFoundError()
            raise  # otherwise, just reraise it

    def comment(self, issue, text):
        data = {'body': text}
        self._post("issues/%d/comments" % issue, data)

    def _post(self, endpoint, data):

        logger.info("GitHub POST to '%s' with '%s'" % (endpoint, data))

        # we support not specifying a token to just output POSTs in the logger
        if self.token is None:
            return

        header = {'Authorization': 'token ' + self.token}
        url = "{api}/repos/{repo}/{endpoint}".format(api=GITHUB_API_URL,
                                                     repo=self.repo,
                                                     endpoint=endpoint)

        try:
            resp = requests.post(url, json=data, headers=header)
            # the GitHub API servers are flaky sometimes; check if we got valid
            # JSON and if not, let's try again just once
            resp.json()
        except JSONDecodeError:
            logger.warning("expected JSON, but received: %s", resp.content)
            logger.warning("retrying...")
            resp = requests.post(url, json=data, headers=header)

        # pylint: disable=no-member
        if resp.status_code != requests.codes.created:
            raise GitHubApiError(url, resp, "POST didn't return HTTP 201")
