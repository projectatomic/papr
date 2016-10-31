#!/usr/bin/env python3

# This is just a trivial parser for now, but as we add more
# functionality to the .redhat-ci.yml spec, we will want to
# integrate pieces of the pipeline in here. E.g.
# provisioning, prereqs, test runs, etc...

import re
import os
import yaml
import shlex
import argparse


def load_suites(filepath):
    "Generator of testsuites parsed from the given YAML file."

    suite = None
    contexts = []
    with open(filepath) as f:
        for idx, raw_yaml in enumerate(yaml.safe_load_all(f.read())):
            try:
                suite = _merge(suite, raw_yaml)
                _validate(suite, contexts)
                yield suite
            except SyntaxError as e:
                # if it happens on the very first document, let's just give the
                # exact error directly
                if idx == 0:
                    raise e
                msg = "failed to parse %s testsuite" % ordinal(idx + 1)
                raise SyntaxError(msg) from e


def _merge(suite, new):
    "Merge the next document into the current one."

    if type(new) is not dict:
        raise SyntaxError("top-level type should be a dict")

    if suite is None:

        # The 'context' key is special. It's optional on the
        # first suite (defaulting to 'Red Hat CI'), but
        # required on subsequent suites.
        if 'context' not in new:
            new['context'] = "Red Hat CI"

    if 'inherit' in new and type(new['inherit']) is not bool:
        raise SyntaxError("expected 'bool' value for 'inherit' key")

    # if we're not inheriting, then let's just return the new suite itself
    if suite is None or not new.get('inherit', False):
        return _normalize(new.copy())

    assert type(suite) is dict

    # apply some helper conversions
    if 'container' in suite and 'host' in new:
        del suite['container']
    elif 'host' in suite and 'container' in new:
        del suite['host']

    # we always expect a new context key
    del suite['context']

    suite.update(new)

    return _normalize(suite)


def _normalize(suite):
    for k, v in list(suite.items()):
        if k == 'inherit' or v is None:
            del suite[k]
    return suite


def _validate(suite, contexts):

    # XXX: We need a proper full schema validation here.
    # Maybe using: https://pypi.python.org/pypi/pykwalify
    # Probably better to just merge this with flush_suite()
    # since it does the real validation on-the-fly.

    if 'host' in suite and 'container' in suite:
        raise SyntaxError("expected only one of 'host' and 'container'")
    elif 'host' in suite:
        if 'distro' not in suite['host']:
            raise SyntaxError("expected 'distro' entry in 'host' dict")
    elif 'container' in suite:
        if 'image' not in suite['container']:
            raise SyntaxError("expected 'image' entry in 'container' dict")
    else:
        raise SyntaxError("expected one of 'host' or 'container'")

    if 'extra-repos' in suite:
        repos = suite['extra-repos']
        if type(repos) is not list:
            raise SyntaxError("expected a list of dicts for 'extra-repos'")
        for i, repo in enumerate(suite['extra-repos']):
            if type(repo) is not dict:
                raise SyntaxError("expected a list of dicts for 'extra-repos'")
            if 'name' not in repo:
                raise SyntaxError("expected 'name' key in extra repo %d" % i)

    if 'tests' not in suite or type(suite['tests']) is not list:
        raise SyntaxError("expected a list for 'tests'")

    if 'context' not in suite:
        raise SyntaxError("expected 'context' key")

    if suite['context'] in contexts:
        raise SyntaxError("duplicate 'context' value detected")

    contexts.append(suite['context'])


def flush_suite(suite, outdir):

    def write_to_file(fn, s):
        with open(os.path.join(outdir, fn), 'w') as f:
            f.write(s)

    os.makedirs(outdir)

    if 'host' in suite:
        host = suite['host']
        if 'ostree' in host:
            val = host['ostree']
            if type(val) is str:  # latest
                if val != "latest":
                    raise SyntaxError("invalid value for 'ostree' key" % val)
                write_to_file("ostree_revision", "")
            elif type(val) is dict:
                write_to_file("ostree_remote", val.get('remote', ''))
                write_to_file("ostree_branch", val.get('branch', ''))
                write_to_file("ostree_revision", val.get('revision', ''))
            else:
                raise SyntaxError("expected str or dict for 'ostree' key")
        write_to_file("distro", host['distro'])

    if 'container' in suite:
        write_to_file("image", suite['container']['image'])

    write_to_file("tests", '\n'.join(suite['tests']))
    write_to_file("branches", '\n'.join(suite.get('branches', ['master'])))
    write_to_file("timeout", suite.get('timeout', '2h'))
    write_to_file("context", suite.get('context'))

    if 'extra-repos' in suite:
        repos = ''
        for repo in suite['extra-repos']:
            repos += "[%s]\n" % repo['name']
            for key, val in repo.items():
                repos += "%s=%s\n" % (key, val)
        if repos != "":
            write_to_file("rhci-extras.repo", repos)

    if 'packages' in suite:
        packages = []
        for pkg in suite['packages']:
            packages.append(shlex.quote(pkg))
        write_to_file("packages", ' '.join(packages))

    if 'artifacts' in suite:
        write_to_file("artifacts", '\n'.join(suite['artifacts']))

    if 'env' in suite:
        envs = ''
        for k, v in suite['env'].items():
            if re.match('[a-zA-Z_][a-zA-Z0-9_]*', k) is None:
                raise SyntaxError("invalid env var name '%s'" % k)
            v = shlex.quote(v)
            envs += 'export %s=%s\n' % (k, v)
        write_to_file("envs", envs)


# http://stackoverflow.com/a/39596504/308136
# XXX: move to a generic util module
def ordinal(n):
    suffix = ['th', 'st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'th', 'th']
    if n < 0:
        n *= -1
    n = int(n)

    if n % 100 in (11, 12, 13):
        s = 'th'
    else:
        s = suffix[n % 10]

    return str(n) + s


if __name__ == '__main__':

    # Just dump each parsed document in indexed subdirs of
    # output_dir. Useful for testing and validating.

    argparser = argparse.ArgumentParser()
    argparser.add_argument('--yml-file', required=True)
    argparser.add_argument('--output-dir', required=True)
    args = argparser.parse_args()

    for idx, suite in enumerate(load_suites(args.yml_file)):
        suite_dir = os.path.join(args.output_dir, str(idx))
        flush_suite(suite, suite_dir)
