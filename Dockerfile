FROM fedora:24
MAINTAINER Jonathan Lebon <jlebon@redhat.com>

RUN dnf install -y \
		git \
		gcc \
		sudo \
		docker \
		findutils \
		python3-devel \
		redhat-rpm-config \
		python3-pip \
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
             -e github_token \
             -e os_keyname \
             -e os_privkey \
             -e os_network \
             -e os_floating_ip_pool \
             -e s3_prefix \
             -e OS_AUTH_URL \
             -e OS_TENANT_ID \
             -e OS_USERNAME \
             -e OS_PASSWORD \
             -e AWS_ACCESS_KEY_ID \
             -e AWS_SECRET_ACCESS_KEY \
             -e BUILD_ID \
             -e RHCI_DEBUG_NO_TEARDOWN \
             -e RHCI_DEBUG_ALWAYS_RUN \
             -e RHCI_DEBUG_USE_NODE \
             \${OPT1} \
             \${IMAGE}"

# When run in e.g. Jenkins, it's really annoying to not see
# any output of e.g. the provisioner until it's all done.
ENV PYTHONUNBUFFERED 1

COPY . /redhat-ci

RUN pip3 install -r /redhat-ci/requirements.txt

CMD ["/redhat-ci/main"]
