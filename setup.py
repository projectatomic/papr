#!/usr/bin/env python3

from setuptools import setup, find_packages

# We don't define any reqs here; we're just an app for now, not a library, and
# we only support running in a dedicated container/virtualenv provisioned with
# requirements.txt. Anyway, the setuptools dep solver is not as good as pip's.

setup(
    name="papr",
    version="0.1",
    packages=find_packages(),
    entry_points={
        "console_scripts": ["papr = papr:main"],
    },
    # just copy the bash scripts for now until they're fully ported over
    package_data={"papr": ["main", "testrunner", "provisioner"],
                  # we'll hoist utils out later to just be a module in papr
                  "papr.utils": ["*.sh", "*.yml", "*.j2", "sshwait",
                                 "user-data"]}
)
