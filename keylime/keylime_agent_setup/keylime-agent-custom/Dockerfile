FROM registry.access.redhat.com/ubi8/ubi:latest

RUN dnf update -y -q && \
    dnf install -y -q python3-pip git tpm2-tss tpm2-tools && \
    pip3 install ansible && \
    git clone https://github.com/keylime/keylime.git /opt/keylime && \
    cd /opt/keylime && pip3 install -r requirements.txt && \
    dnf clean all

WORKDIR /opt/keylime
