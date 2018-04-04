#!/usr/bin/env python3

import os
import yaml
import logging

from .publishers import local
from .publishers import s3

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
        publisher = local.LocalPublisher(publisher_config)
    elif type == 's3':
        publisher = s3.S3Publisher(publisher_config)
    else:
        raise Exception("unknown publisher type: %s" % type)


def _init_cachedir():
    global cachedir
    cachedir = config.get('cachedir', '/var/cache/papr')
    os.makedirs(cachedir, exist_ok=True)
