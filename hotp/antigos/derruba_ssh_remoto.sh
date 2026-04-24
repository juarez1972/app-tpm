#!/bin/bash
ssh 192.168.1.2 <<EOF
pkill sshd
EOF
