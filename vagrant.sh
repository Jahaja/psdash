#!/bin/sh
apt-get update -y
apt-get install -y build-essential python-dev python-setuptools
cd /vagrant
python setup.py develop
