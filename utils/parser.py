#!/usr/bin/env python3

# This is just a trivial parser for now, but as we add more
# functionality to the .redhat-ci.yml spec, we will want to
# integrate pieces of the pipeline in here. E.g.
# provisioning, prereqs, test runs, etc...

import re
import os
import sys
import yaml
import shlex
import argparse

import utils.common as common

from pykwalify.core import Core
from pykwalify.errors import SchemaError


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
            except SchemaError as e:
                # if it happens on the very first document, let's just give the
                # exact error directly
                if idx == 0:
                    raise e
                msg = "failed to parse %s testsuite" % common.ordinal(idx + 1)
                raise SchemaError(msg) from e


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

    schema = os.path.join(sys.path[0], "utils/schema.yml")
    ext = os.path.join(sys.path[0], "utils/ext_schema.py")
    c = Core(source_data=suite, schema_files=[schema], extensions=[ext])
    c.validate()

    if suite['context'] in contexts:
        raise SchemaError("duplicate 'context' value detected")

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
            assert type(val) in [str, dict]
            if type(val) is str:
                assert val == "latest"
                write_to_file("ostree_revision", "")
            else:
                write_to_file("ostree_remote", val.get('remote', ''))
                write_to_file("ostree_branch", val.get('branch', ''))
                write_to_file("ostree_revision", val.get('revision', ''))
        write_to_file("distro", host['distro'])

    if 'container' in suite:
        write_to_file("image", suite['container']['image'])

    write_to_file("tests", '\n'.join(suite['tests']))
    write_to_file("branches", '\n'.join(suite.get('branches', ['master'])))

    timeout = common.str_to_timeout(suite.get('timeout', '2h'))
    write_to_file("timeout", str(timeout))

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
            envs += 'export %s=%s\n' % (k, shlex.quote(v))
        write_to_file("envs", envs)

    if 'build' in suite:
        v = suite['build']
        if type(v) is bool and v:
            write_to_file("build", '')
        elif type(v) is dict:
            write_to_file("build", '')
            write_to_file("build.config_opts", v.get('config-opts', ''))
            write_to_file("build.build_opts", v.get('build-opts', ''))
            write_to_file("build.install_opts", v.get('install-opts', ''))


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
