#!/usr/bin/env python3

# Convert a papr YAML file into a Kubernetes Job

import os
import sys
import re
import time
import yaml
import traceback
import argparse
import subprocess

# XXX: switch to relative imports when we're a proper module
from papr import PKG_DIR
import papr.utils.parser as paprparser

GH_NAME_REGEX = re.compile('^[A-Za-z0-9_.-]+$')

def paprsuite2kubejob(gh_org, gh_repo, commitsha, suiteidx, suite):
    commitsha_short = commitsha[0:10]
    name = 'papr-{}-{}-{}-{}'.format(gh_org, gh_repo, commitsha_short, suiteidx)
    metadata = {'name': name}
    cmd = 'set -xeuo pipefail\n'
    for test in suite['tests']:
        cmd += test + '\n'
    volumes = [
        {'name': 'builddir', 'emptyDir': {}}
    ]
    containers = [{
        'name': name,
        'image': suite['container']['image'],
        'volumeMounts': [
            { 'name': 'builddir',
              'mountPath': '/srv',
            }
        ],
        'securityContext': {'runAsUser': 0},
        'workingDir': '/srv/build',
        'command': ["/usr/bin/bash", "-c", cmd],
    }]
    initContainers = [
        { 'name': 'init-git',
          'image': 'registry.centos.org/centos/centos:7',
          'volumeMounts': [
              { 'name': 'builddir',
                'mountPath': '/srv',
              }
          ],
          'securityContext': {'runAsUser': 0},
          'workingDir': '/srv/',
          'command': ['/bin/sh', '-c',
                      '''set -xeuo pipefail; yum -y install git
                      git clone --depth=100 https://github.com/{gh_org}/{gh_repo} build
                      cd build
                      git checkout {commitsha}'''.format(gh_org=gh_org, gh_repo=gh_repo, commitsha=commitsha)]
        }
    ]
    r = {'apiVersion': 'batch/v1',
         'kind': 'Job',
         'metadata': metadata,
         'spec': {
             'template': {
                 'metadata': dict(metadata),
                 'spec': {
                     'volumes': volumes,
                     'initContainers': initContainers,
                     'containers': containers,
                     'restartPolicy': 'Never'
                 },
             },
         },
    }
    return r

def main():
    "Main entry point."

    parser = argparse.ArgumentParser(description='Convert .papr.yml to Kuberentes Jobs')
    parser.add_argument('--limit', action='store', type=int, help='Emit at most N jobs')
    parser.add_argument('ghid', action='store', help='github repo')
    parser.add_argument('commitsha', action='store', help='commit sha')
    parser.add_argument('path', action='store', help='Path to papr YAML (normally .papr.yml)')
    args = parser.parse_args()

    (org,proj) = args.ghid.split('/', 1)
    assert GH_NAME_REGEX.match(org)
    assert GH_NAME_REGEX.match(proj)

    suite_parser = paprparser.SuiteParser(args.path)
    suites = suite_parser.parse()

    stream = sys.stdout
    stream.write('# Generated from papr YAML: {}\n'.format(os.path.basename(args.path)))
    jobs = []
    joblist = {'apiVersion': 'v1',
               'kind': 'List',
               'items': jobs}
    for i,suite in enumerate(suites):
        if not suite.get('container'):
            continue
        jobs.append(paprsuite2kubejob(org, proj, args.commitsha, i, suite))
        if len(jobs) == args.limit:
            break
    yaml.dump(joblist, stream=stream, explicit_start=True)

if __name__ == '__main__':
    sys.exit(main())
