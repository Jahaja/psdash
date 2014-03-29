#!/bin/sh

yum update -y
yum install -y gcc make python-devel python-setuptools
cd /vagrant
python setup.py develop
