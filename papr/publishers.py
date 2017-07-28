#!/usr/bin/env python3

import os
import shutil
import logging

import boto3
import boto3.session

from . import PKG_DIR
from . import utils

logger = logging.getLogger("papr")


class LocalPublisher:

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


class S3Publisher:

    def __init__(self, config):
        self.config = config
        self.bucket = config['bucket']
        self.root_dir = config.get('rootdir', None)

        key_id = None
        access_key = None
        if not self.config.get('auth-from-env'):
            key_id = self.config['auth-key-id']
            access_key = self.config['auth-secret-key']
        self.session = boto3.Session(aws_access_key_id=key_id,
                                     aws_secret_access_key=access_key)

    def publish_dir(self, dir, dest_dir):
        # XXX: convert to python/boto3; should be able to just walk the tree
        # and collect filenames

        default_obj = self._get_default_object(dir)
        if default_obj == 'index.html':
            self._run_indexer(dir)

        full_path = os.path.join(self.bucket, self.root_dir, dest_dir)
        logger.debug("publishing dir %s to s3://%s" % (dir, full_path))
        # Upload logs separately so that we can set the MIME type properly.
        # Let's just always label the logs as UTF-8. If the data is not strict
        # ISO-8859-1, then it won't render properly anyway. If it's (even if
        # partially) UTF-8, then we made the best choice. If it's random
        # garbage, we're no worse off (plus, UTF-8 is pretty good at handling
        # that).

        aws_env = None
        if not self.config.get('auth-from-env', False):
            aws_env = dict(os.environ)
            aws_env['AWS_ACCESS_KEY_ID'] = self.config['auth-key-id']
            aws_env['AWS_SECRET_ACCESS_KEY'] = self.config['auth-secret-key']
        utils.checked_cmd(["aws", "s3", "sync", "--exclude", "*.log",
                           dir, "s3://%s" % full_path], env=aws_env)
        utils.checked_cmd(["aws", "s3", "sync",
                           "--exclude", "*", "--include", "*.log",
                           "--content-type", "text/plain; charset=utf-8",
                           dir, "s3://%s" % full_path], env=aws_env)

        return "https://s3.amazonaws.com/%s/%s" % (full_path, default_obj)

    def publish_filedata(self, data, dest, type):
        keypath = os.path.join(self.root_dir, dest)
        logger.debug("publishing file to s3://%s/%s" % (self.bucket, keypath))
        s3 = self.session.resource("s3")
        s3.Object(self.bucket, keypath).put(Body=data, ContentType=type)
        return "https://s3.amazonaws.com/%s/%s" % (self.bucket, keypath)

    @staticmethod
    def _get_default_object(dir):

        dirents = os.listdir(dir)
        if len(dirents) == 0:
            raise RuntimeError("empty dir")

        if len(dirents) == 1:
            return dirents[0]
        else:
            return "index.html"

    @staticmethod
    def _run_indexer(dir):
        # XXX: we should make this a proper python module
        utils.checked_cmd(["python3", os.path.join(PKG_DIR, "indexer.py")],
                          cwd=dir)
