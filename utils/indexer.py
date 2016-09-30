#!/usr/bin/env python

'''
    Recursively create index.html file listings for
    directories that do no have any.
'''

from os import getcwd, listdir
from os.path import isfile, isdir, join
from cgi import escape

def get_index(dirpath):
    if isfile(join(dirpath, 'index.htm')):
        return 'index.htm'
    if isfile(join(dirpath, 'index.html')):
        return 'index.html'
    return None

def create_index(dirpath, at_top):

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

cwd = getcwd()
if get_index(cwd) is None:
    create_index(cwd, at_top=True)
    recurse(cwd)
