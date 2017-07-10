#!/usr/bin/env python3

import os
import sys
import subprocess

PKG_DIR = os.path.dirname(os.path.realpath(__file__))


def main():
    main_script = os.path.join(PKG_DIR, 'main')
    main_args = [main_script] + sys.argv[:1]
    return subprocess.run(main_args).returncode


if __name__ == "__main__":
    sys.exit(main())
