#!/usr/bin/env python3

import os
import shutil
import logging

import boto3
import boto3.session

from . import Publisher
from . import PKG_DIR

logger = logging.getLogger("papr")


class LocalPublisher(Publisher):

    def __init__(self, config):
        self.config = config
        self.root_dir = config['rootdir']

    def publish_dir(self, dir, dest_dir):
        final_dir = os.path.join(self.root_dir, dest_dir)
        logger.debug("publishing dir %s to %s" % (dir, final_dir))
        shutil.copytree(dir, final_dir)
        return os.path.abspath(final_dir)

    def publish_filedata(self, data, dest, content_type):
        full_path = os.path.join(self.root_dir, dest)
        logger.debug("publishing file %s" % dest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(data)
        return os.path.abspath(full_path)
