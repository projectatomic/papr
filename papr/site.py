#!/usr/bin/env python3

import os
import yaml
import logging

from . import publishers

from .testenv import nova
from .testenv import docker

logger = logging.getLogger("papr")

# Just an easy way to store the site config globally. Might make sense to wrap
# in a class later on.
config = None
config_path = None
publisher = None
cachedir = None


def init(fpath):

    global config_path
    config_path = fpath

    _init_config()
    _init_publisher()
    _init_cachedir()


def _init_config():

    global config
    with open(config_path, encoding='utf-8') as f:
        filedata = f.read()

    # use CSafeLoader, because the default loader arbitrarily thinks
    # code points >= 0x10000 (like 🐄) are not valid:
    # https://bitbucket.org/xi/pyyaml/issues/26
    yaml.SafeLoader = yaml.CSafeLoader
    config = yaml.safe_load(filedata)

    # XXX: we should set up a schema and run pykwalify on it


def _init_publisher():

    global publisher

    type = config['publisher']['type']
    publisher_config = config['publisher']['config']
    if type == 'local':
        publisher = publishers.LocalPublisher(publisher_config)
    elif type == 's3':
        publisher = publishers.S3Publisher(publisher_config)
    else:
        raise Exception("unknown publisher type: %s" % type)


def _init_cachedir():
    global cachedir
    cachedir = config.get('cachedir', '/var/tmp/papr-cache')
    os.makedirs(cachedir, exist_ok=True)


def get_container_class():

    if ('container' not in config['backends'] or
            not config['backends']['container']):
        raise Exception("no container backend supported")

    type = config['backends']['container']['type']
    if type == 'docker':
        return docker.DockerTestEnv

    raise Exception("unknown container backend: %s" % type)


def get_host_class():

    if ('host' not in config['backends'] or
            not config['backends']['host']):
        raise Exception("no host backend supported")

    type = config['backends']['host']['type']
    if type == 'nova':
        return nova.NovaTestEnv

    raise Exception("unknown host backend: %s" % type)
