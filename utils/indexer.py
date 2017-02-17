#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2016 Jonathan Lebon
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Recursively create index.html file listings for
directories that do not have any.
"""

import jinja2

from os import getcwd, listdir
from os.path import dirname, isfile, isdir, join, realpath


def get_index(dirpath):
    "Attempts to find an index file"
    if isfile(join(dirpath, 'index.htm')):
        return 'index.htm'
    if isfile(join(dirpath, 'index.html')):
        return 'index.html'
    return None


def create_index(dirpath, at_top):
    "Creates a new index.html file"

    # get children
    files = {}
    for name in listdir(dirpath):
        if isdir(join(dirpath, name)):
            name = name + '/'
        files[name] = name
        path = join(dirpath, name)

        # link to the index.html of the child
        if isdir(path):
            index = get_index(join(dirpath, name))
            if index is None:
                index = 'index.html'
            files[name] = name + index

    tpl_fname = join(dirname(realpath(__file__)), 'index.j2')
    # Render the template to index.html
    with open(tpl_fname, 'r') as tplf:
        tpl = jinja2.Template(
            tplf.read(),
            extensions=['jinja2.ext.i18n'],
            autoescape=True)

        with open(join(dirpath, "index.html"), 'w') as f:
            f.write(tpl.render(files=files, at_top=at_top))


def recurse(dirpath):
    for name in listdir(dirpath):
        path = join(dirpath, name)
        if isdir(path):
            if get_index(path) is None:
                create_index(path, at_top=False)
                recurse(path)


def main():
    "Main entry point"
    cwd = getcwd()
    if get_index(cwd) is None:
        create_index(cwd, at_top=True)
        recurse(cwd)


if __name__ == '__main__':
    main()
