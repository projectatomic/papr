#!/usr/bin/env python
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

from os import getcwd, listdir
from os.path import isfile, isdir, join
from cgi import escape


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
    names = []
    for name in listdir(dirpath):
        if isdir(join(dirpath, name)):
            name = name + '/'
        names.append(name)

    with open(join(dirpath, "index.html"), 'w') as f:

        # write header
        f.write("<html><head><title>Listing</title></head><body>\n")

        n = len(names)
        f.write("%d entr%s<br><br>\n" % (n, "y" if n == 1 else "ies"))

        # let's be nice and give a link back to our parent
        if not at_top:
            f.write('<a href="../index.html">..</a><br>\n')

        for name in names:
            link = name
            path = join(dirpath, name)

            # link to the index.html of the child
            if isdir(path):
                index = get_index(join(dirpath, name))
                if index is None:
                    index = 'index.html'
                link = link + index

            # escape everything for safety
            link = escape(link)
            name = escape(name)

            f.write('<a href="{0}">{1}</a><br>\n'.format(link, name))

        f.write("</body></html>")


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
