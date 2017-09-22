#!/usr/bin/env python3

'''
    This script is not meant to be run manually. It is
    called from the main script. See the README for details.

    We assume that the usual OpenStack authentication env
    vars are defined. Addtionally, the following env vars
    are expected:
      - os_image
      - os_min_ram
      - os_min_vcpus
      - os_min_disk
      - os_min_ephemeral
      - os_keyname
      - os_network
      - os_user_data
      - os_name_prefix
      - os_floating_ip_pool (optional)
'''

import os
import sys
import uuid
import time
from novaclient import client as novaclient
from cinderclient import client as cinderclient

# XXX: clean this up

output_dir = sys.argv[1]

nova = novaclient.Client(2, auth_url=os.environ['OS_AUTH_URL'],
                         tenant_id=os.environ['OS_TENANT_ID'],
                         username=os.environ['OS_USERNAME'],
                         password=os.environ['OS_PASSWORD'])

print("INFO: authenticating")
nova.authenticate()

# it's possible multiple images match, e.g. during automated
# image uploads, in which case let's just pick the first one
print("INFO: resolving image '%s'" % os.environ['os_image'])
image = nova.images.findall(name=os.environ['os_image'])[0]

# go through all the flavours and determine which one to use
min_ram = int(os.environ['os_min_ram'])
min_vcpus = int(os.environ['os_min_vcpus'])
min_disk = int(os.environ['os_min_disk'])
flavors = nova.flavors.findall()
flavors = [f for f in flavors if (f.ram >= min_ram and
                                  f.vcpus >= min_vcpus and
                                  f.disk >= min_disk)]

if len(flavors) == 0:
    print("ERROR: no flavor satisfies minimum requirements.")
    sys.exit(1)


# OK, now we need to pick the *least* resource-hungry flavor
# from the list of flavors that fit the min reqs. This is
# inevitably subjective, but here we prioritize vcpus, then
# ram, then disk.
def filter_flavors(flavors, attr):
    minval = min([getattr(f, attr) for f in flavors])
    return [f for f in flavors if getattr(f, attr) == minval]


flavors = filter_flavors(flavors, 'vcpus')
flavors = filter_flavors(flavors, 'ram')
flavors = filter_flavors(flavors, 'disk')

flavor = flavors[0]
print("INFO: choosing flavor '%s'" % flavor.name)

print("INFO: resolving network '%s'" % os.environ['os_network'])
network = nova.networks.find(label=os.environ['os_network'])

# if BUILD_ID is defined, let's add it so that it's easy to
# trace back a node to the exact Jenkins build.
meta = None
if 'BUILD_ID' in os.environ:
    meta = {'BUILD_ID': os.environ['BUILD_ID']}

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
    print("ERROR: can't find unique name. Something is probably broken.")
    sys.exit(1)

print("INFO: booting server %s" % name)
server = nova.servers.create(name, meta=meta, image=image, userdata=userdata,
                             flavor=flavor, key_name=os.environ['os_keyname'],
                             nics=[{'net-id': network.id}])
print("INFO: booted server %s (%s)" % (name, server.id))

def write_to_file(fn, s):
    with open(os.path.join(output_dir, fn), 'w') as f:
        f.write(s)

write_to_file('node_name', name)

# XXX: check if there's a more elegant way to do this
# XXX: implement timeout
print("INFO: waiting for server to become active...")
while server.status == 'BUILD':
    time.sleep(1)
    server.get()

if server.status != 'ACTIVE':
    print("ERROR: server is not ACTIVE (state: %s)" % server.status)
    print("ERROR: deleting server")
    server.delete()
    sys.exit(1)

vol = None
min_ephemeral = int(os.environ['os_min_ephemeral'])
if min_ephemeral > 0:
    try:
        print("INFO: creating volume of size %dG" % min_ephemeral)
        cinder = cinderclient.Client(2, os.environ['OS_USERNAME'],
                                     os.environ['OS_PASSWORD'],
                                     os.environ['OS_TENANT_NAME'],
                                     os.environ['OS_AUTH_URL'],)
        cinder.authenticate()
        volname = name + '-vol'
        vol = cinder.volumes.create(name=volname, size=min_ephemeral)
        print("INFO: created volume %s (%s)" % (volname, vol.id))

        print("INFO: waiting for volume to become active...")
        while vol.status == 'creating':
            time.sleep(1)
            vol.get()

        if vol.status != 'available':
            print("ERROR: volume is not avilable (state: %s)" % vol.status)
            server.delete()
            vol.delete()
            sys.exit(1)

        # now we can safely attach the volume
        nova.volumes.create_server_volume(server.id, vol.id)
    except:
        server.delete()
        if vol is not None:
            vol.delete()
        raise

ip = server.networks[network.label][0]
print("INFO: network IP is %s" % ip)
if 'os_floating_ip_pool' in os.environ:
    print("INFO: attaching floating ip")
    fip = nova.floating_ips.create(os.environ['os_floating_ip_pool'])
    server.add_floating_ip(fip)
    ip = fip.ip
    print("INFO: floating IP is %s" % ip)

write_to_file('node_addr', ip)
write_to_file('node_volid', vol.id if vol is not None else '')
