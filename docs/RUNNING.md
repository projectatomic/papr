### Parameters

The script takes no arguments, but expects the following
environment vars to be set:

- `github_repo` --  GitHub repo in `<owner>/<repo>` format.
- `github_branch` -- Branch to test (incompatible with
  `gihub_pull_id`).
- `github_pull_id` -- Pull request ID to test (incompatible
  with `github_branch`).

The following optional environment vars may be set:

- `github_commit` -- SHA of commit to expect; this allows
  for handling of race conditions.
- `github_token` -- If specified, update the commit status
  using GitHub's API, accessed with this repo-scoped token.
- `github_contexts` -- A pipe-separated list of contexts. If
  specified, only the testsuites which set these contexts
  will be run.
- `os_keyname` -- OpenStack keypair to use for provisioning,
  if you want to support virtualized tests.
- `os_privkey` -- Private key corresponding to the OpenStack
  keyname, if you want to support virtualized tests.
- `os_network` -- OpenStack network to use for provisioning,
  if you want to support virtualized tests.
- `os_floating_ip_pool` -- If specified, assign a floating
  IP to the provisioned node from this pool and use the IP
  to communicate with it. This is required if not running on
  the same OpenStack network as the node.
- `s3_prefix` -- If specified, artifacts will be uploaded to
  this S3 path, in `<bucket>[/<prefix>]` form.
- `site_repos` -- If specified, pipe-separated list of
  repo files to inject. Each entry specifies the OS it is
  valid for. E.g.:

```
centos/7=http://example.com/centos.repo|fedora/*=repos/fedora.repo
```

If you want to support virtualized tests, it also implicitly
expects the usual OpenStack variables needed for
authentication. These can normally be sourced from an RC
file downloadable from the OpenStack interface:

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
python-novaclient, PyYAML, jinja2, and awscli installed (the
latter only being required if artifact uploading is wanted).
Docker is also expected to be up and running for
containerized tests.

The script checks out the repo in `checkouts/$repo` and will
re-use it if available rather than cloning each time. No
builds are done on the host; the repo is transferred to the
test environment during provisioning.

A `state` directory is created, in which all temporary
files that need to be stored during a run are kept.

### Exit code

We return non-zero *only* if there is an infrastructure
error. In other words, no matter whether the PR/branch
passes or fails the tests, we should always expect a clean
exit. PR failures can be reported through the commit status
API, or by looking at the state/rc file.
