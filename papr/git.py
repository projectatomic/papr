#!/usr/bin/env python3

import os
import subprocess


class Git:

    '''
        Simple git helper class which remembers the context directory.
    '''

    def __init__(self, dir, repo_url):
        self.dir = dir
        self.repo_url = repo_url
        self._git_env = dict(os.environ)
        self._git_env.update({
            "GIT_COMMITTER_NAME": "papr",
            "GIT_COMMITTER_EMAIL": "papr@example.com"
        })

    def update(self):
        # use .git here in case the clone fails
        if not os.path.isdir(os.path.join(self.dir, ".git")):
            os.makedirs(self.dir, exist_ok=True)
            self.clone()
        else:
            self.fetch()

    def cmd(self, *args):
        return subprocess.run(['git'] + list(args),
                              cwd=self.dir, check=True, env=self._git_env)

    def clone(self):
        return self.cmd("clone", self.repo_url, ".")

    def fetch(self, ref=None):
        args = ["fetch", "origin"]
        if ref is not None:
            args.append(ref)
        return self.cmd(*args)

    def get_rev(self, ref):
        p = subprocess.run(['git', "rev-parse", ref],
                           cwd=self.dir, check=True, env=self._git_env,
                           stdout=subprocess.PIPE)
        return p.stdout.strip().decode('ascii')

    def get_head(self):
        return self.get_rev("HEAD")

    def checkout(self, ref):
        return self.cmd("checkout", ref)
