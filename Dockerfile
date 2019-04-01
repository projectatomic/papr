FROM registry.fedoraproject.org/fedora:25
MAINTAINER Jonathan Lebon <jlebon@redhat.com>

# NB: we install libyaml-devel so that we can use
# CSafeLoader in PyYAML (see related comment in the parser)

RUN dnf install -y \
		git \
		gcc \
		sudo \
		docker \
		findutils \
		python3-devel \
		redhat-rpm-config \
		python3-pip \
		openssl-devel \
		libyaml-devel \
		nmap-ncat && \
	dnf clean all

# There's a tricky bit here. We mount $PWD at $PWD in the
# container so that when we do the nested docker run in the
# main script, the paths the daemon receives will still be
# correct from the host perspective.

# We use --net=host here to be able to communicate with the
# internal OpenStack instance. For some reason, the default
# bridge docker sets up causes issues. Will debug this
# properly eventually.

LABEL RUN="/usr/bin/docker run --rm --privileged \
             -v /run/docker.sock:/run/docker.sock \
             -v \"\$PWD:\$PWD\" --workdir \"\$PWD\" \
             --net=host \
             -e github_repo \
             -e github_branch \
             -e github_pull_id \
             -e github_commit \
             -e github_contexts \
             -e github_token \
             -e os_keyname \
             -e os_privkey \
             -e os_network \
             -e s3_prefix \
             -e site_repos \
             -e OS_AUTH_URL \
             -e OS_PROJECT_DOMAIN_ID \
             -e OS_REGION_NAME \
             -e OS_PROJECT_NAME \
             -e OS_USER_DOMAIN_NAME \
             -e OS_IDENTITY_API_VERSION \
             -e OS_INTERFACE \
             -e OS_PASSWORD \
             -e OS_USERNAME \
             -e OS_PROJECT_ID \
             -e AWS_ACCESS_KEY_ID \
             -e AWS_SECRET_ACCESS_KEY \
             -e BUILD_ID \
             -e RHCI_DEBUG_NO_TEARDOWN \
             -e RHCI_DEBUG_ALWAYS_RUN \
             -e RHCI_DEBUG_USE_NODE \
             \${OPT1} \
             \${IMAGE}"

COPY . /src

RUN pip3 install -r /src/requirements.txt /src

CMD ["/usr/bin/papr"]
