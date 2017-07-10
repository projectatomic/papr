#!/usr/bin/env python3

'''
    Simple script to validate a YAML file.
    Usage: ./validator.py /my/github/project/.papr.yml
'''

import os
import pprint
import argparse
import papr.utils.parser as parser

argparser = argparse.ArgumentParser()
argparser.add_argument('yml_file', help="YAML file to parse and validate")
argparser.add_argument('--output-dir', metavar="DIR",
                       help="directory to which to flush suites if desired")
args = argparser.parse_args()

suite_parser = parser.SuiteParser(args.yml_file)
for idx, suite in enumerate(suite_parser.parse()):
    print("INFO: validated suite %d" % idx)
    pprint.pprint(suite, indent=4)
    if args.output_dir:
        suite_dir = os.path.join(args.output_dir, str(idx))
        parser.flush_suite(suite, suite_dir)
        print("INFO: flushed to %s" % suite_dir)
