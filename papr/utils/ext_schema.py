import re

from pykwalify.core import Core
from pykwalify.errors import SchemaError

# we can't use pkg-relative imports here because pykwalify imports this file as
# its own pkg
from papr.utils import common


# http://stackoverflow.com/questions/2532053/
def _valid_hostname(hostname):
    if len(hostname) > 253:
        return False
    if re.match(r"[\d.]+$", hostname):
        return False
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)  # noqa: W605, E501
    return all(allowed.match(x) for x in hostname.split("."))


def ext_testenv(value, rule_obj, path):
    envtypes = ['host', 'container', 'cluster']
    n = sum([int(k in value) for k in envtypes])
    if n == 0:
        raise SchemaError("at least one of 'host', 'container', "
                          "or 'cluster' required")
    if n > 1:
        raise SchemaError("only one of 'host', 'container', "
                          "or 'cluster' required")
    if 'build' not in value and 'tests' not in value:
        raise SchemaError("at least one of 'build' or 'tests' required")
    return True


def ext_hosts(value, rule_obj, path):
    # Until this is fixed:
    # https://github.com/Grokzen/pykwalify/issues/67
    if type(value) is not list:
        raise SchemaError("expected list of dicts")
    for i, host in enumerate(value):
        if type(host) is not dict:
            raise SchemaError("host %d is not a dict" % i)
        if 'name' not in host:
            raise SchemaError("host %d missing key 'name'" % i)
        if 'distro' not in host:
            raise SchemaError("host %d missing key 'distro'" % i)
        if not _valid_hostname(host['name']):
            raise SchemaError("invalid hostname for host %d" % i)
        if 'ostree' in host:
            ext_ostree(host['ostree'], rule_obj, path)
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
                raise SchemaError("key '%s' of repo %d is not str or int"
                                  % (key, i))
    return True


def ext_ostree(value, rule_obj, path):
    if type(value) is str:
        if value != "latest":
            raise SchemaError("expected string 'latest'")
    elif type(value) is dict:
        schema = {'mapping':
                  {'remote': {'type': 'str'},
                   'branch': {'type': 'str'},
                   'revision': {'type': 'str'}
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


def ext_build(value, rule_obj, path):
    if type(value) not in [dict, bool]:
        raise SchemaError("expected bool or map")
    if type(value) is dict:
        schema = {'mapping':
                  {'config-opts': {'type': 'str'},
                   'build-opts': {'type': 'str'},
                   'install-opts': {'type': 'str'}
                   }
                  }
        c = Core(source_data=value, schema_data=schema)
        c.validate()
    return True
