FROM openshift/origin:v3.7
MAINTAINER Project Atomic <atomic-devel@projectatomic.io>

# NB: we install libyaml-devel so that we can use
# CSafeLoader in PyYAML (see related comment in the parser)

RUN yum install -y epel-release && \
	yum install -y \
		gcc \
		redhat-rpm-config \
		python36 \
		python36-devel \
		libyaml-devel && \
	yum clean all && \
	rm -rf /var/cache/yum && \
	python36 -m ensurepip

COPY . /src

RUN pip3 install -r /src/requirements.txt /src

ENTRYPOINT ["papr"]
