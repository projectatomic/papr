#!/usr/bin/env python

# This is just a trivial parser for now, but as we add more
# functionality to the .redhat-ci.yml spec, we will want to
# integrate pieces of the pipeline in here. E.g.
# provisioning, prereqs, test runs, etc...

import os
import sys
import yaml

output_dir = sys.argv[1]
yml_filename = sys.argv[2]

with open(yml_filename) as f:
    yml = yaml.load(f)

def write_to_file(fn, s):
    with open(os.path.join(output_dir, fn), 'w') as f:
        f.write(s);

if 'host' not in yml:
    print("ERROR: Missing 'host' entry in YAML.")
    exit(1)

if 'distro' not in yml['host']:
    print("ERROR: Missing 'distro' entry from 'host' in YAML.")
    exit(1)

if 'tests' not in yml:
    print("ERROR: Missing 'tests' entry in YAML.")
    exit(1)

write_to_file("distro", yml['host']['distro'])
write_to_file("tests", '\n'.join(yml['tests']))
write_to_file("branches", '\n'.join(yml.get('branches', ['master'])))
write_to_file("timeout", yml.get('timeout','2h'))
write_to_file("context", yml.get('context', 'Red Hat CI'))

if 'extra-repos' in yml:
    repos = ''
    for repo in yml['extra-repos']:
        repos += "[%s]\n" % repo['name']
        for key, val in repo.iteritems():
            repos += "%s=%s\n" % (key, val)
    if repos != "":
        write_to_file("extras.repo", repos)

if 'packages' in yml:
    write_to_file("packages", ' '.join(yml['packages']))

if 'artifacts' in yml:
    write_to_file("artifacts", '\n'.join(yml['artifacts']))
