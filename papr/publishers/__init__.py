#!/usr/bin/env python3

import os

PKG_DIR = os.path.dirname(os.path.realpath(__file__))


class Publisher:

    def set_template_vars(self, test_name, test_url, test_sha1):
        self.test_name = test_name
        self.test_url = test_url
        self.test_sha1 = test_sha1

    def publish_dir(self, dir, dest_dir):
        raise Exception("not implemented")

    def publish_filedata(self, data, dest, content_type):
        raise Exception("not implemented")
