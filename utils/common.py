import re

# http://stackoverflow.com/a/39596504/308136
def ordinal(n):
    suffix = ['th', 'st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'th', 'th']
    if n < 0:
        n *= -1
    n = int(n)

    if n % 100 in (11, 12, 13):
        s = 'th'
    else:
        s = suffix[n % 10]

    return str(n) + s

# normalize timeout str to seconds
def str_to_timeout(s):
    assert re.match('^[0-9]+[smh]$', s)
    timeout = int(s[:-1])
    if s.endswith('m'):
        timeout *= 60
    if s.endswith('h'):
        timeout *= 60 * 60
    return timeout
