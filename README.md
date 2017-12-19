### PAPR (previously called redhat-ci)

PAPR (pronounced like "paper") is a testing tool similar in
workflow to Travis CI, but with an emphasis on enabling test
environments useful for the Project Atomic effort. Only
Fedora and CentOS-based test environments are supported for
now (see [DISTROS](docs/DISTROS.md) for details).

Configured projects have a `.papr.yml` file located in their
repositories, detailing how to provision the environment and
which tests should be run. Multiple testsuites can be
defined, each with a different "context" (these refer to the
names of the status checkmarks that appear on GitHub pull
requests). A sample YAML file with allowed keys can be found
[here](docs/sample.papr.yml).

A running instance of this service is currently maintained
in the internal Red Hat infrastructure and is set up to
monitor a growing list of projects. The full list of
monitored repos appears below.

If you'd like to run *your own instance* of this service,
please see [RUNNING](docs/RUNNING.md).

### Monitored projects

- [autotest/autotest-docker](https://github.com/autotest/autotest-docker.git)
- [flatpak/flatpak](https://github.com/flatpak/flatpak)
- [flatpak/flatpak-builder](https://github.com/flatpak/flatpak-builder)
- [openshift/openshift-ansible](https://github.com/openshift/openshift-ansible)
- [ostreedev/ostree](https://github.com/ostreedev/ostree)
- [projectatomic/atomic](https://github.com/projectatomic/atomic)
- [projectatomic/atomic-host-tests](http://github.com/projectatomic/atomic-host-tests)
- [projectatomic/atomic-system-containers](https://github.com/projectatomic/atomic-system-containers)
- [projectatomic/bubblewrap](https://github.com/projectatomic/bubblewrap)
- [projectatomic/buildah](https://github.com/projectatomic/buildah)
- [projectatomic/bwrap-oci](https://github.com/projectatomic/bwrap-oci)
- [projectatomic/commissaire](https://github.com/projectatomic/commissaire)
- [projectatomic/commissaire-http](https://github.com/projectatomic/commissaire-http)
- [projectatomic/commissaire-service](https://github.com/projectatomic/commissaire-service)
- [projectatomic/container-storage-setup](https://github.com/projectatomic/container-storage-setup)
- [projectatomic/docker](https://github.com/projectatomic/docker)
- [projectatomic/libpod](https://github.com/projectatomic/libpod)
- [projectatomic/papr](https://github.com/projectatomic/papr)
- [projectatomic/registries](https://github.com/projectatomic/registries)
- [projectatomic/rpm-ostree](https://github.com/projectatomic/rpm-ostree)

**If you would like to have a repository added, please open
a pull request to update the list above.**

### More details about Project Atomic CI services

In addition to PAPR, many of the projects above are also
hooked up to
[our instance of](https://homu-projectatomic-ci.apps.ci.centos.org/)
the upstream [Homu](https://github.com/servo/homu/) project.

While PAPR deals with automatic testing of branches and
PRs, Homu is used as a merge bot.

You only need to know a few commands to interact with these
services:
 - If PR tests failed and you'd like to rerun them, use
   `bot, retest this please`.
 - If a PR is ready to be merged, use
   `@rh-atomic-bot r+ <commit sha>`. This will rebase the PR
   on the target branch, *rerun* the tests, and push the
   commits if the tests pass.
 - If the merge failed and you want to retest it, use
   `@rh-atomic-bot retry`.

**NOTE:  it is not required (but encouraged!) to use Homu as a merge
bot when using PAPR to automatically run tests against your PRs.
If your repo is currently only using PAPR and would like to start using
Homu, [open an issue here](https://github.com/projectatomic/papr/issues/new)
 to request usage of Homu.**
