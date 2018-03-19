### Requirements

PAPR has only two major requirements:

- Python 3.6
- A running instance of OpenShift

PAPR expects to be running in an environment where it can
e.g. `oc create` objects (i.e. with a logged in account with
at least the `edit` role).

It also requires the logged in account to have membership in
an SCC with `RunAsAny` (e.g. `privileged`). In the
`oc cluster up` workflow, you can simply login as
`system:admin` and edit the `privileged` SCC
(`oc edit scc privileged`) to add `developer` to the list of
users.

### Setup

Getting started is easy and looks much like a regular Python
app. First, create a virtualenv and install the
dependencies:

```sh
$ virtualenv-3 myenv
$ . myenv/bin/activate
# NB: make sure to have `libyaml-devel` first, see below.
$ pip install -r requirements.txt
```

Note that we use the C implementation of `PyYAML`. Make sure
to have `libyaml-devel` installed before running `pip` so
that the `PyYAML` package is aware of it during its setup.
If the `PyYAML` package is already cached, `pip` will not
run its setup again, so you'll want to use `--no-cache-dir`.

And now install PAPR in developer mode:

```sh
$ pip install -e .
```

And that's it!

### Running

The main command for running tests is `runtest`. For
example, to test the `dev` branch of the
`jlebon/papr-sandbox` repo:

```
$ papr --debug runtest --conf docs/local.yaml \
    --repo jlebon/papr-sandbox --branch dev
```

The `docs/local.yaml` config tells PAPR to keep its cache in
`$PWD/cachedir` and publish results in `$PWD/results`. Since
no GitHub token is provided, no updates are actually sent to
GitHub.

Once the test is over, you can see the results in e.g.
`results/jlebon/papr-sandbox/$commit.$timestamp/`.
