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
        "console_scripts": ["papr = papr.main:main"],
    },
    package_data={"papr": ["data/*", "schema/*", "templates/*"]}
)
