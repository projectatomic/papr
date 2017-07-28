import os
import pprint

from . import parser


def add_cli_parsers(subparsers):
    validate = subparsers.add_parser('validate', help='validate a YAML file')
    validate.add_argument('yml_file', help="YAML file to parse and validate")
    validate.add_argument('--output-dir', metavar="DIR",
                          help="directory to which to flush suites if desired")
    validate.set_defaults(func=_cmd_validate)


def _cmd_validate(args):
    suite_parser = parser.SuiteParser(args.yml_file)
    for idx, suite in enumerate(suite_parser.parse()):
        print("INFO: validated suite %d" % idx)
        pprint.pprint(suite, indent=4)
        if args.output_dir:
            suite_dir = os.path.join(args.output_dir, str(idx))
            parser.flush_suite(suite, suite_dir)
            print("INFO: flushed to %s" % suite_dir)
