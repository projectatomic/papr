import utils.common as common

from pykwalify.core import Core
from pykwalify.errors import SchemaError

def ext_testenv(value, rule_obj, path):
    if 'host' in value and 'container' in value:
        raise SchemaError("only one of 'host' and 'container' allowed")
    if 'host' not in value and 'container' not in value:
        raise SchemaError("one of 'host' or 'container' required")
    return True

def ext_repos(value, rule_obj, path):
    # Until this is fixed:
    # https://github.com/Grokzen/pykwalify/issues/67
    if type(value) is not list:
        raise SchemaError("expected list of dicts")
    for i, repo in enumerate(value):
        if type(repo) is not dict:
            raise SchemaError("repo %d is not a dict" % i)
        if 'name' not in repo:
            raise SchemaError("repo %d missing key 'name'" % i)
        for key in repo:
            if type(repo[key]) not in [int, str]:
                raise SchemaError("key '%s' of repo %d is not str or int" % (key, i))
    return True

def ext_ostree(value, rule_obj, path):
    if type(value) is str:
        if value != "latest":
            raise SchemaError("expected string 'latest'")
    elif type(value) is dict:
        schema = { 'mapping':
                   { 'remote': { 'type': 'str' },
                     'branch': { 'type': 'str' },
                     'revision' : { 'type': 'str' }
                   }
                 }
        c = Core(source_data=value, schema_data=schema)
        c.validate()
    else:
        raise SchemaError("expected str or map")
    return True

def ext_timeout(value, rule_obj, path):
    if common.str_to_timeout(value) > (2 * 60 * 60):
        raise SchemaError("timeout cannot be greater than 2 hours")
    return True
