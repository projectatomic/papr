#!/usr/bin/env python

# This script is not meant to be run manually. It is called
# from the main script.

# Assumes the usual OpenStack authentication env vars are
# defined.

# Expects the following env vars:
#   os_image
#   os_flavor
#   os_keyname
#   os_network
#   os_user_data
#   os_name_prefix
#   os_floating_ip_pool (optional)

# See the README for details.

import os
import sys
import uuid
from novaclient import client

# XXX: clean this up

output_dir = sys.argv[1]

nova = client.Client(2, auth_url=os.environ['OS_AUTH_URL'],
                     tenant_id=os.environ['OS_TENANT_ID'],
                     username=os.environ['OS_USERNAME'],
                     password=os.environ['OS_PASSWORD'])

print("INFO: authenticating")
nova.authenticate()

print("INFO: resolving image '%s'" % os.environ['os_image'])
image = nova.images.find(name=os.environ['os_image'])
print("INFO: resolving flavor '%s'" % os.environ['os_flavor'])
flavor = nova.flavors.find(name=os.environ['os_flavor'])
print("INFO: resolving network '%s'" % os.environ['os_network'])
network = nova.networks.find(label=os.environ['os_network'])

# if BUILD_ID is defined, let's add it so that it's easy to
# trace back a node to the exact Jenkins build.
meta=None
if 'BUILD_ID' in os.environ:
    meta = { 'BUILD_ID': os.environ['BUILD_ID'] }

print("INFO: reading user-data file '%s'" % os.environ['os_user_data'])
with open(os.environ['os_user_data']) as f:
    userdata = f.read()

def gen_name():
    return "%s-%s" % (os.environ['os_name_prefix'], uuid.uuid4().hex[:8])

def server_exists(name):
    return len(nova.servers.findall(name=name)) > 0

max_tries = 10
name = gen_name()
while server_exists(name) and max_tries > 0:
    name = gen_name()
    max_tries -= 1

if max_tries == 0:
    print("ERROR: Can't find unique name. Something is probably broken.")
    sys.exit(1)

print("INFO: booting server '%s'" % name)
server = nova.servers.create(name, meta=meta, image=image, userdata=userdata,
                             flavor=flavor, key_name=os.environ['os_keyname'],
                             nics=[{'net-id': network.id}])

def write_to_file(fn, s):
    with open(os.path.join(output_dir, fn), 'w') as f:
        f.write(s);

write_to_file('node_name', name)

# XXX: check if there's a more elegant way to do this
# XXX: implement timeout
print("INFO: waiting for server to become active...")
while server.status == 'BUILD':
    server.get()

if server.status != 'ACTIVE':
    print("ERROR: server is not ACTIVE (state: %s)" % server.status)
    sys.exit(1)

ip = server.networks[network.label][0]
print("INFO: network IP is %s" % ip)
if 'os_floating_ip_pool' in os.environ:
    print("INFO: attaching floating ip")
    fip = nova.floating_ips.create(os.environ['os_floating_ip_pool'])
    server.add_floating_ip(fip)
    ip = fip.ip
    print("INFO: floating IP is %s" % ip)

write_to_file('node_addr', ip)
