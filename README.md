This repo contains scripts and files used for CI testing of
some Project Atomic repositories. The testing environment
and procedure is defined by a `.redhat-ci.yml` file located
in the project repository. A sample YAML file with allowed
keys can be found [here](sample.redhat-ci.yml).

Projects currently monitored are:

- [projectatomic/atomic](https://github.com/projectatomic/atomic)
- [projectatomic/commissaire](https://github.com/projectatomic/commissaire)
- [projectatomic/commissaire-http](https://github.com/projectatomic/commissaire-http)
- [projectatomic/commissaire-service](https://github.com/projectatomic/commissaire-service)
- [projectatomic/rpm-ostree](https://github.com/projectatomic/rpm-ostree)
- [ostreedev/ostree](https://github.com/ostreedev/ostree)

**If you would like to have a repository added, please open
a pull request to update the list above.**

### Parameters

The script takes no arguments, but expects the following
environment vars to be set:

- `github_repo` --  GitHub repo in `<owner>/<repo>` format.
- `github_branch` -- Branch to test (incompatible with
  `gihub_pull_id`).
- `github_pull_id` -- Pull request ID to test (incompatible
  with `github_branch`).
- `os_keyname` -- OpenStack keypair to use for provisioning.
- `os_network` -- OpenStack network to use for provisioning.

The following optional environment vars may be set:

- `github_commit` -- SHA of commit to expect; this allows
  for handling of race conditions.
- `github_token` -- If specified, update the commit status
  using GitHub's API, accessed with this repo-scoped token.
- `os_floating_ip_pool` -- If specified, assign a floating
  IP to the provisioned node from this pool and use the IP
  to communicate with it. This is required if not running on
  the same OpenStack network as the node.
- `s3_prefix` -- If specified, artifacts will be uploaded to
  this S3 path, in `<bucket>[/<prefix>]` form.

It also implicitly expects the usual OpenStack variables
needed for authentication. These can normally be sourced
from an RC file downloadable from the OpenStack interface:

- `OS_AUTH_URL`
- `OS_TENANT_ID`
- `OS_USERNAME`
- `OS_PASSWORD`

Finally, AWS credentials may additionally be specified if
uploading artifacts to S3:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

### Running

The `main` script integrates nicely in Jenkins, though it
can be run locally, which is useful for testing. The easiest
way to get started is to run inside a Python virtualenv with
the python-novaclient and awscli packages installed (the
latter only being required if artifact uploading is wanted).

The script checks out the repo in `checkouts/$repo` and will
re-use it if available rather than cloning each time. No
builds are done on the host; the repo is transferred to the
test node during provisioning.

A `state` directory is created, in which all temporary
files that need to be stored during a run are kept.

### Exit code

We return non-zero *only* if there is an infrastructure
error. In other words, no matter whether the PR/branch
passes or fails the tests, we should always expect a clean
exit. PR failures can be reported through the commit status
API, or by looking at the state/rc file.
